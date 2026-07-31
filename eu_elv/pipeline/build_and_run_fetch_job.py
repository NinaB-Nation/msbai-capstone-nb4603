"""
!!! DO NOT RUN AS-IS -- REWORK THE SECRET HANDLING FIRST !!!

This script's create_or_update_job() passes the service-account key as a
plaintext GCP_SA_KEY_JSON environment variable on the Job spec. On
2026-07-31 that leaked the key: Cloud Run's Admin API echoes a job's full
env-var values back in its execution/describe responses, so printing that
response to check job status put the entire private key into a session
transcript. The key was revoked and rotated (see CLAUDE.md in the
msbai-dwd-nb4603 repo for the full incident and the rules it produced).

Before this is run again it must be reworked to mount the key from Secret
Manager instead (`claude-agent@` does not yet hold `secretmanager.*` --
that needs granting), and main() must stop dumping the raw run_job()
response, selecting only status/conditions. Kept in the repo as the
working Cloud Build + Cloud Run Jobs scaffolding, not as a runnable tool.

---

Builds the automated Eurostat-fetch image via Cloud Build, creates/updates
a Cloud Run Job from it, and triggers one execution -- end to end, one
script, mirroring dashboard/build_and_deploy.py's Cloud Build pattern.

Must run as a Job, not a Service: ec.europa.eu is blocked by this dev
sandbox's own network egress policy (see DECISIONS.md), so the fetch has to
happen inside GCP. The job carries its own explicit service-account key via
an env var rather than an attached runtime identity -- see
fetch_bronze_api.py's module docstring for why (an org-policy block on
cross-project iam.serviceAccounts.actAs hit earlier for the dashboard
Service applies to Jobs too).

Each build is tagged with a unique timestamp (not :latest) for the same
reason as the dashboard build: Cloud Run only creates a new
job generation when the declared spec text changes, so an unchanged
":latest" string would silently keep the old image.
"""
import datetime
import json
import os
import sys
import tarfile
import time

import requests
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
REGION = "us-central1"
JOB = "eu-elv-fetch-bronze-api"
BUCKET = "msbai-capstone-nb4603-eu-elv-staging-us"
KEY_PATH = "/tmp/gcp-adc-credentials.json"
PIPELINE_DIR = os.path.dirname(__file__)


def get_creds():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds


def build_tarball(tag):
    tar_path = f"/tmp/eu-elv-fetch-job-src-{tag}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(os.path.join(PIPELINE_DIR, "Dockerfile.fetch_job"), arcname="Dockerfile")
        tar.add(os.path.join(PIPELINE_DIR, "fetch_job_requirements.txt"), arcname="fetch_job_requirements.txt")
        tar.add(os.path.join(PIPELINE_DIR, "fetch_bronze_api.py"), arcname="fetch_bronze_api.py")
    return tar_path


def submit_build(creds, tag, gcs_object):
    image = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{JOB}:{tag}"
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    build_config = {
        "source": {"storageSource": {"bucket": BUCKET, "object": gcs_object}},
        "steps": [{"name": "gcr.io/cloud-builders/docker", "args": ["build", "-t", image, "."]}],
        "images": [image],
    }
    r = requests.post(f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/builds", headers=headers, json=build_config)
    r.raise_for_status()
    build_id = r.json()["metadata"]["build"]["id"]
    return build_id, image


def wait_for_build(creds_getter, build_id):
    while True:
        creds = creds_getter()
        r = requests.get(
            f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/builds/{build_id}",
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        status = r.json().get("status", "UNKNOWN")
        if status in ("SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"):
            return status
        time.sleep(10)


def job_spec(image, sa_key_json):
    return {
        "template": {
            "template": {
                "containers": [{
                    "image": image,
                    "env": [
                        {"name": "GCP_SA_KEY_JSON", "value": sa_key_json},
                        {"name": "BUCKET", "value": BUCKET},
                    ],
                    "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                }],
                "timeout": "600s",
                "maxRetries": 1,
            },
            "taskCount": 1,
            "parallelism": 1,
        }
    }


def create_or_update_job(creds_getter, image):
    with open(KEY_PATH) as f:
        sa_key_json = f.read()
    creds = creds_getter()
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
    spec = job_spec(image, sa_key_json)

    r = requests.get(f"{base}/jobs/{JOB}", headers=headers)
    if r.status_code == 200:
        r = requests.patch(f"{base}/jobs/{JOB}", headers=headers, json=spec)
    else:
        r = requests.post(f"{base}/jobs?jobId={JOB}", headers=headers, json=spec)
    r.raise_for_status()
    op = r.json()
    op_name = op["name"]

    for _ in range(60):
        creds = creds_getter()
        op = requests.get(f"https://run.googleapis.com/v2/{op_name}", headers={"Authorization": f"Bearer {creds.token}"}).json()
        if op.get("done"):
            if "error" in op:
                raise RuntimeError(f"job create/update failed: {op['error']}")
            return
        time.sleep(5)
    raise TimeoutError("job create/update operation did not complete in time")


def run_job(creds_getter):
    creds = creds_getter()
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
    r = requests.post(f"{base}/jobs/{JOB}:run", headers=headers, json={})
    r.raise_for_status()
    op_name = r.json()["name"]

    for _ in range(60):
        creds = creds_getter()
        op = requests.get(f"https://run.googleapis.com/v2/{op_name}", headers={"Authorization": f"Bearer {creds.token}"}).json()
        if op.get("done"):
            return op
        time.sleep(10)
    raise TimeoutError("job execution did not complete in time")


def main():
    tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    print(f"tag: {tag}")

    tar_path = build_tarball(tag)
    gcs_object = f"cloudbuild-src/{JOB}-src-{tag}.tar.gz"
    storage.Client(project=PROJECT).bucket(BUCKET).blob(gcs_object).upload_from_filename(tar_path)
    print(f"uploaded source -> gs://{BUCKET}/{gcs_object}")

    creds = get_creds()
    build_id, image = submit_build(creds, tag, gcs_object)
    print(f"build submitted: {build_id}, image: {image}")

    status = wait_for_build(get_creds, build_id)
    print(f"build status: {status}")
    if status != "SUCCESS":
        return 1

    create_or_update_job(get_creds, image)
    print(f"job {JOB} created/updated")

    op = run_job(get_creds)
    print(json.dumps(op, indent=2)[:4000])
    if "error" in op:
        print("EXECUTION FAILED")
        return 1
    print("EXECUTION SUBMITTED/COMPLETED, see execution resource above for status")
    return 0


if __name__ == "__main__":
    sys.exit(main())

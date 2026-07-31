"""
Builds the dashboard image via Cloud Build and deploys it to Cloud Run,
end to end, as one script -- replaces the earlier separate build-then-
deploy_cloud_run.py flow.

Each run tags the image with a unique, timestamp-based tag (not just
:latest) and deploys that exact tag. This is required, not cosmetic:
Cloud Run only creates a new revision when the *declared service spec*
changes text -- redeploying an unchanged ":latest" string is a no-op to
Cloud Run even though the image content behind that tag changed, so a
previous redeploy silently kept serving the old revision. A unique tag
per build guarantees the spec text always changes.
"""
import datetime
import os
import subprocess
import sys
import tarfile
import time

import requests
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
REGION = "us-central1"
SERVICE = "eu-elv-dashboard"
BUCKET = "msbai-capstone-nb4603-eu-elv-staging"
KEY_PATH = "/tmp/gcp-adc-credentials.json"
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")


def get_creds():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds


def build_tarball(tag):
    tar_path = f"/tmp/eu-elv-dashboard-src-{tag}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name in ["app.py", "requirements.txt", "Dockerfile", ".dockerignore", "data"]:
            tar.add(os.path.join(DASHBOARD_DIR, name), arcname=name)
    return tar_path


def submit_build(creds, tag, gcs_object):
    image = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/eu-elv-dashboard:{tag}"
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


def deploy(creds_getter, image):
    creds = creds_getter()
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"

    service_config = {
        "template": {
            "scaling": {"minInstanceCount": 0, "maxInstanceCount": 2},
            "containers": [{
                "image": image,
                "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                "ports": [{"containerPort": 8080}],
            }],
        }
    }

    r = requests.get(f"{base}/services/{SERVICE}", headers=headers)
    if r.status_code == 200:
        r = requests.patch(f"{base}/services/{SERVICE}", headers=headers, json=service_config)
    else:
        r = requests.post(f"{base}/services?serviceId={SERVICE}", headers=headers, json=service_config)
    r.raise_for_status()
    op_name = r.json()["name"]

    for _ in range(60):
        creds = creds_getter()
        op = requests.get(f"https://run.googleapis.com/v2/{op_name}", headers={"Authorization": f"Bearer {creds.token}"}).json()
        if op.get("done"):
            if "error" in op:
                raise RuntimeError(f"deploy failed: {op['error']}")
            return op["response"]
        time.sleep(5)
    raise TimeoutError("deploy operation did not complete in time")


def main():
    tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    print(f"tag: {tag}")

    tar_path = build_tarball(tag)
    gcs_object = f"cloudbuild-src/eu-elv-dashboard-src-{tag}.tar.gz"
    storage.Client(project=PROJECT).bucket(BUCKET).blob(gcs_object).upload_from_filename(tar_path)
    print(f"uploaded source -> gs://{BUCKET}/{gcs_object}")

    creds = get_creds()
    build_id, image = submit_build(creds, tag, gcs_object)
    print(f"build submitted: {build_id}, image: {image}")

    status = wait_for_build(get_creds, build_id)
    print(f"build status: {status}")
    if status != "SUCCESS":
        return 1

    result = deploy(get_creds, image)
    print(f"DEPLOY SUCCEEDED. URL: {result.get('uri')}")
    print(f"revision: {result.get('latestReadyRevision', result.get('name'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

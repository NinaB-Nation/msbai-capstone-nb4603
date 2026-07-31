"""
Builds the automated Eurostat-fetch image via Cloud Build, creates/updates a
Cloud Run Job from it, and triggers one execution -- end to end, one script,
mirroring dashboard/build_and_deploy.py's Cloud Build pattern.

Must run as a Job, not a Service: ec.europa.eu is blocked by this dev
sandbox's own network egress policy (see DECISIONS.md), so the fetch has to
happen inside GCP.

Each build is tagged with a unique timestamp (not :latest) for the same
reason as the dashboard build: Cloud Run only creates a new job generation
when the declared spec text changes, so an unchanged ":latest" string would
silently keep the old image.

SECRET HANDLING -- reworked 2026-07-31 after the key leak
---------------------------------------------------------
The previous version passed the service-account key as a plaintext
GCP_SA_KEY_JSON environment variable on the Job spec. Cloud Run's Admin API
echoes a job's full env-var values back in its describe/execution responses,
so printing that response to check job status put the entire private key
into a session transcript. The key was revoked and rotated. Two rules came
out of that incident (see CLAUDE.md in the msbai-dwd-nb4603 repo), and this
script now follows both:

  1. The key is stored in Secret Manager and **mounted as a file** into the
     container (`/secrets/sa/key.json`). The Job spec then contains only a
     secret *reference*, so the Admin API has no key material to echo back.
  2. No raw Cloud Run API response is ever printed. Every status readout
     here selects named fields (status / conditions / counts) instead of
     dumping the object.

Prerequisites -- both granted 2026-07-31, both re-checked by preflight()
------------------------------------------------------------------------
  a. `secretmanager.googleapis.com` enabled on msbai-capstone-nb4603. This
     is separate from IAM: while the API is off every call 403s with "has
     not been used in project", no matter what roles are held.
  b. `roles/secretmanager.admin` on msbai-capstone-nb4603 for
     claude-agent@msbai-dwd-nb4603.iam.gserviceaccount.com, covering
     secrets.create/get, versions.add, and secrets.get/setIamPolicy.

preflight() re-verifies both and refuses to run rather than failing partway
and leaving a half-created secret behind.

Runtime identity: the Job keeps Cloud Run's project-local default compute
service account (see DECISIONS.md, "Deployment" -- an org policy blocks
cross-project iam.serviceAccounts.actAs, so the job cannot run *as*
claude-agent@). That default SA is what needs read access to the secret, so
ensure_secret() binds roles/secretmanager.secretAccessor to it on the secret
itself, not project-wide.
"""
import base64
import datetime
import os
import sys
import tarfile
import time

import requests
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
PROJECT_NUMBER = "919371925869"
REGION = "us-central1"
JOB = "eu-elv-fetch-bronze-api"
BUCKET = "msbai-capstone-nb4603-eu-elv-staging-us"
KEY_PATH = "/tmp/gcp-adc-credentials.json"
PIPELINE_DIR = os.path.dirname(__file__)

SECRET_ID = "eu-elv-fetch-sa-key"
SECRET_MOUNT_DIR = "/secrets/sa"
SECRET_FILENAME = "key.json"
# Cloud Run's project-local default runtime identity for this job.
RUNTIME_SA = f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

RUN_BASE = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
SM_BASE = f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}"
REQUIRED_SM_PERMISSIONS = [
    "secretmanager.secrets.create",
    "secretmanager.secrets.get",
    "secretmanager.versions.add",
    "secretmanager.secrets.getIamPolicy",
    "secretmanager.secrets.setIamPolicy",
]


def get_creds():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds


def auth_headers(creds):
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def check(r, what):
    """raise_for_status, but keep the API's explanation.

    Bare raise_for_status() reports only the status line and URL, which for
    a malformed Job spec means losing the one thing that identifies the bad
    field. Safe to surface: an error body is a google.rpc.Status (message +
    fieldViolations), not the Job resource, and the spec no longer carries
    key material for a violation to quote back.
    """
    if r.status_code < 400:
        return r
    try:
        message = r.json().get("error", {}).get("message", "")
    except ValueError:
        message = r.text[:300]
    raise RuntimeError(f"{what}: HTTP {r.status_code} -- {message}")


def preflight(creds):
    """Fail early, with the exact ask, if Secret Manager is unusable.

    Checked in this order because API enablement gates the IAM check: while
    the API is off, every Secret Manager call 403s regardless of roles held.
    """
    problems = []

    # Two different things return 403 here, and they need different fixes.
    # "has not been used in project" means the API itself is off -- no role
    # grant will clear it. Any other 403 is an ordinary permission denial,
    # which the testIamPermissions check below reports far more precisely,
    # so it is not repeated as a separate ask.
    r = requests.get(f"{SM_BASE}/secrets", headers=auth_headers(creds))
    if r.status_code == 403 and "has not been used in project" in r.text:
        problems.append(
            f"Secret Manager API is not enabled on {PROJECT}.\n"
            f"      ASK: enable secretmanager.googleapis.com on {PROJECT}\n"
            f"      (allow a few minutes for propagation -- cloudbuild and run\n"
            f"      both needed that wait after being enabled)"
        )
    elif r.status_code not in (200, 403):
        msg = r.json().get("error", {}).get("message", "")[:200]
        problems.append(f"Secret Manager returned {r.status_code}: {msg}")

    r = requests.post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT}:testIamPermissions",
        headers=auth_headers(creds), json={"permissions": REQUIRED_SM_PERMISSIONS},
    )
    held = set(r.json().get("permissions", [])) if r.status_code == 200 else set()
    missing = [p for p in REQUIRED_SM_PERMISSIONS if p not in held]
    if missing:
        problems.append(
            "claude-agent@ is missing Secret Manager permissions:\n"
            + "".join(f"        - {p}\n" for p in missing)
            + f"      ASK: grant roles/secretmanager.admin to\n"
            f"      claude-agent@msbai-dwd-nb4603.iam.gserviceaccount.com on {PROJECT}"
        )

    if problems:
        print("PREFLIGHT FAILED -- not running. Outstanding asks:\n")
        for i, problem in enumerate(problems, 1):
            print(f"  {i}. {problem}\n")
        return False

    print("preflight OK: Secret Manager API enabled and permissions held")
    return True


def ensure_secret(creds_getter):
    """Create/update the secret holding the SA key, and let the job read it.

    The key material goes in the request body of addVersion, which is not
    echoed back by any subsequent describe call -- unlike a Job env var.
    """
    with open(KEY_PATH, "rb") as f:
        key_bytes = f.read()

    headers = auth_headers(creds_getter())
    r = requests.get(f"{SM_BASE}/secrets/{SECRET_ID}", headers=headers)
    if r.status_code == 404:
        r = requests.post(
            f"{SM_BASE}/secrets?secretId={SECRET_ID}",
            headers=headers, json={"replication": {"automatic": {}}},
        )
        check(r, "create secret")
        print(f"  created secret {SECRET_ID}")
    else:
        check(r, "get secret")
        print(f"  secret {SECRET_ID} already exists")

    # Only add a version if the key actually changed. Every run would
    # otherwise mint a new version of identical material, and Secret
    # Manager's Always Free tier covers just 6 active versions -- the same
    # free-tier sensitivity that drove the us-central1 bucket choice.
    payload = base64.b64encode(key_bytes).decode()
    r = requests.get(f"{SM_BASE}/secrets/{SECRET_ID}/versions/latest:access",
                     headers=auth_headers(creds_getter()))
    if r.status_code == 200 and r.json().get("payload", {}).get("data") == payload:
        print("  latest secret version already holds this key; not adding another")
    else:
        r = requests.post(
            f"{SM_BASE}/secrets/{SECRET_ID}:addVersion",
            headers=auth_headers(creds_getter()), json={"payload": {"data": payload}},
        )
        check(r, "add secret version")
        # Print the version *name* only -- never the payload.
        print(f"  added secret version {r.json()['name'].rsplit('/', 1)[-1]}")

    # Bind secretAccessor to the job's runtime identity, on this secret only.
    # getIamPolicy is a GET on Secret Manager (setIamPolicy is a POST);
    # POSTing it returns 404, not 405, which reads misleadingly like a
    # missing secret.
    r = requests.get(f"{SM_BASE}/secrets/{SECRET_ID}:getIamPolicy",
                     headers=auth_headers(creds_getter()))
    check(r, "get secret IAM policy")
    policy = r.json()
    bindings = policy.get("bindings", [])
    member = f"serviceAccount:{RUNTIME_SA}"
    accessor = next(
        (b for b in bindings if b["role"] == "roles/secretmanager.secretAccessor"), None
    )
    if accessor is None:
        bindings.append({"role": "roles/secretmanager.secretAccessor", "members": [member]})
    elif member not in accessor.get("members", []):
        accessor.setdefault("members", []).append(member)
    else:
        print(f"  {RUNTIME_SA} already has secretAccessor")
        return

    policy["bindings"] = bindings
    r = requests.post(
        f"{SM_BASE}/secrets/{SECRET_ID}:setIamPolicy",
        headers=auth_headers(creds_getter()), json={"policy": policy},
    )
    check(r, "set secret IAM policy")
    print(f"  granted secretAccessor on {SECRET_ID} to {RUNTIME_SA}")


def build_tarball(tag):
    tar_path = f"/tmp/eu-elv-fetch-job-src-{tag}.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(os.path.join(PIPELINE_DIR, "Dockerfile.fetch_job"), arcname="Dockerfile")
        tar.add(os.path.join(PIPELINE_DIR, "fetch_job_requirements.txt"),
                arcname="fetch_job_requirements.txt")
        tar.add(os.path.join(PIPELINE_DIR, "fetch_bronze_api.py"), arcname="fetch_bronze_api.py")
    return tar_path


def submit_build(creds, tag, gcs_object):
    image = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/{JOB}:{tag}"
    build_config = {
        "source": {"storageSource": {"bucket": BUCKET, "object": gcs_object}},
        "steps": [{"name": "gcr.io/cloud-builders/docker", "args": ["build", "-t", image, "."]}],
        "images": [image],
    }
    r = requests.post(
        f"https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/builds",
        headers=auth_headers(creds), json=build_config,
    )
    check(r, "submit build")
    return r.json()["metadata"]["build"]["id"], image


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


def job_spec(image):
    """Job spec carrying a secret *reference*, never key material.

    Everything in this dict is safe to echo back from the Admin API: the
    only thing it says about the key is which secret and version to mount.
    """
    return {
        "template": {
            "template": {
                "containers": [{
                    "image": image,
                    "env": [
                        {"name": "GCP_SA_KEY_FILE",
                         "value": f"{SECRET_MOUNT_DIR}/{SECRET_FILENAME}"},
                        {"name": "BUCKET", "value": BUCKET},
                    ],
                    "volumeMounts": [{"name": "sa-key", "mountPath": SECRET_MOUNT_DIR}],
                    "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                }],
                "volumes": [{
                    "name": "sa-key",
                    "secret": {
                        "secret": SECRET_ID,
                        # v2 calls this "items"; "versions" is the v1/Knative
                        # spelling and is rejected with a 400 "Cannot find
                        # field", not silently ignored.
                        "items": [{"version": "latest", "path": SECRET_FILENAME}],
                    },
                }],
                "timeout": "600s",
                "maxRetries": 1,
            },
            "taskCount": 1,
            "parallelism": 1,
        }
    }


def wait_for_operation(creds_getter, op_name, what, tries=60, delay=5):
    """Poll a long-running operation, reporting only named fields."""
    for _ in range(tries):
        creds = creds_getter()
        op = requests.get(
            f"https://run.googleapis.com/v2/{op_name}",
            headers={"Authorization": f"Bearer {creds.token}"},
        ).json()
        if op.get("done"):
            if "error" in op:
                # op["error"] is a status object (code/message), not the
                # resource -- no env or volume contents can appear here.
                err = op["error"]
                raise RuntimeError(
                    f"{what} failed: code={err.get('code')} message={err.get('message')}"
                )
            return op
        time.sleep(delay)
    raise TimeoutError(f"{what} did not complete in time")


def create_or_update_job(creds_getter, image):
    headers = auth_headers(creds_getter())
    spec = job_spec(image)
    r = requests.get(f"{RUN_BASE}/jobs/{JOB}", headers=headers)
    if r.status_code == 200:
        r = requests.patch(f"{RUN_BASE}/jobs/{JOB}", headers=headers, json=spec)
    else:
        r = requests.post(f"{RUN_BASE}/jobs?jobId={JOB}", headers=headers, json=spec)
    check(r, "create/update job")
    wait_for_operation(creds_getter, r.json()["name"], "job create/update")


def run_job(creds_getter, probe=False, dump=False):
    # Cloud Run applies containerOverrides per execution, so probe mode needs
    # no separate job spec or redeploy -- the deployed job is unchanged.
    body = {}
    env = []
    if probe:
        env.append({"name": "PROBE_ONLY", "value": "1"})
    if dump:
        env.append({"name": "DUMP_STRUCTURE", "value": "1"})
    if env:
        body = {"overrides": {"containerOverrides": [{"env": env}]}}
    r = requests.post(f"{RUN_BASE}/jobs/{JOB}:run",
                      headers=auth_headers(creds_getter()), json=body)
    check(r, "run job")
    op = wait_for_operation(creds_getter, r.json()["name"], "job execution",
                            tries=60, delay=10)
    return op.get("response", {})


def summarize_execution(execution):
    """Print only named execution fields.

    Deliberately does NOT print the execution object: it embeds the full job
    template, and it was exactly this dump that leaked the key when the
    template still carried a plaintext env var. Even now that the template
    holds only a secret reference, selecting fields stays the rule.
    """
    print("  execution summary:")
    for field in ("succeededCount", "failedCount", "cancelledCount",
                  "retriedCount", "runningCount", "taskCount"):
        if field in execution:
            print(f"    {field:16s} {execution[field]}")
    name = execution.get("name", "")
    if name:
        print(f"    {'execution':16s} {name.rsplit('/', 1)[-1]}")
    for cond in execution.get("conditions", []):
        line = f"    condition        {cond.get('type')}={cond.get('state')}"
        if cond.get("message"):
            line += f" ({cond['message']})"
        print(line)
    return (int(execution.get("failedCount", 0) or 0) == 0
            and int(execution.get("succeededCount", 0) or 0) > 0)


def main():
    probe = "--probe" in sys.argv
    dump = "--dump-structure" in sys.argv
    creds = get_creds()
    if not preflight(creds):
        return 1

    tag = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dt%H%M%S")
    print(f"tag: {tag}")

    print("secret:")
    ensure_secret(get_creds)

    tar_path = build_tarball(tag)
    gcs_object = f"cloudbuild-src/{JOB}-src-{tag}.tar.gz"
    # Pass credentials explicitly, like every other call here. Left to
    # itself the storage client falls back to ambient ADC, which only
    # happens to be set when the SessionStart hook has exported
    # GOOGLE_APPLICATION_CREDENTIALS -- so the script worked in the session
    # that wrote it and failed with DefaultCredentialsError in one where
    # the hook no-opped, despite KEY_PATH being present and valid either way.
    storage.Client(project=PROJECT, credentials=get_creds()) \
        .bucket(BUCKET).blob(gcs_object).upload_from_filename(tar_path)
    print(f"uploaded source -> gs://{BUCKET}/{gcs_object}")

    build_id, image = submit_build(get_creds(), tag, gcs_object)
    print(f"build submitted: {build_id}, image: {image}")

    status = wait_for_build(get_creds, build_id)
    print(f"build status: {status}")
    if status != "SUCCESS":
        return 1

    create_or_update_job(get_creds, image)
    print(f"job {JOB} created/updated (key mounted from secret {SECRET_ID})")
    if probe:
        print("running in PROBE mode: headers only, no BigQuery load")

    execution = run_job(get_creds, probe=probe, dump=dump)
    ok = summarize_execution(execution)
    print("EXECUTION SUCCEEDED" if ok else "EXECUTION FAILED -- check Cloud Run job logs")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""
Deploys the built image to Cloud Run via the Admin API v2 REST endpoints
directly (no gcloud CLI available in this environment). Does not touch IAM
(public-invoker binding is a separate, explicitly-approved step).

Deliberately does NOT set a runtime serviceAccount: the dashboard makes zero
GCP API calls at request time (it reads a baked-in CSV extract -- see
DECISIONS.md), so it has no need for the cross-project claude-agent@
identity used elsewhere in this pipeline. Letting Cloud Run default to
msbai-capstone-nb4603's own project-local compute service account avoids
the iam.serviceAccounts.actAs cross-project friction entirely rather than
fighting it -- that identity exists in-project already (confirmed: Cloud
Build used it automatically for the image build).
"""
import sys
import time

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

PROJECT = "msbai-capstone-nb4603"
REGION = "us-central1"
SERVICE = "eu-elv-dashboard"
IMAGE = f"us-central1-docker.pkg.dev/{PROJECT}/cloud-run-source-deploy/eu-elv-dashboard:latest"
KEY_PATH = "/tmp/gcp-adc-credentials.json"


def get_token():
    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(Request())
    return creds.token


def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    base = f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"

    service_config = {
        "template": {
            "scaling": {"minInstanceCount": 0, "maxInstanceCount": 2},
            "containers": [{
                "image": IMAGE,
                "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                "ports": [{"containerPort": 8080}],
            }],
        }
    }

    r = requests.get(f"{base}/services/{SERVICE}", headers=headers)
    if r.status_code == 200:
        print("service exists, patching...")
        r = requests.patch(f"{base}/services/{SERVICE}", headers=headers, json=service_config)
    else:
        print("creating new service...")
        r = requests.post(f"{base}/services?serviceId={SERVICE}", headers=headers, json=service_config)

    print("deploy status", r.status_code)
    resp = r.json()
    if r.status_code not in (200,):
        print(resp)
        return 1

    op_name = resp["name"]
    print("operation:", op_name)

    for _ in range(60):
        token = get_token()
        op = requests.get(
            f"https://run.googleapis.com/v2/{op_name}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        if op.get("done"):
            if "error" in op:
                print("DEPLOY FAILED:", op["error"])
                return 1
            uri = op["response"].get("uri")
            print("DEPLOY SUCCEEDED. URL:", uri)
            with open("/tmp/cloud_run_url.txt", "w") as f:
                f.write(uri or "")
            return 0
        time.sleep(5)

    print("timed out waiting for deploy operation")
    return 1


if __name__ == "__main__":
    sys.exit(main())

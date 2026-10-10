import json
import subprocess

import pytest


def _kubectl_ok():
    try:
        r = subprocess.run(["kubectl", "--context", "kind-platform", "get", "ns"],
                            capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _kubectl_ok(), reason="needs the kind-platform cluster with ArgoCD installed")


def test_18_applications_from_one_applicationset():
    out = subprocess.run(
        ["kubectl", "--context", "kind-platform", "-n", "argocd",
         "get", "applications.argoproj.io", "-o", "json"],
        capture_output=True, text=True, timeout=20,
    )
    apps = json.loads(out.stdout)["items"]
    names = {a["metadata"]["name"] for a in apps}
    expected = {f"cluster-{c}-svc{n}" for c in "abc" for n in range(1, 7)}
    assert names == expected
    assert len(names) == 18

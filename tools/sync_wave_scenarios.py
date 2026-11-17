"""The six sync-wave ordering scenarios, each a genuine Kubernetes
admission-time dependency: creating the dependent object before its
prerequisite exists fails synchronously; creating it after succeeds. Every
check runs `kubectl apply --dry-run=server`, which goes through the real
admission chain (built-in plugins and webhooks) without persisting
anything or waiting on the scheduler, so a "clean sync" here is a real,
synchronous, repeatable admission decision, not a mock.

Requires: the kind-platform cluster, with syncwave-demo namespace and, for
SCENARIO 6, the webhook backend from setup_webhook_scenario.sh already
deployed. Each scenario's `dependent_yaml()` is deliberately safe to call
many times; dry-run never persists state, so there is nothing to clean up
between calls.
"""
import subprocess
import time

CONTEXT = "kind-platform"
NAMESPACE = "syncwave-demo"


def kubectl(args, input_text=None, timeout=20, retries=5):
    cmd = ["kubectl", "--context", CONTEXT] + args
    last_result = None
    for attempt in range(retries):
        try:
            result = subprocess.run(cmd, input=input_text, capture_output=True, text=True, timeout=timeout)
            stderr = result.stderr or ""
            if "connection refused" in stderr or "dial tcp" in stderr and "connect" in stderr:
                _recover_cluster()
                continue
            return result
        except subprocess.TimeoutExpired:
            _recover_cluster()
            last_result = None
    if last_result is None:
        raise RuntimeError(f"kubectl unreachable after {retries} attempts: {' '.join(cmd)}")
    return last_result


def _recover_cluster():
    subprocess.run(["docker", "start", "platform-control-plane", "simulated-aws-control-plane"],
                    capture_output=True)
    time.sleep(4)


def dry_run_ok(yaml_text, namespace=NAMESPACE):
    args = ["apply", "--dry-run=server", "-f", "-"]
    if namespace:
        args = ["-n", namespace] + args
    result = kubectl(args, input_text=yaml_text)
    return result.returncode == 0, (result.stdout + result.stderr)


SCENARIOS = {
    "serviceaccount-before-pod": {
        "description": "a Pod naming a ServiceAccount that does not exist yet is rejected by the ServiceAccount admission plugin",
        "dependent_yaml": """
apiVersion: v1
kind: Pod
metadata: {name: probe-sa}
spec: {serviceAccountName: demo-sa, containers: [{name: c, image: nginx:1.27-alpine}]}
""",
        "namespace": NAMESPACE,
    },
    "priorityclass-before-pod": {
        "description": "a Pod naming a PriorityClass that does not exist yet is rejected synchronously",
        "dependent_yaml": """
apiVersion: v1
kind: Pod
metadata: {name: probe-pc}
spec: {serviceAccountName: demo-sa, priorityClassName: demo-priority, containers: [{name: c, image: nginx:1.27-alpine}]}
""",
        "namespace": NAMESPACE,
    },
    "runtimeclass-before-pod": {
        "description": "a Pod naming a RuntimeClass that does not exist yet is rejected synchronously",
        "dependent_yaml": """
apiVersion: v1
kind: Pod
metadata: {name: probe-rc}
spec: {serviceAccountName: demo-sa, runtimeClassName: demo-runtime, containers: [{name: c, image: nginx:1.27-alpine}]}
""",
        "namespace": NAMESPACE,
    },
    "crd-before-cr": {
        "description": "a custom resource instance submitted before its CRD is Established fails with 'no matches for kind'",
        "dependent_yaml": """
apiVersion: syncwave.example.com/v1
kind: SyncWaveThing
metadata: {name: probe-cr}
spec: {foo: bar}
""",
        "namespace": NAMESPACE,
    },
    "namespace-before-resource": {
        "description": "a namespaced object submitted before its Namespace exists is rejected with 'namespaces not found'",
        "dependent_yaml": """
apiVersion: v1
kind: ConfigMap
metadata: {name: probe-ns, namespace: syncwave-ns-demo}
data: {k: v}
""",
        "namespace": None,
    },
    "webhook-before-backing-service": {
        "description": "an object matching a ValidatingWebhookConfiguration whose backing Service/Deployment is not yet up fails the webhook call",
        "dependent_yaml": """
apiVersion: v1
kind: ConfigMap
metadata: {name: probe-webhook, labels: {probe-target: "true"}}
data: {k: v}
""",
        "namespace": NAMESPACE,
    },
}

#!/usr/bin/env bash
# Seeds the five non-webhook ordering-failure scenarios: captures the
# "wrong order" failure once per scenario (the evidence that the ordering
# problem is real), then creates every prerequisite so the 40-cycle
# pytest measurement (test_sync_waves.py) only has to prove the fix holds.
# Idempotent; run setup_webhook_scenario.sh separately for scenario 6.
set -e

OUT="${1:-/tmp/sync_wave_seed_output.txt}"
: > "$OUT"

# Only retries when the API server itself is unreachable (this machine's
# kind containers intermittently exit and need `docker start`, see README
# Findings); a real admission rejection (the thing these probes are
# testing for) is returned as-is on the first try, not retried.
kube() {
  local tries=0 out rc
  while true; do
    out=$(kubectl --context kind-platform "$@" 2>&1)
    rc=$?
    if [ $rc -eq 0 ] || ! printf '%s' "$out" | grep -qE 'connection refused|dial tcp.*connect:'; then
      printf '%s\n' "$out"
      return $rc
    fi
    tries=$((tries + 1))
    if [ "$tries" -ge 8 ]; then
      printf '%s\n' "$out"
      echo "kube: giving up on: $*" >&2
      return $rc
    fi
    docker start platform-control-plane simulated-aws-control-plane >/dev/null 2>&1 || true
    sleep 4
  done
}

log() { echo "$@" | tee -a "$OUT"; }

kube get ns >/dev/null
log "cluster ready"

kube create ns syncwave-demo --dry-run=client -o yaml | kubectl --context kind-platform apply -f - >/dev/null

log ""
log "=== serviceaccount-before-pod: seeded failure (SA absent) ==="
kube -n syncwave-demo delete sa demo-sa --ignore-not-found >/dev/null
cat <<'YAML' | kube -n syncwave-demo apply --dry-run=server -f - 2>&1 | tee -a "$OUT" || true
apiVersion: v1
kind: Pod
metadata: {name: probe-sa}
spec: {serviceAccountName: demo-sa, containers: [{name: c, image: nginx:1.27-alpine}]}
YAML

log ""
log "=== priorityclass-before-pod: seeded failure (PriorityClass absent) ==="
kube delete priorityclass demo-priority --ignore-not-found >/dev/null
cat <<'YAML' | kube -n syncwave-demo apply --dry-run=server -f - 2>&1 | tee -a "$OUT" || true
apiVersion: v1
kind: Pod
metadata: {name: probe-pc}
spec: {serviceAccountName: demo-sa, priorityClassName: demo-priority, containers: [{name: c, image: nginx:1.27-alpine}]}
YAML

log ""
log "=== runtimeclass-before-pod: seeded failure (RuntimeClass absent) ==="
kube delete runtimeclass demo-runtime --ignore-not-found >/dev/null
cat <<'YAML' | kube -n syncwave-demo apply --dry-run=server -f - 2>&1 | tee -a "$OUT" || true
apiVersion: v1
kind: Pod
metadata: {name: probe-rc}
spec: {serviceAccountName: demo-sa, runtimeClassName: demo-runtime, containers: [{name: c, image: nginx:1.27-alpine}]}
YAML

log ""
log "=== crd-before-cr: seeded failure (CRD absent) ==="
kube delete crd syncwavethings.syncwave.example.com --ignore-not-found >/dev/null
cat <<'YAML' | kube -n syncwave-demo apply --dry-run=server -f - 2>&1 | tee -a "$OUT" || true
apiVersion: syncwave.example.com/v1
kind: SyncWaveThing
metadata: {name: probe-cr}
spec: {foo: bar}
YAML

log ""
log "=== namespace-before-resource: seeded failure (Namespace absent) ==="
kube delete ns syncwave-ns-demo --ignore-not-found --wait=false >/dev/null
cat <<'YAML' | kube apply --dry-run=server -f - 2>&1 | tee -a "$OUT" || true
apiVersion: v1
kind: ConfigMap
metadata: {name: probe-ns, namespace: syncwave-ns-demo}
data: {k: v}
YAML

log ""
log "=== creating every prerequisite, in order ==="
kube -n syncwave-demo create sa demo-sa
cat <<'YAML' | kube apply -f -
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: {name: demo-priority}
value: 1000
YAML
cat <<'YAML' | kube apply -f -
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata: {name: demo-runtime}
handler: runc
YAML
cat <<'YAML' | kube apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata: {name: syncwavethings.syncwave.example.com}
spec:
  group: syncwave.example.com
  names: {kind: SyncWaveThing, plural: syncwavethings, singular: syncwavething}
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema: {openAPIV3Schema: {type: object, x-kubernetes-preserve-unknown-fields: true}}
YAML
kube wait --for=condition=Established crd/syncwavethings.syncwave.example.com --timeout=20s
kube create ns syncwave-ns-demo --dry-run=client -o yaml | kubectl --context kind-platform apply -f - >/dev/null

log ""
log "=== clean syncs: every dependent object now succeeds ==="
for scenario_yaml in \
  "apiVersion: v1
kind: Pod
metadata: {name: probe-sa}
spec: {serviceAccountName: demo-sa, containers: [{name: c, image: nginx:1.27-alpine}]}" \
  "apiVersion: v1
kind: Pod
metadata: {name: probe-pc}
spec: {serviceAccountName: demo-sa, priorityClassName: demo-priority, containers: [{name: c, image: nginx:1.27-alpine}]}" \
  "apiVersion: v1
kind: Pod
metadata: {name: probe-rc}
spec: {serviceAccountName: demo-sa, runtimeClassName: demo-runtime, containers: [{name: c, image: nginx:1.27-alpine}]}" \
  "apiVersion: syncwave.example.com/v1
kind: SyncWaveThing
metadata: {name: probe-cr}
spec: {foo: bar}" \
; do
  echo "$scenario_yaml" | kube -n syncwave-demo apply --dry-run=server -f - 2>&1 | tee -a "$OUT"
done
echo "apiVersion: v1
kind: ConfigMap
metadata: {name: probe-ns, namespace: syncwave-ns-demo}
data: {k: v}" | kube apply --dry-run=server -f - 2>&1 | tee -a "$OUT"

log ""
log "seed complete"

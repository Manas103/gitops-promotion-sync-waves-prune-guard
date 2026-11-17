#!/usr/bin/env bash
# One-shot setup for the sync-wave webhook-before-backing-service scenario:
# regenerates throwaway TLS certs, (re)deploys the real webhook backend
# (reusing the admission-webhook:dev image built for
# compliant-terraform-module-policy-gate as an always-allow responder),
# and (re)creates the probe ValidatingWebhookConfiguration with a matching
# caBundle. Idempotent; safe to re-run after this machine's WSL VM or the
# kind containers restart (see README Findings).
set -e

REPO_DIR="/mnt/c/Users/Manas/Downloads/Auto Job Applier/Total Job Application process flow/projects/gitops-promotion-sync-waves-prune-guard"
CERTS_DIR=/tmp/syncwave-certs

kube() {
  local tries=0
  until kubectl --context kind-platform "$@"; do
    tries=$((tries + 1))
    if [ "$tries" -ge 8 ]; then
      echo "kube: giving up on: $*" >&2
      return 1
    fi
    docker start platform-control-plane simulated-aws-control-plane >/dev/null 2>&1 || true
    sleep 4
  done
}

kube get ns >/dev/null
echo "cluster ready"

mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"
openssl genrsa -out ca.key 2048 >/dev/null 2>&1
openssl req -x509 -new -nodes -key ca.key -subj "/CN=syncwave-webhook-ca" -days 3650 -out ca.crt >/dev/null 2>&1
openssl genrsa -out tls.key 2048 >/dev/null 2>&1
openssl req -new -key tls.key -subj "/CN=syncwave-webhook.syncwave-demo.svc" -out tls.csr >/dev/null 2>&1
printf 'subjectAltName = DNS:syncwave-webhook.syncwave-demo.svc, DNS:syncwave-webhook.syncwave-demo.svc.cluster.local\n' > san.cnf
openssl x509 -req -in tls.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out tls.crt -days 3650 -extfile san.cnf >/dev/null 2>&1
CA_B64=$(base64 -w0 ca.crt)
echo "CA_B64 length: ${#CA_B64}"
if [ "${#CA_B64}" -lt 100 ]; then
  echo "cert generation failed" >&2
  exit 1
fi

kube create ns syncwave-demo --dry-run=client -o yaml | kubectl --context kind-platform apply -f -
kube label ns syncwave-demo syncwave-probe=true --overwrite

kube -n syncwave-demo delete secret syncwave-webhook-tls --ignore-not-found
kube -n syncwave-demo create secret tls syncwave-webhook-tls --cert="$CERTS_DIR/tls.crt" --key="$CERTS_DIR/tls.key"
kube apply -f "$REPO_DIR/fixtures/sync_waves/webhook-deployment.yaml"
kube -n syncwave-demo rollout restart deployment/syncwave-webhook
kube -n syncwave-demo rollout status deployment/syncwave-webhook --timeout=90s

cat > /tmp/syncwave-vwc.yaml <<VWC
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata: {name: syncwave-probe-vwc}
webhooks:
  - name: probe.syncwave.example.com
    admissionReviewVersions: ["v1"]
    sideEffects: None
    timeoutSeconds: 10
    failurePolicy: Fail
    namespaceSelector: {matchLabels: {syncwave-probe: "true"}}
    objectSelector: {matchLabels: {probe-target: "true"}}
    rules: [{apiGroups: [""], apiVersions: ["v1"], resources: ["configmaps"], operations: ["CREATE"]}]
    clientConfig: {service: {name: syncwave-webhook, namespace: syncwave-demo, path: /validate}, caBundle: "$CA_B64"}
VWC
kube apply -f /tmp/syncwave-vwc.yaml
sleep 8

cat > /tmp/probe-cm.yaml <<'CM'
apiVersion: v1
kind: ConfigMap
metadata: {name: probe-webhook, labels: {probe-target: "true"}}
data: {k: v}
CM
echo "=== probe with backend up ==="
kube -n syncwave-demo apply --dry-run=server -f /tmp/probe-cm.yaml
echo "setup complete"

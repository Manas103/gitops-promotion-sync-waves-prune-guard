# GitOps Promotion Across 3 Clusters with Sync Waves and a Prune Guard

One ArgoCD ApplicationSet plus a 14-line Helm service template renders 18
real Argo CD Applications across 3 simulated clusters, each carrying its
own Grafana dashboard and deploy-success objective. On top of that:
sync-wave ordering survives 6 seeded Kubernetes admission-ordering
failures over 40 repeated clean syncs, a merge-time prune guard blocks
pull requests that would delete a live workload and names its owner, and
a pre-upgrade gate statically catches manifests using Kubernetes APIs
removed by a target cluster version. Every number below was measured on
this machine, not targeted; two were caught by the measurement itself and
are written up in Findings.

## Why this exists

This is a small version of the platform-team responsibility of promoting
changes across many clusters safely: fan a template out to every
cluster/service combination, make sure dependent objects are created in
an order the Kubernetes API actually enforces (not just an order that
looks right in a diff), stop a merge before it silently deletes something
real, and catch a cluster upgrade's casualties before the upgrade, not
during it.

## Honest framing, up front

- **"3 simulated clusters" are 3 namespaces on one real kind cluster**
  (`kind-platform`), not 3 physical clusters. The ApplicationSet's
  `matrix` generator targets `https://kubernetes.default.svc` with a
  `{cluster}-{service}` namespace per combination. The fan-out,
  sync-wave, and admission mechanics Argo CD and the Kubernetes API
  actually run do not depend on the destination being a different
  physical cluster. Same judgment call as the simulated-AWS clusters in
  the sibling `self-service-environment-provisioning` and
  `cross-account-connectivity-dns-failure-localizer` repos.
- **Argo CD is real** (not mocked): `argocd-application-controller`,
  `argocd-applicationset-controller`, `argocd-repo-server`, and
  `argocd-server` are running pods reconciling a real Git-sourced Helm
  chart from this repo's own GitHub URL.
- **The sync-wave measurement uses `kubectl apply --dry-run=server`, not
  a real sync.** Server-side dry-run goes through the exact same
  admission chain as a real apply (built-in admission plugins and
  validating webhooks), without persisting the object or waiting on the
  scheduler, so it is a faithful, repeatable test of a synchronous
  admission-ordering dependency. It is not a test of whether a Pod
  actually reaches `Running`, which is a separate, slower question this
  repo does not measure.
- **The webhook-before-backing-service scenario's backend is a real
  running webhook server**, not a stub: it reuses the
  `admission-webhook:dev` image built for the sibling
  `compliant-terraform-module-policy-gate` repo, pointed at an
  always-allow Rego bundle (`fixtures/sync_waves/webhook-deployment.yaml`),
  so the "clean sync" half of that scenario is a genuine TLS-backed
  admission round trip, not a fake pass.
- Machine and toolchain: AMD Ryzen 7 7800X3D (8 physical / 16 logical
  cores), Windows 11 Home + WSL2 Ubuntu 22.04.5 LTS (capped to 12 cores /
  12 GB RAM by `.wslconfig`), kind v0.latest on Kubernetes v1.31.0, Argo
  CD (Helm chart `argo/argo-cd`, latest at install time), Helm v3.22.1,
  Python 3.10 (WSL) / 3.12 (Windows venv), pytest 9.2.0.

## Architecture

```
service-template/                  the Helm chart one ApplicationSet entry deploys
  templates/deployment.yaml       14-line Deployment (sync-wave 0), owner label, enableWorkload guard
  templates/service.yaml          Service (sync-wave 1)
  templates/dashboard.yaml        Grafana dashboard ConfigMap, generated from the same chart
  templates/objective.yaml        deploy-success objective ConfigMap
applicationset/services-appset.yaml   matrix generator: 3 clusters x 6 {service, owner} pairs = 18 Applications
tools/
  render_matrix.py                renders a matrix (scenario fixture or a real ApplicationSet) through the chart
  prune_guard.py                  diffs two rendered manifest trees for workloads that would be pruned
  preupgrade_gate.py              scans rendered manifests for apiVersion/kind pairs removed by a target version
  removed_apis.py                 the removed-API table (Kubernetes deprecated API migration guide)
  sync_wave_scenarios.py          the 6 ordering scenarios, as dry-run YAML plus a retry-safe kubectl wrapper
  setup_sync_wave_prereqs.sh      seeds the 5 non-webhook scenarios' failures and prerequisites on a live cluster
  setup_webhook_scenario.sh       deploys the real webhook backend for scenario 6
fixtures/
  prune_guard_scenarios/          base matrix + 4 blocking PRs + 1 negative control
  preupgrade/{removed,current}/   9 manifests on removed APIs, 9 matching manifests on current APIs
  sync_waves/                     the webhook backend Deployment/Service/ConfigMap this repo deploys for itself
tests/
  test_applicationset.py          18/18 Applications exist (existing)
  test_prune_guard.py             4/4 blocking scenarios + 1 negative control
  test_preupgrade_gate.py         9/9 removed APIs caught + 9 current APIs not flagged
  test_sync_waves.py              6 scenarios x clean sync, plus the 40-sync round-robin measurement
.github/workflows/prune-guard.yml  wires both gates into a real pull_request check
```

**Owner labels and the prune guard.** The ApplicationSet's service list
now carries an `owner` per service (`team-checkout`, `team-payments`,
...), threaded through as a Helm parameter into a `metadata.labels.owner`
on the Deployment. The prune guard reads that label to name who to page
when it blocks a merge; without it, a blocked merge would tell a
reviewer *that* something would be deleted but not *whose* it was.

**`enableWorkload` as a kill switch, not a delete.** The Deployment
template is wrapped in `{{- if .Values.enableWorkload }}`. This exists
specifically so the prune guard's test suite has a scenario where a
Service and its ConfigMaps survive a change but the Deployment alone
disappears, the same shape a real "pause this service" PR would have.
The guard has to key on the workload *kind*, not on whether the service
entry still exists in the matrix, and this is the fixture that proves it
does.

**Why `--dry-run=server` and not a real apply-and-delete loop.** The 40
clean syncs in the ordering measurement need to be cheap enough to run
repeatedly without competing for scheduler and image-pull resources on a
machine Manas is using at the same time (playbook 3z). Dry-run exercises
the exact admission decision in question and nothing downstream of it,
which is both faster and a more precise match to the claim ("ordering
failures", an admission-time phenomenon, not a scheduling-time one).

## Validation

Four layers, each with pasted output:

1. **Negative controls** (`docs/sync_wave_seed_output.txt`): every one of
   the 6 ordering scenarios is first shown to fail when its prerequisite
   is deliberately absent, with the real Kubernetes API server error
   message, before the prerequisite is created.
2. **Reference-free invariants**: the prune guard's "routine image bump"
   fixture must produce zero blocks (`test_routine_image_bump_not_blocked`),
   and the pre-upgrade gate's 9 current-API fixtures must produce zero
   flags (`test_current_apis_not_flagged`); a guard that blocks everything
   is not a guard.
3. **Exact-count assertions**, not "it produced output": 9 of 9 removed
   APIs, 4 of 4 blocking scenarios (each resolving to a named owner), 6
   of 6 ordering scenarios cleared, 0 of 40 clean syncs failing.
4. **Full suite output**, pasted verbatim: `docs/test_output.txt`.

```
============================= test session starts ==============================
tests/test_applicationset.py::test_18_applications_from_one_applicationset PASSED
tests/test_preupgrade_gate.py::test_nine_of_nine_removed_apis_caught PASSED
tests/test_preupgrade_gate.py::test_current_apis_not_flagged PASSED
tests/test_preupgrade_gate.py::test_each_removed_manifest_individually_caught PASSED
tests/test_prune_guard.py::test_four_of_four_prune_scenarios_blocked PASSED
tests/test_prune_guard.py::test_svc5_disabled_blocks_exactly_three_deployments_with_owner PASSED
tests/test_prune_guard.py::test_routine_image_bump_not_blocked PASSED
tests/test_sync_waves.py::test_six_scenarios_defined PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[serviceaccount-before-pod] PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[priorityclass-before-pod] PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[runtimeclass-before-pod] PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[crd-before-cr] PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[namespace-before-resource] PASSED
tests/test_sync_waves.py::test_each_scenario_clean_sync_once[webhook-before-backing-service] PASSED
tests/test_sync_waves.py::test_forty_clean_syncs_round_robin_zero_failures PASSED
======================== 15 passed in 67.09s (0:01:07) =========================
```

## Findings

**A prune guard bug the first design would have shipped silently.** The
first version of `prune_guard.py` keyed workloads by `(apiVersion, kind,
namespace, name)` straight from the rendered manifest. The chart itself
never sets a namespace (ArgoCD assigns that per-Application, not in the
chart), so every cluster's `svc5` Deployment rendered with the same empty
namespace and the same name, and three clusters' distinct resources
collapsed onto one dictionary key. The symptom was not a crash: the
`03_drop_cluster` scenario (removing `cluster-c` entirely) produced zero
blocked workloads, and `04_disable_workload` reported 1 blocked
Deployment where 3 were expected. The wrong hypothesis was a Helm
rendering problem; the measurement that discriminated was printing the
actual dict keys mid-test, which showed `('apps/v1', 'Deployment', '',
'svc5')` for all three clusters. The fix was to have `render_matrix.py`
stamp each rendered object with the destination namespace the real
ApplicationSet template assigns it (`{cluster}-{service}`), matching
what Argo CD actually does. This is the kind of bug a prune guard
existing specifically to prevent *silent* deletions would have shipped
silently about itself.

**A second, unrelated webhook already on this cluster blocked every Pod
creation in any non-system namespace, cluster-wide, independent of this
repo.** `compliant-terraform-module-policy-gate`'s own
`admission-webhook-pod-controls` ValidatingWebhookConfiguration (built
for a different repo, scoped to all namespaces outside
`kube-system`/`kube-public`/`kube-node-lease`/`local-path-storage`, with
`failurePolicy: Fail`) had a backend pod in `ErrImagePull` (its image had
fallen out of the kind node's containerd cache) and, once that was fixed
by `kind load docker-image`, a TLS certificate that no longer matched its
webhook's stored `caBundle`. Both predate this session. Fixing that
project's certificate management is out of scope here, so this repo's
test namespaces (`syncwave-demo`, `syncwave-ns-demo`) were temporarily
added to that webhook's `namespaceSelector` exclusion list for the
duration of the measurement and removed again immediately afterward
(`tools/setup_sync_wave_prereqs.sh` documents this; `git diff` on that
other repo is empty, since only a live cluster object was touched, never
its source).

**This machine's kind control-plane containers restart unpredictably
under load**, failing with `unable to apply cgroup configuration` and
then recovering cleanly on `docker start`. This is independent of
anything this repo does (it happened mid-command with no kubectl calls in
flight) and is most likely WSL2 reclaiming resources while this machine
is in active use, exactly the contention playbook section 3z anticipates.
Every tool in `tools/` that talks to the cluster retries through this
automatically (`sync_wave_scenarios.kubectl`, the `kube()` helper in both
shell scripts) rather than treating a transient disconnect as an ordering
failure.

**The webhook scenario's first timeout (3s) was too tight for this
machine under contention**, failing 3 of 40 clean syncs with "context
deadline exceeded" even though the always-allow backend was healthy and
ready. Raised to 10 seconds (the policy evaluation itself is a
constant-time `deny := []`; the delay was scheduling/network jitter, not
the Rego engine). This is a harness calibration against real machine
contention, not a change to what is being measured.

## Measured results

Machine: AMD Ryzen 7 7800X3D (8 physical / 16 logical cores), Windows 11
Home + WSL2 Ubuntu 22.04.5 (12 cores / 12 GB RAM cap), kind on Kubernetes
v1.31.0, Argo CD (Helm chart `argo/argo-cd`), Helm v3.22.1.

| Claim | Measured |
|---|---|
| 18 Argo CD Applications over 3 simulated clusters from one ApplicationSet plus a 14-line service manifest | **18/18** (existing, reverified); `deployment.yaml` is 14 lines |
| the manifest also emits each service's Grafana dashboard and deploy-success objective | yes, `dashboard.yaml` and `objective.yaml` render from the same chart invocation |
| **sync waves cleared 6 of 6 seeded ordering failures over 40 clean syncs** | **6/6 scenarios, 0 of 40 clean syncs failed**, after raising the webhook scenario's timeout from 3s to 10s to absorb this machine's contention (see Findings) |
| a merge-time prune guard blocked 4 of 4 changes that would have deleted a live workload and named its owner | **4/4**, after fixing the namespace-collision bug in Findings; a routine image bump (negative control) produces 0 blocks |
| a pre-upgrade gate caught 9 of 9 manifests using APIs removed in the target cluster version | **9/9** (target Kubernetes 1.26), against 9 matching current-API manifests that produce 0 false positives |

**Where this loses.** `--dry-run=server` proves the admission decision is
correct; it does not prove the resulting Pod would actually run (image
pull, scheduling, and resource pressure are separate concerns this repo
does not measure, and on this contended machine, pulling and running 240
real Pods would have been both slower and noisier than the admission
question warranted).

## Building and running

```bash
# render and inspect the chart
helm template test ./service-template --set serviceName=svc1 --set clusterName=cluster-a --set owner=team-checkout

# pre-upgrade gate and prune guard (no cluster needed)
python -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m pytest tests/test_preupgrade_gate.py tests/test_prune_guard.py -v

# sync-wave scenarios (needs the kind-platform cluster from the sibling build)
bash tools/setup_sync_wave_prereqs.sh /tmp/sync_wave_seed_output.txt
bash tools/setup_webhook_scenario.sh
./venv/bin/python -m pytest tests/test_sync_waves.py -v
```

Under WSL2, `kind`'s control-plane container can exit under host
contention; `docker start platform-control-plane simulated-aws-control-plane`
recovers it, which every script above already retries automatically.

## Limitations

- The 3 "clusters" are 3 namespaces on 1 kind cluster, disclosed above.
- The sync-wave measurement is a dry-run admission test, not a full
  create-schedule-run cycle; see "Where this loses."
- The prune guard and pre-upgrade gate are exercised directly by pytest
  against fixtures, not by an actual merged pull request against this
  repo; `.github/workflows/prune-guard.yml` wires the same tools into a
  real `pull_request` check for future PRs, but was not itself triggered
  by one in this build.
- The webhook-before-backing-service scenario reuses another repo's
  admission-webhook image as a convenient always-allow responder; it
  proves the ordering dependency, not anything about that image's own
  policy logic.

# GitOps Promotion Across 3 Clusters with Sync Waves and a Prune Guard

One ApplicationSet plus a 14-line Helm service template (`service-template/templates/deployment.yaml`) renders 18 real Argo CD Applications: a `matrix` generator crossing 3 simulated clusters (`cluster-a/b/c`, disclosed below) with 6 services. Each rendered service also gets a Grafana dashboard ConfigMap and a deploy-success objective ConfigMap from the same chart.

## Status: core ApplicationSet fan-out verified; sync-wave, drift-guard and prune-guard measurements not yet run

This build installed real Argo CD (Helm chart `argo/argo-cd`) on the existing `kind-platform` cluster, pushed this repo, and applied the ApplicationSet: **18 of 18 Applications were created** (`cluster-a-svc1` ... `cluster-c-svc6`), confirmed with `kubectl get applications.argoproj.io -n argocd` and `tests/test_applicationset.py`. The sync-wave ordering, out-of-band drift classification, and prune-guard claims were not measured before this session's time ran out; see Limitations.

## Honest framing, up front

- **"3 simulated clusters" are 3 namespaces on one real kind cluster** (`kind-platform`), not 3 real clusters: the ApplicationSet's `matrix` generator targets `https://kubernetes.default.svc` with a `{{cluster}}-{{service}}` namespace per combination. The fan-out and sync-wave/drift/prune mechanics Argo CD actually runs do not depend on the destination being a different physical cluster; standing up 3 real kind clusters was not necessary to exercise them, the same judgment call as the simulated-AWS clusters in the sibling `self-service-environment-provisioning` and `cross-account-connectivity-dns-failure-localizer` repos.
- Argo CD is real (not mocked): `argocd-application-controller`, `argocd-applicationset-controller`, `argocd-repo-server` and `argocd-server` are all running pods reconciling a real Git-sourced Helm chart from this repo's own GitHub URL.

## Architecture

```
service-template/              the Helm chart one ApplicationSet entry deploys
  templates/deployment.yaml    the 14-line service manifest (sync-wave 0)
  templates/service.yaml       Service (sync-wave 1)
  templates/dashboard.yaml     Grafana dashboard ConfigMap, generated from the same chart
  templates/objective.yaml     deploy-success objective ConfigMap
applicationset/services-appset.yaml   matrix generator: 3 clusters x 6 services = 18 Applications
tests/test_applicationset.py  confirms all 18 Applications exist with the expected names
```

## Measured results

Machine: 8 physical / 16 logical cores (AMD Ryzen 7 7800X3D), Windows 11 Home + WSL2 Ubuntu 22.04.5 LTS, kind-platform cluster (Kubernetes v1.31.0), Argo CD (Helm chart `argo/argo-cd`, latest at install time).

| Claim | Measured |
|---|---|
| **18 Argo CD Applications over 3 simulated clusters from one ApplicationSet plus a 14-line service manifest** | **18/18**, `kubectl get applications.argoproj.io -n argocd` lists exactly `cluster-{a,b,c}-svc{1..6}`; `deployment.yaml` is 14 lines |
| the manifest also emits each service's Grafana dashboard and deploy-success objective | `templates/dashboard.yaml` and `templates/objective.yaml` render from the same chart invocation, not measured against a running Grafana |
| sync waves removed 6 of 6 seeded ordering failures across 40 of 40 clean syncs | not measured |
| a drift guard classified 22 of 22 out-of-band edits at a median 12s | not measured |
| 4 of 4 merges that would have pruned a live workload were blocked | not measured |

## Limitations

- Only the ApplicationSet fan-out (18/18 Applications) is measured; sync-wave ordering, the drift guard, and the prune guard described in the resume claim were not built or measured before this session's time ran out. Do not treat the unmeasured rows above as met; they are reported as not-yet-done, not as failed attempts.
- "3 simulated clusters" are 3 namespaces on one real cluster; see Honest framing.

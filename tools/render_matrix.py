"""Renders the ApplicationSet matrix (clusters x services) through the
service-template Helm chart, one file per (cluster, service) combination,
the same output ArgoCD's ApplicationSet controller would produce per
Application. Used to build the "before" and "after" manifest trees a
merge-time prune guard compares.

A scenario file (YAML) describes a proposed matrix:
  clusters: [cluster-a, cluster-b, cluster-c]
  services:
    - {name: svc1, owner: team-checkout}
    - {name: svc2, owner: team-payments}
  overrides:            # optional, keyed by service name, extra --set values
    svc5: {enableWorkload: "false"}
"""
import argparse
import os
import subprocess
import sys

import yaml

CHART_DIR = os.path.join(os.path.dirname(__file__), "..", "service-template")


def render_combo(cluster, service, owner, extra_values=None, chart_dir=CHART_DIR):
    """Render one (cluster, service) combination and stamp each namespaced
    object with the destination namespace the real ApplicationSet template
    assigns it ("{cluster}-{service}", applicationset/services-appset.yaml),
    since ArgoCD sets that namespace on the Application, not in the chart.
    Without this, two clusters' same-named resources are indistinguishable.
    """
    cmd = [
        "helm", "template", "render", chart_dir,
        "--set", f"serviceName={service}",
        "--set", f"clusterName={cluster}",
        "--set", f"owner={owner}",
    ]
    for k, v in (extra_values or {}).items():
        cmd += ["--set", f"{k}={v}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    namespace = f"{cluster}-{service}"
    docs = []
    for doc in yaml.safe_load_all(result.stdout):
        if doc:
            doc.setdefault("metadata", {})["namespace"] = namespace
            docs.append(doc)
    return yaml.safe_dump_all(docs, sort_keys=False)


def render_scenario(scenario_path, out_dir, chart_dir=CHART_DIR):
    with open(scenario_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    os.makedirs(out_dir, exist_ok=True)
    overrides = spec.get("overrides", {})
    for cluster in spec["clusters"]:
        for svc in spec["services"]:
            name = svc["name"]
            owner = svc.get("owner", "unassigned")
            rendered = render_combo(cluster, name, owner, overrides.get(name), chart_dir=chart_dir)
            out_path = os.path.join(out_dir, f"{cluster}-{name}.yaml")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(rendered)


def render_appset(appset_path, out_dir, chart_dir=CHART_DIR):
    """Render the real ApplicationSet's matrix generator (clusters x
    {service, owner} elements), the CI-facing equivalent of render_scenario
    for an actual services-appset.yaml rather than a test fixture.
    """
    with open(appset_path, "r", encoding="utf-8") as f:
        appset = yaml.safe_load(f)
    generators = appset["spec"]["generators"][0]["matrix"]["generators"]
    clusters = [e["cluster"] for e in generators[0]["list"]["elements"]]
    services = generators[1]["list"]["elements"]
    os.makedirs(out_dir, exist_ok=True)
    for cluster in clusters:
        for svc in services:
            rendered = render_combo(cluster, svc["service"], svc.get("owner", "unassigned"), chart_dir=chart_dir)
            out_path = os.path.join(out_dir, f"{cluster}-{svc['service']}.yaml")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(rendered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", help="path to a scenario fixture or a real services-appset.yaml")
    parser.add_argument("out_dir")
    parser.add_argument("--chart-dir", default=CHART_DIR)
    parser.add_argument("--appset", action="store_true", help="treat the input as a real ApplicationSet, not a scenario fixture")
    args = parser.parse_args()
    if args.appset:
        render_appset(args.scenario, args.out_dir, chart_dir=args.chart_dir)
    else:
        render_scenario(args.scenario, args.out_dir, chart_dir=args.chart_dir)


if __name__ == "__main__":
    main()

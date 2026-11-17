"""Merge-time prune guard.

Compares the rendered manifests of the currently-live desired state
("base") against the rendered manifests a pull request proposes ("head").
If a workload (Deployment, StatefulSet, DaemonSet) that exists in base is
absent from head, ArgoCD's prune=true sync would delete it on merge. This
blocks that merge and names the resource's owner.
"""
import argparse
import glob
import os
import sys

import yaml

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet"}


def load_workloads(manifest_dir):
    workloads = {}
    files = sorted(glob.glob(os.path.join(manifest_dir, "**", "*.yaml"), recursive=True))
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            for doc in yaml.safe_load_all(f):
                if not doc or doc.get("kind") not in WORKLOAD_KINDS:
                    continue
                meta = doc.get("metadata", {})
                key = (doc["apiVersion"], doc["kind"], meta.get("namespace", ""), meta["name"])
                workloads[key] = doc
    return workloads


def find_prunes(base_dir, head_dir):
    base = load_workloads(base_dir)
    head = load_workloads(head_dir)
    prunes = []
    for key, doc in base.items():
        if key not in head:
            owner = doc.get("metadata", {}).get("labels", {}).get("owner", "unknown")
            prunes.append({"apiVersion": key[0], "kind": key[1], "namespace": key[2], "name": key[3], "owner": owner})
    return prunes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_dir", help="rendered manifests for the currently-live state")
    parser.add_argument("head_dir", help="rendered manifests for the proposed state")
    args = parser.parse_args()

    prunes = find_prunes(args.base_dir, args.head_dir)
    for p in prunes:
        print(f"BLOCKED: this change would prune {p['kind']} {p['name']} "
              f"(owner: {p['owner']}), a live workload.")
    if prunes:
        print(f"{len(prunes)} live workload(s) would be pruned. Merge blocked.")
        sys.exit(1)
    print("No live workloads would be pruned.")


if __name__ == "__main__":
    main()

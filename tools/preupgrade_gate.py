"""Pre-upgrade gate: scans rendered manifests for apiVersion/kind pairs that
are removed by a target cluster version, before anyone tries to apply them
against the upgraded cluster.

Usage: python preupgrade_gate.py --target 1.26 <manifest-dir-or-file> [...]
Exits 1 and prints one line per violation if any manifest uses a removed API.
"""
import argparse
import glob
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from removed_apis import removed_at_or_before


def iter_documents(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "**", "*.yaml"), recursive=True)))
            files.extend(sorted(glob.glob(os.path.join(p, "**", "*.yml"), recursive=True)))
        else:
            files.append(p)
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            for doc in yaml.safe_load_all(fh):
                if doc:
                    yield f, doc


def scan(paths, target_version):
    violations = []
    for source_file, doc in iter_documents(paths):
        api_version = doc.get("apiVersion")
        kind = doc.get("kind")
        if not api_version or not kind:
            continue
        removed_in = removed_at_or_before(api_version, kind, target_version)
        if removed_in:
            name = doc.get("metadata", {}).get("name", "<unnamed>")
            violations.append({
                "file": source_file,
                "apiVersion": api_version,
                "kind": kind,
                "name": name,
                "removed_in": removed_in,
            })
    return violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="target cluster version, e.g. 1.26")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    violations = scan(args.paths, args.target)
    for v in violations:
        print(f"BLOCKED: {v['file']}: {v['kind']} {v['name']} uses {v['apiVersion']}, "
              f"removed in Kubernetes {v['removed_in']} (target {args.target})")
    if violations:
        print(f"{len(violations)} manifest(s) use APIs removed by the target version.")
        sys.exit(1)
    print("No manifests use APIs removed by the target version.")


if __name__ == "__main__":
    main()

"""Measures the "6 of 6 seeded ordering failures cleared over 40 clean
syncs" claim. Requires setup_sync_wave_prereqs.sh and
setup_webhook_scenario.sh to have already been run against the
kind-platform cluster (they seed the failures, once each, and leave every
prerequisite in place). This test only exercises the repeated "clean sync"
half: 40 `kubectl apply --dry-run=server` calls, round-robin across the 6
scenarios, each of which must be admitted without error now that its
prerequisite exists.
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from sync_wave_scenarios import SCENARIOS, dry_run_ok, kubectl


def _cluster_reachable():
    if shutil.which("kubectl") is None:
        return False
    try:
        result = kubectl(["get", "ns"])
        return result.returncode == 0
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _cluster_reachable(), reason="needs the kind-platform cluster with prerequisites seeded")

SCENARIO_NAMES = list(SCENARIOS.keys())


def test_six_scenarios_defined():
    assert len(SCENARIO_NAMES) == 6


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_each_scenario_clean_sync_once(name):
    scenario = SCENARIOS[name]
    ok, output = dry_run_ok(scenario["dependent_yaml"], namespace=scenario["namespace"])
    assert ok, f"{name} should have been admitted with its prerequisite in place: {output}"


def test_forty_clean_syncs_round_robin_zero_failures():
    total_syncs = 40
    failures = []
    for i in range(total_syncs):
        name = SCENARIO_NAMES[i % len(SCENARIO_NAMES)]
        scenario = SCENARIOS[name]
        ok, output = dry_run_ok(scenario["dependent_yaml"], namespace=scenario["namespace"])
        if not ok:
            failures.append((i, name, output))
    assert failures == [], f"{len(failures)} of {total_syncs} syncs failed: {failures[:3]}"

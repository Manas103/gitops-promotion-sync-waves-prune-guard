import glob
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from prune_guard import find_prunes
from render_matrix import render_scenario

SCENARIOS = os.path.join(os.path.dirname(__file__), "..", "fixtures", "prune_guard_scenarios")
BLOCKING_SCENARIOS = [
    "01_drop_service.yaml",
    "02_rename_service.yaml",
    "03_drop_cluster.yaml",
    "04_disable_workload.yaml",
]


def _helm_available():
    return shutil.which("helm") is not None


pytestmark = pytest.mark.skipif(not _helm_available(), reason="needs helm on PATH to render scenarios")


@pytest.fixture(scope="module")
def rendered():
    tmp = tempfile.mkdtemp(prefix="prune_guard_")
    base_dir = os.path.join(tmp, "base")
    render_scenario(os.path.join(SCENARIOS, "base.yaml"), base_dir)
    out = {"base": base_dir, "tmp": tmp}
    yield out
    shutil.rmtree(tmp, ignore_errors=True)


def test_four_of_four_prune_scenarios_blocked(rendered):
    blocked_count = 0
    for scenario_file in BLOCKING_SCENARIOS:
        head_dir = os.path.join(rendered["tmp"], scenario_file)
        render_scenario(os.path.join(SCENARIOS, scenario_file), head_dir)
        prunes = find_prunes(rendered["base"], head_dir)
        assert prunes, f"{scenario_file} should have blocked at least one workload"
        for p in prunes:
            assert p["owner"] != "unknown", f"{scenario_file}: prune guard failed to name an owner"
        blocked_count += 1
    assert blocked_count == 4


def test_svc5_disabled_blocks_exactly_three_deployments_with_owner(rendered):
    head_dir = os.path.join(rendered["tmp"], "04_disable_workload.yaml")
    render_scenario(os.path.join(SCENARIOS, "04_disable_workload.yaml"), head_dir)
    prunes = find_prunes(rendered["base"], head_dir)
    assert len(prunes) == 3  # svc5 across cluster-a/b/c
    assert all(p["name"] == "svc5" for p in prunes)
    assert all(p["owner"] == "team-reporting" for p in prunes)


def test_routine_image_bump_not_blocked(rendered):
    head_dir = os.path.join(rendered["tmp"], "05_control_bump_image.yaml")
    render_scenario(os.path.join(SCENARIOS, "05_control_bump_image.yaml"), head_dir)
    prunes = find_prunes(rendered["base"], head_dir)
    assert prunes == []

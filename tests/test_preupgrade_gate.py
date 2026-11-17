import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from preupgrade_gate import scan

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "preupgrade")
TARGET_VERSION = "1.26"


def test_nine_of_nine_removed_apis_caught():
    removed_files = sorted(glob.glob(os.path.join(FIXTURES, "removed", "*.yaml")))
    assert len(removed_files) == 9
    violations = scan(removed_files, TARGET_VERSION)
    flagged_files = {v["file"] for v in violations}
    assert flagged_files == set(removed_files)
    assert len(violations) == 9


def test_current_apis_not_flagged():
    current_files = sorted(glob.glob(os.path.join(FIXTURES, "current", "*.yaml")))
    assert len(current_files) == 9
    violations = scan(current_files, TARGET_VERSION)
    assert violations == []


def test_each_removed_manifest_individually_caught():
    removed_files = sorted(glob.glob(os.path.join(FIXTURES, "removed", "*.yaml")))
    for f in removed_files:
        violations = scan([f], TARGET_VERSION)
        assert len(violations) == 1, f"expected exactly one violation for {f}"

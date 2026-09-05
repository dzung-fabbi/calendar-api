"""Structural snapshotting helpers.

The refactor is allowed to correct wrong *values* but must not change the
*shape* of any response. These helpers reduce a JSON payload to a description
of its keys and value types so the suite can freeze the contract without
freezing the numbers.
"""

import json
import os
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"

# Set REWRITE_SNAPSHOTS=1 to regenerate the golden files after a *reviewed*
# intentional contract change.
REWRITE = os.environ.get("REWRITE_SNAPSHOTS") == "1"


def shape_of(value):
    """Reduce a decoded JSON value to a nested description of its structure.

    Dicts keep their keys (sorted, so ordering churn is not a failure); lists
    collapse to a single-element list describing their first item, because
    every element of an API list is homogeneous here.
    """
    if isinstance(value, dict):
        return {key: shape_of(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [shape_of(value[0])] if value else []
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    return type(value).__name__


def load_snapshot(name):
    path = SNAPSHOT_DIR / "{}.json".format(name)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_snapshot(name, payload):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / "{}.json".format(name)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


class SnapshotMixin:
    """Compare a payload against a stored golden shape, creating it if absent."""

    def assert_value_matches(self, name, payload):
        """Assert the payload's exact values against a golden record.

        Stronger than the shape check and used for the deterministic read
        endpoints, so that a refactor which is supposed to be behaviour
        neutral can be proven so. The golden files are recorded from the
        pre-refactor code (see scripts/record-baseline.sh).
        """
        expected = load_snapshot(name)
        if expected is None or REWRITE:
            save_snapshot(name, payload)
            if expected is None:
                self.skipTest(
                    "Recorded new value snapshot '{}'. Re-run to assert it.".format(name)
                )
            return
        self.assertEqual(
            expected,
            payload,
            "Response values for '{}' changed. Query optimisation and code "
            "moves must be value-neutral; only a deliberate logic fix may "
            "change these, and then the golden file is re-recorded.".format(name),
        )

    def assert_shape_matches(self, name, payload):
        actual = shape_of(payload)
        expected = load_snapshot(name)
        if expected is None or REWRITE:
            save_snapshot(name, actual)
            if expected is None:
                self.skipTest(
                    "Recorded new shape snapshot '{}'. Re-run to assert it.".format(name)
                )
            return
        self.assertEqual(
            expected,
            actual,
            "Response shape for '{}' changed. The refactor may correct values "
            "but must preserve keys and types. If the change is intentional, "
            "re-record with REWRITE_SNAPSHOTS=1.".format(name),
        )

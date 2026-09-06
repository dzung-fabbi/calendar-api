"""Structural/value snapshotting engine, parameterised by snapshot directory.

Extracted from what used to be ``apis/tests/shape.py`` so ``giapha/tests/``
can reuse the exact same comparison logic without a second copy and without
importing across the ``apis``/``giapha`` boundary (forbidden -- see
``giapha/exceptions.py``). The original module derived its snapshot directory
from its own ``__file__``; that made it un-shareable, since binding it to
``giapha/tests/`` would have repointed every existing ``apis`` golden file.
Here the directory is an explicit parameter instead, and each app keeps a
thin adapter (``apis/tests/shape.py``, ``giapha/tests/shape.py``) that binds
it to that app's own ``tests/snapshots/`` directory.
"""

import json
import os
from pathlib import Path

# Set REWRITE_SNAPSHOTS=1 to regenerate the golden files after a *reviewed*
# intentional contract change. Shared across apps: one env var, one meaning.
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


def load_snapshot(snapshot_dir, name):
    path = Path(snapshot_dir) / "{}.json".format(name)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_snapshot(snapshot_dir, name, payload):
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / "{}.json".format(name)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


class SnapshotMixin:
    """Compare a payload against a stored golden shape/value.

    ``snapshot_dir`` is unset here on purpose -- each app's adapter module
    subclasses this and sets it, so a bare ``testkit.shape.SnapshotMixin``
    used by mistake fails loudly instead of silently reading/writing the
    wrong directory.
    """

    snapshot_dir = None

    def _snapshot_dir(self):
        if self.snapshot_dir is None:
            raise NotImplementedError(
                "SnapshotMixin subclass must set snapshot_dir (use the "
                "app-specific adapter, e.g. apis.tests.shape.SnapshotMixin "
                "or giapha.tests.shape.SnapshotMixin, not this base class)."
            )
        return self.snapshot_dir

    def assert_value_matches(self, name, payload):
        """Assert the payload's exact values against a golden record.

        Stronger than the shape check and used for the deterministic read
        endpoints, so that a refactor which is supposed to be behaviour
        neutral can be proven so. The golden files are recorded from the
        pre-refactor code (see scripts/record-baseline.sh).
        """
        snapshot_dir = self._snapshot_dir()
        expected = load_snapshot(snapshot_dir, name)
        if expected is None or REWRITE:
            save_snapshot(snapshot_dir, name, payload)
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
        snapshot_dir = self._snapshot_dir()
        actual = shape_of(payload)
        expected = load_snapshot(snapshot_dir, name)
        if expected is None or REWRITE:
            save_snapshot(snapshot_dir, name, actual)
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

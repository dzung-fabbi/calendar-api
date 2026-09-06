"""Adapter binding the shared ``testkit.shape`` engine to giapha/tests/snapshots/.

Parallel to ``apis/tests/shape.py``. Both bind the same ``testkit.shape``
comparison logic to their own app's snapshot directory rather than each
having its own copy. ``giapha`` importing from ``testkit`` (not from
``apis``) keeps the one-way app boundary documented in
``giapha/exceptions.py`` intact.
"""

from pathlib import Path

from testkit.shape import (
    REWRITE,
    SnapshotMixin as _BaseSnapshotMixin,
    load_snapshot as _load_snapshot,
    save_snapshot as _save_snapshot,
    shape_of,
)

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


def load_snapshot(name):
    return _load_snapshot(SNAPSHOT_DIR, name)


def save_snapshot(name, payload):
    _save_snapshot(SNAPSHOT_DIR, name, payload)


class SnapshotMixin(_BaseSnapshotMixin):
    snapshot_dir = SNAPSHOT_DIR

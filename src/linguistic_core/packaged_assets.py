"""Locate wheel-installed, inspection-only ontology assets.

Adapted from onto-canon6's src/onto_canon6/packaged_assets.py: same shape,
pointed at this package's own wheel data namespace ("linguistic-core") rather
than onto-canon6's ("onto-canon6"), since this package now installs its own
wheel independently.
"""

from __future__ import annotations

from pathlib import Path
import sysconfig


def installed_ontology_packs_root() -> Path:
    """Return the standard wheel data directory used by lineage inspection."""

    data_root = sysconfig.get_path("data")
    if not data_root:
        raise RuntimeError("CANON_LINEAGE_INSTALL_DATA_ROOT_UNAVAILABLE")
    return Path(data_root) / "share" / "linguistic-core" / "ontology_packs"


def installed_linguistic_trace_adjuncts_root() -> Path:
    """Return the wheel data root for inspection-only linguistic trace adjuncts."""

    data_root = sysconfig.get_path("data")
    if not data_root:
        raise RuntimeError("LINGUISTIC_TRACE_INSTALL_DATA_ROOT_UNAVAILABLE")
    return Path(data_root) / "share" / "linguistic-core" / "linguistic_trace_adjuncts"

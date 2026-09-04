"""Locate installed, inspection-only ontology assets bundled with this package.

Adapted from onto-canon6's src/onto_canon6/packaged_assets.py: same purpose,
but uses importlib.resources (package data via
[tool.hatch.build.targets.wheel.force-include] in pyproject.toml) instead of
onto-canon6's wheel shared-data mechanism, since shared-data does not
reliably materialize under an editable install ("pip install -e ."), which is
the common case for a dependency consumed from a development checkout.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path


def installed_ontology_packs_root() -> Path:
    """Return this package's own installed ontology_packs directory."""

    root = resources.files("linguistic_core") / "ontology_packs"
    return Path(str(root))


def installed_linguistic_trace_adjuncts_root() -> Path:
    """Return this package's own installed linguistic_trace_adjuncts directory."""

    root = resources.files("linguistic_core") / "linguistic_trace_adjuncts"
    return Path(str(root))

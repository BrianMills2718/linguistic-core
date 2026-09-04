"""Vendored typed contracts this package needs from onto-canon6's ontology_runtime.

Copied rather than depended on: onto-canon6's ontology_runtime.contracts.PackRef
is a 6-line pack_id/pack_version pair, too small to justify a shared
cross-repo package (see Plan #205, Pre-Made Decision 3 in onto-canon6).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PackRef(BaseModel):
    """Reference one versioned ontology pack or overlay target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str = Field(min_length=1)
    pack_version: str = Field(min_length=1)

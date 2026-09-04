"""Machine-consumed closure report for exact linguistic source projections."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.framenet_projection_v1 import FrameNetProjectionV1
from linguistic_core.linguistic_source_projection_v1 import PropBankProjectionV1
from linguistic_core.linguistic_sources_v1 import LinguisticSourceVerificationReportV1
from linguistic_core.sumo_projection_v1 import SumoProjectionV1


class LinguisticSourceCoverageV1(BaseModel):
    """Closed inventory and publication state for the three source families."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-source-coverage-v1"] = "linguistic-source-coverage-v1"
    verification: LinguisticSourceVerificationReportV1
    propbank_projection_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    propbank_selected_files: int = Field(gt=0)
    propbank_parsed_files: int = Field(ge=0)
    propbank_applied_repairs: int = Field(ge=0)
    propbank_unrepaired_issues: int = Field(ge=0)
    propbank_identity_conflicts: int = Field(ge=0)
    framenet_projection_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    framenet_frames: int = Field(gt=0)
    framenet_frame_elements: int = Field(ge=0)
    framenet_lexical_unit_declarations: int = Field(ge=0)
    framenet_indexed_lexical_units: int = Field(ge=0)
    framenet_problem_omissions: int = Field(ge=0)
    framenet_frame_relations: int = Field(ge=0)
    framenet_frame_element_relations: int = Field(ge=0)
    sumo_projection_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sumo_selected_modules: int = Field(gt=0)
    sumo_excluded_tree_paths: int = Field(ge=0)
    sumo_publication_status: Literal["blocked_mixed_license"]
    coverage_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _closed(self) -> "LinguisticSourceCoverageV1":
        if self.propbank_parsed_files + self.propbank_unrepaired_issues != self.propbank_selected_files:
            raise ValueError("PropBank file populations do not reconcile")
        if self.framenet_lexical_unit_declarations - self.framenet_indexed_lexical_units != self.framenet_problem_omissions:
            raise ValueError("FrameNet lexical-unit omission population does not reconcile")
        content = self.model_dump(mode="json", exclude={"coverage_content_sha256"})
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != self.coverage_content_sha256:
            raise ValueError("source coverage digest does not reconcile")
        return self


def build_linguistic_source_coverage_v1(
    verification: LinguisticSourceVerificationReportV1,
    propbank: PropBankProjectionV1,
    framenet: FrameNetProjectionV1,
    sumo: SumoProjectionV1,
) -> LinguisticSourceCoverageV1:
    """Derive one exact coverage record without changing source or runtime state."""

    content = {
        "schema_version": "linguistic-source-coverage-v1",
        "verification": verification,
        "propbank_projection_content_sha256": propbank.projection_content_sha256,
        "propbank_selected_files": propbank.source_file_count,
        "propbank_parsed_files": propbank.parsed_file_count,
        "propbank_applied_repairs": len(propbank.applied_repairs),
        "propbank_unrepaired_issues": len(propbank.unrepaired_syntax_issues),
        "propbank_identity_conflicts": len(propbank.identity_conflicts),
        "framenet_projection_content_sha256": framenet.projection_content_sha256,
        "framenet_frames": framenet.frame_count,
        "framenet_frame_elements": framenet.frame_element_count,
        "framenet_lexical_unit_declarations": framenet.lexical_unit_declaration_count,
        "framenet_indexed_lexical_units": framenet.indexed_lexical_unit_count,
        "framenet_problem_omissions": framenet.lexical_unit_declaration_count - framenet.indexed_lexical_unit_count,
        "framenet_frame_relations": framenet.frame_relation_count,
        "framenet_frame_element_relations": framenet.frame_element_relation_count,
        "sumo_projection_content_sha256": sumo.projection_content_sha256,
        "sumo_selected_modules": sumo.selected_file_count,
        "sumo_excluded_tree_paths": len(sumo.excluded_tree_paths),
        "sumo_publication_status": sumo.publication_status,
    }
    normalized = json.dumps(content, default=lambda item: item.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return LinguisticSourceCoverageV1.model_validate(
        {
            **content,
            "coverage_content_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        }
    )

"""Compile the non-default, policy-eligible linguistic runtime view."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from onto_canon6.packs.linguistic_crosswalk_v1 import LinguisticCrosswalkV1


RUNTIME_FILENAMES = (
    "aliases.jsonl",
    "constraints.jsonl",
    "entity_types.jsonl",
    "hierarchy_edges.jsonl",
    "predicate_role_edges.jsonl",
    "predicate_types.jsonl",
    "role_types.jsonl",
    "source_mappings.jsonl",
    "value_types.jsonl",
)


def _sha256(data: bytes) -> str:
    """Hash exact emitted bytes."""

    return hashlib.sha256(data).hexdigest()


class LinguisticRuntimeViewReceiptV1(BaseModel):
    """Bounded receipt for a side-by-side runtime view with no self-promotion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-runtime-view-v1"] = "linguistic-runtime-view-v1"
    pack_id: Literal["linguistic_core"] = "linguistic_core"
    pack_version: Literal["0.4.0-rc1"] = "0.4.0-rc1"
    crosswalk_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_record_count: int = Field(ge=0)
    eligible_record_count: Literal[0] = 0
    emitted_predicate_count: Literal[0] = 0
    emitted_role_count: Literal[0] = 0
    emitted_entity_type_count: Literal[0] = 0
    default_activation: Literal[False] = False
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _non_promotional(self) -> "LinguisticRuntimeViewReceiptV1":
        content = self.model_dump(mode="json", exclude={"content_sha256"})
        if self.content_sha256 != _sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ):
            raise ValueError("runtime-view receipt digest does not reconcile")
        return self


def build_linguistic_runtime_view_receipt_v1(
    crosswalk: LinguisticCrosswalkV1,
) -> LinguisticRuntimeViewReceiptV1:
    """Bind a sparse candidate to all reviewed input without granting eligibility."""

    content = {
        "schema_version": "linguistic-runtime-view-v1",
        "pack_id": "linguistic_core",
        "pack_version": "0.4.0-rc1",
        "crosswalk_content_sha256": crosswalk.content_sha256,
        "input_record_count": len(crosswalk.records),
        "eligible_record_count": 0,
        "emitted_predicate_count": 0,
        "emitted_role_count": 0,
        "emitted_entity_type_count": 0,
        "default_activation": False,
    }
    return LinguisticRuntimeViewReceiptV1.model_validate(
        {
            **content,
            "content_sha256": _sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()),
        }
    )


def compile_linguistic_runtime_view_v1(
    crosswalk: LinguisticCrosswalkV1, *, output_dir: Path
) -> LinguisticRuntimeViewReceiptV1:
    """Write an atomically published sparse pack, refusing replacement or activation."""

    receipt = build_linguistic_runtime_view_receipt_v1(crosswalk)
    if output_dir.name != receipt.pack_version:
        raise ValueError("runtime-view output directory must equal the declared prerelease version")
    if output_dir.exists():
        raise FileExistsError(f"refusing to replace runtime view: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent, prefix=f".{output_dir.name}.stage-") as root:
        stage = Path(root) / output_dir.name
        stage.mkdir()
        artifact_hashes: dict[str, str] = {}
        for filename in RUNTIME_FILENAMES:
            payload = b""
            (stage / filename).write_bytes(payload)
            artifact_hashes[filename] = _sha256(payload)
        manifest = {
            "pack": {
                "id": receipt.pack_id,
                "version": receipt.pack_version,
                "name": receipt.pack_id,
                "description": "Non-default sparse runtime view; no semantic assertions are policy-eligible.",
            },
            "build": {
                "compiler_version": "linguistic-runtime-view-v1",
                "crosswalk_content_sha256": receipt.crosswalk_content_sha256,
                "runtime_view_receipt": receipt.model_dump(mode="json"),
                "artifact_sha256": artifact_hashes,
            },
            "capabilities": {"assertion_type": "n-ary", "type_system": "sumo"},
            "content": {
                "entity_types": "entity_types.jsonl",
                "predicate_types": "predicate_types.jsonl",
                "role_types": "role_types.jsonl",
                "value_types": "value_types.jsonl",
                "hierarchy_edges": "hierarchy_edges.jsonl",
                "predicate_role_edges": "predicate_role_edges.jsonl",
                "source_mappings": "source_mappings.jsonl",
                "aliases": "aliases.jsonl",
                "constraints": "constraints.jsonl",
            },
        }
        (stage / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        validate_linguistic_runtime_view_v1(stage)
        stage.replace(output_dir)
    return receipt


def validate_linguistic_runtime_view_v1(pack_dir: Path) -> LinguisticRuntimeViewReceiptV1:
    """Reject a promoted, incomplete, or byte-substituted sparse runtime view."""

    manifest = yaml.safe_load((pack_dir / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("runtime-view manifest must be an object")
    build = manifest.get("build")
    if not isinstance(build, dict):
        raise ValueError("runtime-view manifest requires build metadata")
    receipt = LinguisticRuntimeViewReceiptV1.model_validate(build.get("runtime_view_receipt"))
    if manifest.get("pack", {}).get("version") != receipt.pack_version:
        raise ValueError("runtime-view manifest version does not reconcile")
    declared = build.get("artifact_sha256")
    if not isinstance(declared, dict) or set(declared) != set(RUNTIME_FILENAMES):
        raise ValueError("runtime-view artifact inventory does not reconcile")
    if {path.name for path in pack_dir.iterdir() if path.is_file()} != {"manifest.yaml", *RUNTIME_FILENAMES}:
        raise ValueError("runtime-view file inventory does not reconcile")
    for filename in RUNTIME_FILENAMES:
        if (pack_dir / filename).read_bytes():
            raise ValueError("runtime-view cannot emit runtime rows without eligible semantics")
        if declared[filename] != _sha256((pack_dir / filename).read_bytes()):
            raise ValueError("runtime-view artifact hash does not reconcile")
    return receipt

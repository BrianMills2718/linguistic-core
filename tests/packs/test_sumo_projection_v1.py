"""Deterministic, fail-closed SUMO projection tests for Plan 0147."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError
import yaml

from scripts.compile_sumo_projection import main as compile_sumo_projection_main

from onto_canon6.packs.linguistic_sources_v1 import (
    GitSourceIdentityV1,
    LicenseEvidenceV1,
    LinguisticSourceManifestV1,
    LinguisticSourceSnapshotV1,
    compute_selected_payload_v1,
)
from onto_canon6.packs.sumo_projection_v1 import (
    SumoProjectionError,
    SumoProjectionV1,
    compile_sumo_projection_v1,
    load_sumo_projection_v1,
)


def _git(checkout: Path, *args: str) -> str:
    """Run one deterministic local Git operation for the clean-room source."""

    completed = subprocess.run(
        ["git", *args], cwd=checkout, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _source_checkout(tmp_path: Path) -> Path:
    """Create a real Git source with the exact bounded semantic neighborhood."""

    checkout = tmp_path / "sumo"
    checkout.mkdir()
    _git(checkout, "init", "--initial-branch=main")
    _git(checkout, "config", "user.email", "fixture@example.invalid")
    _git(checkout, "config", "user.name", "SUMO fixture")
    (checkout / "LICENSE").write_text("fixture license evidence\n", encoding="utf-8")
    (checkout / "Merge.kif").write_text(
        """; clean-room fixture, not upstream SUMO content
(instance Entity Class)
(instance Physical Class)
(instance Process Class)
(instance Motion Class)
(instance Translocation Class)
(instance Leaving Class)
(instance Object Class)
(instance AutonomousAgent Class)
(subclass Physical ; an embedded comment with a \"quoted phrase\"
 Entity)
(subclass Process Physical)
(subclass Motion Process)
(subclass Translocation Motion)
(subclass Leaving Translocation)
(subclass Object Physical)
(subclass AutonomousAgent Object)
(disjoint Process Object)
(documentation Leaving EnglishLanguage \"A departure process.\")
(format EnglishLanguage ignoredRelation\"source irregularity retained\")
(instance Relation Class)
(instance CaseRole Class)
(subclass CaseRole Relation)
(instance agent CaseRole)
(instance patient CaseRole)
(domain agent 1 Process)
(domain agent 2 AutonomousAgent)
(domain patient 1 Process)
(domain patient 2 Entity)
""",
        encoding="utf-8",
    )
    (checkout / "Mid-level-ontology.kif").write_text(
        """; clean-room secondary module retained in the complete inventory
(documentation Relation EnglishLanguage \"A relation type.\")
""",
        encoding="utf-8",
    )
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-m", "fixture")
    return checkout


def _manifest(checkout: Path) -> LinguisticSourceManifestV1:
    """Bind the fixture's exact Git tree, selected payload, and license bytes."""

    source = LinguisticSourceSnapshotV1(
        source_key="sumo_root_kif",
        family="sumo",
        release_label="clean-room fixture",
        official_url="https://example.invalid/sumo",
        availability="available",
        git_identity=GitSourceIdentityV1(
            commit_sha=_git(checkout, "rev-parse", "HEAD"),
            tree_sha=_git(checkout, "rev-parse", "HEAD^{tree}"),
        ),
        selected_payload=compute_selected_payload_v1(
            checkout, selection_globs=("*.kif",)
        ),
        license_disposition="mixed_review_required",
        license_evidence=(
            LicenseEvidenceV1.from_checkout_file(
                checkout, path="LICENSE", evidence_scope="repository"
            ),
        ),
        storage_policy="external_cache",
        redistribution_allowed=False,
    )
    return LinguisticSourceManifestV1(sources=(source,))


def test_projection_is_deterministic_closed_and_bounded(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    manifest = _manifest(checkout)

    first = compile_sumo_projection_v1(manifest, source_checkout=checkout)
    second = compile_sumo_projection_v1(manifest, source_checkout=checkout)

    assert first == second
    assert [module.path for module in first.modules] == [
        "Merge.kif",
        "Mid-level-ontology.kif",
    ]
    assert first.excluded_tree_paths == ("LICENSE",)
    assert first.publication_status == "blocked_mixed_license"
    assert first.redistribution_allowed is False
    assert first.formula_count == 28
    assert first.bounded_context.leaving_type_hierarchy == (
        "Leaving",
        "Translocation",
        "Motion",
        "Process",
        "Physical",
        "Entity",
    )
    assert first.bounded_context.autonomous_agent_type_hierarchy == (
        "AutonomousAgent",
        "Object",
        "Physical",
        "Entity",
    )
    assert [item.argument_type for item in first.bounded_context.agent_constraints] == [
        "Process",
        "AutonomousAgent",
    ]
    assert [item.argument_type for item in first.bounded_context.patient_constraints] == [
        "Process",
        "Entity",
    ]
    assert set(first.bounded_context.case_roles) == {"agent", "patient"}
    assert first.bounded_context.source_module == "Merge.kif"
    assert "location" not in first.bounded_context.case_roles
    assert SumoProjectionV1.model_validate_json(first.model_dump_json()) == first


def test_projection_rejects_source_byte_substitution(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    manifest = _manifest(checkout)
    path = checkout / "Merge.kif"
    path.write_bytes(path.read_bytes().replace(b"Leaving", b"Arriving", 1))

    with pytest.raises(ValueError, match="selected payload does not match manifest"):
        compile_sumo_projection_v1(manifest, source_checkout=checkout)


def test_projection_rejects_malformed_kif_after_rebinding(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    (checkout / "Merge.kif").write_text("(instance Entity Class\n", encoding="utf-8")
    _git(checkout, "add", "Merge.kif")
    _git(checkout, "commit", "-m", "malformed")

    with pytest.raises(SumoProjectionError, match="unclosed formula"):
        compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)


def test_projection_model_rejects_omitted_module(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    projection = compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)
    payload = projection.model_dump(mode="python")
    payload["modules"] = payload["modules"][:-1]

    with pytest.raises(ValidationError, match="selected module inventory"):
        SumoProjectionV1.model_validate(payload)


def test_projection_model_rejects_omitted_supported_axiom(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    projection = compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)
    payload = projection.model_dump(mode="python")
    payload["instance_axioms"] = payload["instance_axioms"][:-1]

    with pytest.raises(ValidationError, match="supported formula inventory"):
        SumoProjectionV1.model_validate(payload)


def test_projection_model_rejects_license_laundering(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    projection = compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)
    payload = projection.model_dump(mode="python")
    payload["redistribution_allowed"] = True
    payload["publication_status"] = "publishable"

    with pytest.raises(ValidationError):
        SumoProjectionV1.model_validate(payload)


def test_projection_model_rejects_count_preserving_axiom_substitution(
    tmp_path: Path,
) -> None:
    checkout = _source_checkout(tmp_path)
    projection = compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)
    payload = projection.model_dump(mode="python")
    payload["subclass_axioms"][0]["parent"] = "FabricatedParent"
    content_fields = (
        "modules",
        "excluded_tree_paths",
        "types",
        "relations",
        "instance_axioms",
        "subclass_axioms",
        "subrelation_axioms",
        "argument_constraints",
        "disjoint_axioms",
        "bounded_context",
    )
    content = {name: payload[name] for name in content_fields}
    payload["projection_content_sha256"] = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    with pytest.raises(ValidationError, match="dangling type or relation"):
        SumoProjectionV1.model_validate(payload)


def test_formula_refs_bind_exact_source_bytes(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    projection = compile_sumo_projection_v1(_manifest(checkout), source_checkout=checkout)
    leaving = next(item for item in projection.types if item.term == "Leaving")
    source_ref = leaving.source_refs[0]
    module = checkout / source_ref.module_path
    formulas = module.read_text(encoding="utf-8").splitlines()
    raw = formulas[source_ref.start_line - 1].encode("utf-8")

    assert hashlib.sha256(raw).hexdigest() == source_ref.formula_sha256


def test_cli_matches_library_and_refuses_silent_replacement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    checkout = _source_checkout(tmp_path)
    manifest = _manifest(checkout)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "sumo_projection.json.gz"

    assert compile_sumo_projection_main(
        [
            "--manifest",
            str(manifest_path),
            "--source-checkout",
            str(checkout),
            "--output",
            str(output),
        ]
    ) == 0
    assert load_sumo_projection_v1(output) == compile_sumo_projection_v1(
        manifest, source_checkout=checkout
    )
    assert '"published_or_activated": false' in capsys.readouterr().out
    original = output.read_bytes()
    with pytest.raises(FileExistsError, match="--force"):
        compile_sumo_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-checkout",
                str(checkout),
                "--output",
                str(output),
            ]
        )
    assert output.read_bytes() == original


def test_cli_refuses_to_replace_dangling_symlink(tmp_path: Path) -> None:
    checkout = _source_checkout(tmp_path)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(_manifest(checkout).model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    output = tmp_path / "projection.json"
    output.symlink_to(tmp_path / "missing-target.json")

    with pytest.raises(FileExistsError, match="--force"):
        compile_sumo_projection_main(
            [
                "--manifest",
                str(manifest_path),
                "--source-checkout",
                str(checkout),
                "--output",
                str(output),
            ]
        )
    assert output.is_symlink()

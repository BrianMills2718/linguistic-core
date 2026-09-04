"""Fail-closed tests for the module-scoped SUMO publication profile."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys

import pytest

from linguistic_core.linguistic_sources_v1 import load_linguistic_source_manifest_v1
from linguistic_core.sumo_projection_v1 import compile_sumo_projection_v1
from linguistic_core.sumo_publication_v1 import (
    PublishedSumoBoundedContextV1,
    SumoModulePublicationReviewV1,
    SumoPublicationError,
    compile_sumo_publication_v1,
    load_sumo_module_publication_config_v1,
)
from scripts.compile_sumo_publication import main as publication_main


ROOT = Path(__file__).parents[2]
SOURCE = (
    Path.home()
    / "projects/data/linguistic_sources/sumo"
    / "806b9cd57d1313309aad67dffa12871c06de0f26"
)


@pytest.fixture(scope="module")
def compiled() -> tuple[SumoModulePublicationReviewV1, PublishedSumoBoundedContextV1, str]:
    """Compile the exact retained source once for all publication controls."""

    if not SOURCE.is_dir():
        pytest.skip("exact external-cache SUMO checkout is unavailable")
    projection = compile_sumo_projection_v1(
        load_linguistic_source_manifest_v1(ROOT / "config/linguistic_sources_v1.yaml"),
        source_checkout=SOURCE,
    )
    return compile_sumo_publication_v1(
        projection,
        source_checkout=SOURCE,
        config=load_sumo_module_publication_config_v1(
            ROOT / "config/sumo_module_publication_v1.yaml"
        ),
    )


def test_review_dispositions_every_selected_module_and_publishes_only_merge(
    compiled: tuple[SumoModulePublicationReviewV1, PublishedSumoBoundedContextV1, str],
) -> None:
    """All 66 modules are visible while only exact Merge-derived facts ship."""

    review, context, attribution = compiled
    assert review.selected_module_count == 66
    assert review.approved_module_count == 1
    assert review.excluded_module_count == 65
    assert review.full_projection_publication_status == "blocked_mixed_license"
    approved = [
        item
        for item in review.module_dispositions
        if item.publication_disposition == "approved_for_linguistic_bounded_context"
    ]
    assert [(item.path, item.header_class) for item in approved] == [
        ("Merge.kif", "ieee_custom_notice")
    ]
    assert context.bounded_context.translocation_type_hierarchy == (
        "Translocation",
        "Motion",
        "Process",
        "Physical",
        "Entity",
    )
    assert context.bounded_context.case_roles == ("agent", "patient")
    assert tuple(
        (item.child, item.parent) for item in context.translocation_hierarchy_axioms
    ) == tuple(
        zip(
            context.bounded_context.translocation_type_hierarchy,
            context.bounded_context.translocation_type_hierarchy[1:],
        )
    )
    assert tuple(
        (item.child, item.parent) for item in context.autonomous_agent_hierarchy_axioms
    ) == tuple(
        zip(
            context.bounded_context.autonomous_agent_type_hierarchy,
            context.bounded_context.autonomous_agent_type_hierarchy[1:],
        )
    )
    assert tuple(item.instance for item in context.case_role_axioms) == ("agent", "patient")
    source_refs = (
        *(item.source_ref for item in context.translocation_hierarchy_axioms),
        *(item.source_ref for item in context.autonomous_agent_hierarchy_axioms),
        *(item.source_ref for item in context.case_role_axioms),
    )
    assert all(item.module_path == "Merge.kif" for item in source_refs)
    assert all(item.module_sha256 == context.source_module_sha256 for item in source_refs)
    assert "Institute of Electrical and Electronics Engineers" in attribution
    assert "prepare derivative works" in attribution
    assert hashlib.sha256(attribution.encode()).hexdigest() == context.attribution_sha256


def test_unapproved_modules_remain_excluded_even_when_their_header_mentions_gpl(
    compiled: tuple[SumoModulePublicationReviewV1, PublishedSumoBoundedContextV1, str],
) -> None:
    """Automated notice detection never promotes a module into the profile."""

    review, _context, _attribution = compiled
    mid = next(item for item in review.module_dispositions if item.path == "Mid-level-ontology.kif")
    assert mid.header_class == "gpl_notice"
    assert mid.publication_disposition == "excluded_pending_module_specific_review"


def test_source_or_notice_substitution_fails_closed(tmp_path: Path) -> None:
    """Hash-compatible-looking source edits cannot preserve publication approval."""

    if not SOURCE.is_dir():
        pytest.skip("exact external-cache SUMO checkout is unavailable")
    copied = tmp_path / "sumo"
    shutil.copytree(SOURCE, copied, symlinks=True)
    merge = copied / "Merge.kif"
    merge.write_bytes(
        merge.read_bytes().replace(b"prepare derivative works", b"prepare altered works   ", 1)
    )
    projection = compile_sumo_projection_v1(
        load_linguistic_source_manifest_v1(ROOT / "config/linguistic_sources_v1.yaml"),
        source_checkout=SOURCE,
    )
    with pytest.raises(SumoPublicationError, match="module identity changed"):
        compile_sumo_publication_v1(
            projection,
            source_checkout=copied,
            config=load_sumo_module_publication_config_v1(
                ROOT / "config/sumo_module_publication_v1.yaml"
            ),
        )


def test_cli_preflights_all_outputs_before_materializing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A colliding final destination cannot leave earlier artifacts behind."""

    if not SOURCE.is_dir():
        pytest.skip("exact external-cache SUMO checkout is unavailable")
    review = tmp_path / "review.json"
    context = tmp_path / "context.json"
    attribution = tmp_path / "attribution.txt"
    attribution.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile_sumo_publication.py",
            "--source-manifest",
            str(ROOT / "config/linguistic_sources_v1.yaml"),
            "--publication-config",
            str(ROOT / "config/sumo_module_publication_v1.yaml"),
            "--source-checkout",
            str(SOURCE),
            "--review-output",
            str(review),
            "--context-output",
            str(context),
            "--attribution-output",
            str(attribution),
        ],
    )
    with pytest.raises(FileExistsError, match="refusing to replace"):
        publication_main()
    assert not review.exists()
    assert not context.exists()

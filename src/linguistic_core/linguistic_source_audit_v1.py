"""Read-only comparison of donor identifiers with pinned linguistic sources.

Matching here means only that a normalized donor identifier occurs in the
selected current source. It does not prove historical identity or semantic
equivalence and never mutates the donor database or a crosswalk.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Literal, Mapping
import xml.etree.ElementTree as ET

from pydantic import BaseModel, ConfigDict, Field, model_validator

from linguistic_core.framenet_projection_v1 import compile_framenet_projection_v1
from linguistic_core.linguistic_sources_v1 import (
    LinguisticSourceManifestV1,
    LinguisticSourceVerificationReportV1,
    SourceFamily,
    verify_linguistic_source_manifest_v1,
)


ComparisonStatus = Literal[
    "matched_current_source",
    "missing_current_source",
    "invalid_donor_id",
    "source_unavailable",
]
_PROPBANK_DONOR_ID = re.compile(r"^(?P<lemma>.+)-(?P<sense>[0-9]{2})$")
_PROPBANK_ROLESET_ID = re.compile(
    r"<roleset\b[^>]*\bid=[\"'](?P<roleset_id>[^\"']+)[\"']", re.DOTALL
)
_SUMO_SYMBOL = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


class SourceSyntaxIssueV1(BaseModel):
    """Visible source syntax defect discovered during identifier indexing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: SourceFamily = Field(description="Affected source family.")
    relative_path: str = Field(
        min_length=1, description="Checkout-relative file containing the defect."
    )
    issue_kind: Literal["invalid_xml"] = Field(description="Stable syntax issue class.")
    detail: str = Field(min_length=1, description="Concrete parser error text.")


class DonorIdentifierComparisonV1(BaseModel):
    """Exhaustive disposition for one distinct donor identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: SourceFamily = Field(description="Source family named by the donor row.")
    donor_id: str = Field(min_length=1, description="Identifier exactly as stored by the donor.")
    normalized_source_id: str | None = Field(
        default=None,
        description="Mechanical current-source lookup form, or null when invalid/unavailable.",
    )
    donor_source_labels: tuple[str, ...] = Field(
        min_length=1, description="Distinct donor source labels attached to this identifier."
    )
    status: ComparisonStatus = Field(
        description="Syntactic current-source comparison disposition."
    )

    @model_validator(mode="after")
    def _normalization_matches_status(self) -> "DonorIdentifierComparisonV1":
        if self.status in {"matched_current_source", "missing_current_source"}:
            if self.normalized_source_id is None:
                raise ValueError("matched or missing comparison requires normalized_source_id")
        elif self.normalized_source_id is not None:
            raise ValueError("invalid or unavailable comparison cannot claim normalization")
        if tuple(sorted(set(self.donor_source_labels))) != self.donor_source_labels:
            raise ValueError("donor_source_labels must be sorted and unique")
        return self


class DonorIdentifierFamilySummaryV1(BaseModel):
    """Count reconciliation for one comparison family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: SourceFamily = Field(description="Summarized source family.")
    donor_identifier_count: int = Field(ge=0, description="Distinct donor identifier count.")
    matched_count: int = Field(ge=0, description="Identifiers present in selected current source.")
    missing_count: int = Field(ge=0, description="Valid identifiers absent from selected source.")
    invalid_count: int = Field(ge=0, description="Identifiers failing mechanical syntax rules.")
    unavailable_count: int = Field(
        ge=0, description="Identifiers not comparable because official source is unavailable."
    )

    @model_validator(mode="after")
    def _counts_reconcile(self) -> "DonorIdentifierFamilySummaryV1":
        classified = (
            self.matched_count
            + self.missing_count
            + self.invalid_count
            + self.unavailable_count
        )
        if classified != self.donor_identifier_count:
            raise ValueError("family comparison counts do not reconcile")
        return self


class LinguisticDonorLabelAuditV1(BaseModel):
    """Complete read-only donor-to-current-source syntactic comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-donor-label-audit-v1"] = Field(
        default="linguistic-donor-label-audit-v1",
        description="Audit report contract discriminator.",
    )
    donor_db_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete donor SQLite file."
    )
    manifest_semantic_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the normalized strict source manifest JSON.",
    )
    source_verification: LinguisticSourceVerificationReportV1 = Field(
        description="Exact source verification performed before donor comparison."
    )
    summaries: tuple[DonorIdentifierFamilySummaryV1, ...] = Field(
        min_length=1, description="Per-family reconciled comparison counts."
    )
    comparisons: tuple[DonorIdentifierComparisonV1, ...] = Field(
        description="Exhaustive distinct donor identifier dispositions."
    )
    source_syntax_issues: tuple[SourceSyntaxIssueV1, ...] = Field(
        default=(), description="Visible syntax defects in the exact selected sources."
    )

    @model_validator(mode="after")
    def _comparisons_reconcile(self) -> "LinguisticDonorLabelAuditV1":
        if len({summary.family for summary in self.summaries}) != len(self.summaries):
            raise ValueError("audit summaries must have unique families")
        comparison_keys = [
            (comparison.family, comparison.donor_id) for comparison in self.comparisons
        ]
        if len(comparison_keys) != len(set(comparison_keys)):
            raise ValueError("audit comparisons must have unique family/donor_id keys")
        by_family: dict[SourceFamily, list[DonorIdentifierComparisonV1]] = defaultdict(list)
        for comparison in self.comparisons:
            by_family[comparison.family].append(comparison)
        for summary in self.summaries:
            observed = _summary(summary.family, by_family[summary.family])
            if observed != summary:
                raise ValueError(f"comparison statuses do not reconcile for {summary.family}")
        if set(by_family) != {summary.family for summary in self.summaries}:
            raise ValueError("comparison families do not reconcile with summaries")
        return self

    def summary_by_family(self) -> dict[SourceFamily, DonorIdentifierFamilySummaryV1]:
        """Return summaries keyed by family for programmatic inspection."""

        return {summary.family: summary for summary in self.summaries}


def normalize_propbank_donor_id_v1(donor_id: str) -> str | None:
    """Convert donor ``lemma-01`` syntax to current PropBank ``lemma.01``."""

    match = _PROPBANK_DONOR_ID.fullmatch(donor_id)
    if match is None:
        return None
    return f"{match.group('lemma')}.{match.group('sense')}"


def normalize_sumo_donor_id_v1(donor_id: str) -> str | None:
    """Accept one complete SUMO symbol and reject malformed donor values."""

    if _SUMO_SYMBOL.fullmatch(donor_id) is None:
        return None
    return donor_id


def _selected_files(checkout: Path, globs: tuple[str, ...]) -> tuple[Path, ...]:
    root = checkout.resolve()
    selected = {path for pattern in globs for path in root.glob(pattern) if path.is_file()}
    files = tuple(sorted(selected, key=lambda path: path.relative_to(root).as_posix()))
    if not files:
        raise ValueError("source selection contains no files")
    for path in files:
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError(f"selected source file escapes checkout: {path}")
    return files


def _propbank_roleset_ids(
    checkout: Path, globs: tuple[str, ...]
) -> tuple[set[str], tuple[SourceSyntaxIssueV1, ...]]:
    root_path = checkout.resolve()
    roleset_ids: set[str] = set()
    issues: list[SourceSyntaxIssueV1] = []
    for path in _selected_files(checkout, globs):
        text = path.read_text(encoding="utf-8", errors="strict")
        try:
            parsed_root = ET.parse(path).getroot()
        except ET.ParseError as error:
            roleset_ids.update(
                match.group("roleset_id") for match in _PROPBANK_ROLESET_ID.finditer(text)
            )
            issues.append(
                SourceSyntaxIssueV1(
                    family="propbank",
                    relative_path=path.relative_to(root_path).as_posix(),
                    issue_kind="invalid_xml",
                    detail=str(error),
                )
            )
        else:
            roleset_ids.update(
                roleset_id
                for element in parsed_root.iter("roleset")
                if (roleset_id := element.get("id")) is not None
            )
    return roleset_ids, tuple(issues)


def _sumo_symbols(checkout: Path, globs: tuple[str, ...]) -> set[str]:
    symbols: set[str] = set()
    for path in _selected_files(checkout, globs):
        in_string = False
        escaped = False
        visible: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
            index = 0
            while index < len(line):
                character = line[index]
                if in_string:
                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False
                    visible.append(" ")
                elif character == '"':
                    in_string = True
                    visible.append(" ")
                elif character == ";":
                    visible.extend(" " for _ in line[index:])
                    break
                else:
                    visible.append(character)
                index += 1
            visible.append("\n")
        if in_string:
            raise ValueError(f"unterminated SUMO string in {path}")
        symbols.update(_SUMO_SYMBOL.findall("".join(visible)))
    return symbols


def _read_donor_identifiers(
    database: Path,
) -> dict[SourceFamily, dict[str, tuple[str, ...]]]:
    uri = f"{database.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        queries: dict[SourceFamily, str] = {
            "propbank": (
                "SELECT propbank_sense_id, source FROM predicates "
                "WHERE propbank_sense_id IS NOT NULL ORDER BY propbank_sense_id, source"
            ),
            "framenet": "SELECT id, source FROM frames ORDER BY id, source",
            "sumo": "SELECT id, source FROM types ORDER BY id, source",
        }
        result: dict[SourceFamily, dict[str, tuple[str, ...]]] = {}
        for family, query in queries.items():
            labels: dict[str, set[str]] = defaultdict(set)
            for donor_id, source_label in connection.execute(query):
                labels[str(donor_id)].add(str(source_label))
            result[family] = {
                donor_id: tuple(sorted(source_labels))
                for donor_id, source_labels in sorted(labels.items())
            }
        return result
    finally:
        connection.close()


def _summary(
    family: SourceFamily, comparisons: list[DonorIdentifierComparisonV1]
) -> DonorIdentifierFamilySummaryV1:
    statuses = [comparison.status for comparison in comparisons]
    return DonorIdentifierFamilySummaryV1(
        family=family,
        donor_identifier_count=len(comparisons),
        matched_count=statuses.count("matched_current_source"),
        missing_count=statuses.count("missing_current_source"),
        invalid_count=statuses.count("invalid_donor_id"),
        unavailable_count=statuses.count("source_unavailable"),
    )


def audit_linguistic_donor_labels_v1(
    donor_database: Path,
    *,
    manifest: LinguisticSourceManifestV1,
    source_roots: Mapping[str, Path],
) -> LinguisticDonorLabelAuditV1:
    """Classify every donor identifier against exact current sources, read-only."""

    database = donor_database.resolve()
    if not database.is_file():
        raise ValueError(f"donor database is missing: {donor_database}")
    database_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    verification = verify_linguistic_source_manifest_v1(
        manifest, source_roots=source_roots
    )
    sources = {source.family: source for source in manifest.sources}
    donor_ids = _read_donor_identifiers(database)

    propbank = sources["propbank"]
    sumo = sources["sumo"]
    if propbank.selected_payload is None or sumo.selected_payload is None:
        raise ValueError("PropBank and SUMO must be available for donor label audit")
    propbank_ids, source_syntax_issues = _propbank_roleset_ids(
        source_roots[propbank.source_key], propbank.selected_payload.selection_globs
    )
    sumo_ids = _sumo_symbols(
        source_roots[sumo.source_key], sumo.selected_payload.selection_globs
    )
    framenet = sources["framenet"]
    framenet_ids: set[str] | None = None
    if framenet.availability == "available":
        archive = source_roots.get(framenet.source_key)
        if archive is None:
            raise ValueError("available FrameNet source requires a local archive")
        framenet_ids = {
            frame.name
            for frame in compile_framenet_projection_v1(
                manifest, source_archive=archive
            ).frames
        }

    all_comparisons: list[DonorIdentifierComparisonV1] = []
    summaries: list[DonorIdentifierFamilySummaryV1] = []
    for family in ("propbank", "framenet", "sumo"):
        family_comparisons: list[DonorIdentifierComparisonV1] = []
        for donor_id, source_labels in donor_ids[family].items():
            normalized: str | None
            status: ComparisonStatus
            if family == "propbank":
                normalized = normalize_propbank_donor_id_v1(donor_id)
                if normalized is None:
                    status = "invalid_donor_id"
                elif normalized in propbank_ids:
                    status = "matched_current_source"
                else:
                    status = "missing_current_source"
            elif family == "framenet":
                if framenet_ids is None:
                    normalized = None
                    status = "source_unavailable"
                else:
                    normalized = donor_id
                    status = (
                        "matched_current_source"
                        if normalized in framenet_ids
                        else "missing_current_source"
                    )
            else:
                normalized = normalize_sumo_donor_id_v1(donor_id)
                if normalized is None:
                    status = "invalid_donor_id"
                else:
                    status = (
                        "matched_current_source"
                        if normalized in sumo_ids
                        else "missing_current_source"
                    )
            family_comparisons.append(
                DonorIdentifierComparisonV1(
                    family=family,
                    donor_id=donor_id,
                    normalized_source_id=normalized,
                    donor_source_labels=source_labels,
                    status=status,
                )
            )
        summaries.append(_summary(family, family_comparisons))
        all_comparisons.extend(family_comparisons)

    manifest_digest = hashlib.sha256(
        manifest.model_dump_json().encode("utf-8")
    ).hexdigest()
    return LinguisticDonorLabelAuditV1(
        donor_db_sha256=database_sha256,
        manifest_semantic_sha256=manifest_digest,
        source_verification=verification,
        summaries=tuple(summaries),
        comparisons=tuple(all_comparisons),
        source_syntax_issues=source_syntax_issues,
    )

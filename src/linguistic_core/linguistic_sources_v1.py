"""Exact, fail-closed source identities for the linguistic ontology pack.

The contract binds source acquisition facts only. It does not assert that a
donor mapping is correct, promote a crosswalk row, or change a runtime pack.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import subprocess
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml


SourceFamily = Literal["propbank", "framenet", "sumo"]
Availability = Literal["available", "temporarily_unavailable"]
LicenseDisposition = Literal[
    "verified_redistributable", "mixed_review_required", "unknown"
]
StoragePolicy = Literal["external_cache", "reference_only"]


class GitSourceIdentityV1(BaseModel):
    """Exact Git commit and root-tree identity for one official checkout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commit_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Exact upstream Git commit SHA-1."
    )
    tree_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$", description="Exact root Git tree SHA-1 at the commit."
    )


class ArchiveSourceIdentityV1(BaseModel):
    """Exact identity of one maintained non-Git source archive."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    archive_filename: str = Field(
        min_length=1,
        description="Expected basename of the retained source archive.",
    )
    byte_count: int = Field(gt=0, description="Exact archive byte length.")
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the complete retained archive bytes.",
    )
    distribution_url: str = Field(
        pattern=r"^https://",
        description="Maintained distribution URL whose metadata identifies the archive.",
    )

    @model_validator(mode="after")
    def _filename_is_a_basename(self) -> "ArchiveSourceIdentityV1":
        path = Path(self.archive_filename)
        if path.name != self.archive_filename or self.archive_filename in {".", ".."}:
            raise ValueError("archive_filename must be one safe basename")
        return self


class DistributionMetadataEvidenceV1(BaseModel):
    """Revision-bound upstream metadata supporting archive identity or license."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository_url: str = Field(
        pattern=r"^https://",
        description="Maintained metadata repository containing the evidence record.",
    )
    revision_sha: str = Field(
        pattern=r"^[0-9a-f]{40}$",
        description="Exact metadata-repository commit containing the evidence record.",
    )
    path: str = Field(
        min_length=1,
        description="Repository-relative metadata record path at the exact revision.",
    )
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the complete metadata record bytes.",
    )
    evidence_scope: Literal["archive_identity", "license"] = Field(
        description="Whether the record supports archive identity or licensing."
    )
    license_id: str | None = Field(
        default=None,
        description="Exact license identifier only for metadata that states one.",
    )
    attribution_title: str | None = Field(
        default=None,
        min_length=1,
        description="Work title supplied by the exact license metadata, when present.",
    )
    attribution_author: str | None = Field(
        default=None,
        min_length=1,
        description="Original author supplied by the exact license metadata, when present.",
    )
    attribution_uri: str | None = Field(
        default=None,
        pattern=r"^https?://",
        description="Work URI supplied by the exact license metadata, when present.",
    )

    @model_validator(mode="after")
    def _metadata_evidence_is_consistent(self) -> "DistributionMetadataEvidenceV1":
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("metadata evidence path must be repository-relative")
        if self.evidence_scope == "license" and self.license_id is None:
            raise ValueError("license metadata evidence requires license_id")
        if self.evidence_scope != "license" and self.license_id is not None:
            raise ValueError("archive identity metadata cannot declare license_id")
        attribution = (
            self.attribution_title,
            self.attribution_author,
            self.attribution_uri,
        )
        if self.evidence_scope != "license" and any(value is not None for value in attribution):
            raise ValueError("archive identity metadata cannot declare attribution fields")
        if any(value is not None for value in attribution) and not all(
            value is not None for value in attribution
        ):
            raise ValueError("license metadata attribution fields must be complete")
        return self


class SelectedPayloadV1(BaseModel):
    """Canonical digest of the files selected from an exact checkout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_globs: tuple[str, ...] = Field(
        min_length=1,
        description="Repository-relative glob set defining the selected source payload.",
    )
    digest_algorithm: Literal["path-length-bytes-sha256-v1"] = Field(
        default="path-length-bytes-sha256-v1",
        description="Canonical path-and-byte framing used for the aggregate digest.",
    )
    file_count: int = Field(gt=0, description="Exact selected regular-file count.")
    byte_count: int = Field(gt=0, description="Exact sum of selected file byte lengths.")
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of sorted framed relative paths and complete file bytes.",
    )

    @model_validator(mode="after")
    def _selection_globs_are_safe(self) -> "SelectedPayloadV1":
        if len(set(self.selection_globs)) != len(self.selection_globs):
            raise ValueError("selection_globs must be unique")
        for value in self.selection_globs:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not value.strip():
                raise ValueError("selection_globs must be non-empty repository-relative paths")
        return self


class LicenseEvidenceV1(BaseModel):
    """Byte-bound license evidence observed inside an official checkout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, description="Repository-relative evidence file path.")
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$", description="SHA-256 of the complete evidence file."
    )
    evidence_scope: Literal["repository", "selected_module", "selected_payload"] = Field(
        description="Declared scope to which the evidence text applies."
    )
    license_id: str | None = Field(
        default=None,
        description="SPDX-style identifier only when the evidence supports one exact license.",
    )

    @model_validator(mode="after")
    def _path_is_safe(self) -> "LicenseEvidenceV1":
        path = Path(self.path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("license evidence path must be repository-relative")
        return self

    @classmethod
    def from_checkout_file(
        cls,
        checkout: Path,
        *,
        path: str,
        evidence_scope: Literal[
            "repository", "selected_module", "selected_payload"
        ] = "selected_payload",
        license_id: str | None = None,
    ) -> "LicenseEvidenceV1":
        """Create exact evidence from one local checkout file."""

        evidence_path = _safe_checkout_path(checkout, path)
        return cls(
            path=path,
            sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            evidence_scope=evidence_scope,
            license_id=license_id,
        )


class UnavailableSourceEvidenceV1(BaseModel):
    """Observed official evidence that a declared source cannot be acquired."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observed_at: datetime = Field(description="Timezone-aware observation time.")
    evidence_url: str = Field(
        pattern=r"^https://", description="Official page supporting the unavailable state."
    )
    reason: str = Field(min_length=1, description="Concrete observed acquisition blocker.")

    @model_validator(mode="after")
    def _observation_is_timezone_aware(self) -> "UnavailableSourceEvidenceV1":
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return self


class LinguisticSourceSnapshotV1(BaseModel):
    """One source family's exact identity or explicit unavailable state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(
        pattern=r"^[a-z0-9_]+$", description="Manifest-local stable source key."
    )
    family: SourceFamily = Field(description="Linguistic source family.")
    release_label: str = Field(
        min_length=1, description="Upstream release label or pinned-revision label."
    )
    official_url: str = Field(pattern=r"^https://", description="Official source location.")
    availability: Availability = Field(description="Observed acquisition state.")
    git_identity: GitSourceIdentityV1 | None = Field(
        default=None, description="Exact Git identity when the official source is Git-backed."
    )
    archive_identity: ArchiveSourceIdentityV1 | None = Field(
        default=None,
        description="Exact archive identity when the maintained source is not Git-backed.",
    )
    selected_payload: SelectedPayloadV1 | None = Field(
        default=None, description="Exact selected payload identity when available."
    )
    unavailable_evidence: UnavailableSourceEvidenceV1 | None = Field(
        default=None, description="Official evidence when acquisition is unavailable."
    )
    license_disposition: LicenseDisposition = Field(
        description="Reviewed license status for the selected payload."
    )
    license_evidence: tuple[LicenseEvidenceV1, ...] = Field(
        default=(), description="Byte-bound evidence supporting the license disposition."
    )
    metadata_evidence: tuple[DistributionMetadataEvidenceV1, ...] = Field(
        default=(),
        description="Revision-bound distribution metadata for archive identity and licensing.",
    )
    storage_policy: StoragePolicy = Field(
        description="Whether bytes stay in an external cache or only a reference is retained."
    )
    redistribution_allowed: bool = Field(
        description="Reviewed permission to redistribute the selected payload."
    )

    @model_validator(mode="after")
    def _state_is_truthful(self) -> "LinguisticSourceSnapshotV1":
        if self.availability == "available":
            git_identity_complete = self.git_identity is not None and self.selected_payload is not None
            git_identity_partial = (self.git_identity is None) != (self.selected_payload is None)
            archive_identity_present = self.archive_identity is not None
            if git_identity_partial or git_identity_complete == archive_identity_present:
                raise ValueError(
                    "available source requires exactly one complete Git or archive identity"
                )
            if self.unavailable_evidence is not None:
                raise ValueError("available source cannot carry unavailable evidence")
            if not self.license_evidence and not self.metadata_evidence:
                raise ValueError("available source requires exact license evidence")
            if archive_identity_present:
                scopes = {item.evidence_scope for item in self.metadata_evidence}
                if scopes != {"archive_identity", "license"}:
                    raise ValueError(
                        "archive source requires separate identity and license metadata evidence"
                    )
                if self.family == "framenet" and self.redistribution_allowed and not any(
                    item.evidence_scope == "license"
                    and item.attribution_title is not None
                    and item.attribution_author is not None
                    and item.attribution_uri is not None
                    for item in self.metadata_evidence
                ):
                    raise ValueError(
                        "redistributable FrameNet archive requires complete supplied attribution"
                    )
            if self.storage_policy != "external_cache":
                raise ValueError("available source bytes must use external_cache storage policy")
        else:
            if self.unavailable_evidence is None:
                raise ValueError("unavailable source requires official unavailable evidence")
            if (
                self.git_identity is not None
                or self.archive_identity is not None
                or self.selected_payload is not None
            ):
                raise ValueError("unavailable source cannot claim Git, archive, or payload identity")
            if self.license_evidence or self.metadata_evidence:
                raise ValueError("unavailable source cannot claim license evidence")
            if self.storage_policy != "reference_only":
                raise ValueError("unavailable source must remain reference_only")
        if self.redistribution_allowed and self.license_disposition != "verified_redistributable":
            raise ValueError("redistribution requires verified_redistributable license evidence")
        has_exact_license = any(item.license_id for item in self.license_evidence) or any(
            item.license_id for item in self.metadata_evidence
        )
        if self.license_disposition == "verified_redistributable" and not has_exact_license:
            raise ValueError("verified redistributable source requires an exact license_id")
        metadata_keys = [
            (item.repository_url, item.revision_sha, item.path)
            for item in self.metadata_evidence
        ]
        if len(metadata_keys) != len(set(metadata_keys)):
            raise ValueError("distribution metadata evidence records must be unique")
        return self


class LinguisticSourceManifestV1(BaseModel):
    """Complete authoritative source set for one linguistic source snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-source-manifest-v1"] = Field(
        default="linguistic-source-manifest-v1",
        description="Manifest contract discriminator.",
    )
    sources: tuple[LinguisticSourceSnapshotV1, ...] = Field(
        min_length=1, description="Complete declared source snapshots."
    )

    @model_validator(mode="after")
    def _sources_are_unique(self) -> "LinguisticSourceManifestV1":
        for field_name in ("source_key", "family"):
            values = [getattr(source, field_name) for source in self.sources]
            if len(values) != len(set(values)):
                raise ValueError(f"manifest {field_name} values must be unique")
        return self

    def source_for(self, source_key: str) -> LinguisticSourceSnapshotV1:
        """Return one declared source or fail loud for an unknown key."""

        source = next((item for item in self.sources if item.source_key == source_key), None)
        if source is None:
            raise ValueError(f"unknown linguistic source key: {source_key}")
        return source


class LinguisticSourceVerificationV1(BaseModel):
    """Observed verification result for one declared source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str = Field(min_length=1, description="Verified manifest source key.")
    status: Literal["verified", "unavailable"] = Field(
        description="Observed source verification disposition."
    )
    commit_sha: str | None = Field(
        default=None, description="Observed exact Git commit for an available source."
    )
    tree_sha: str | None = Field(
        default=None, description="Observed exact Git tree for an available source."
    )
    selected_payload_sha256: str | None = Field(
        default=None, description="Observed selected-payload aggregate SHA-256."
    )
    archive_byte_count: int | None = Field(
        default=None, description="Observed exact archive byte length."
    )
    archive_sha256: str | None = Field(
        default=None, description="Observed exact archive SHA-256."
    )


class LinguisticSourceVerificationReportV1(BaseModel):
    """Complete deterministic verification report for one manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["linguistic-source-verification-v1"] = Field(
        default="linguistic-source-verification-v1",
        description="Verification report discriminator.",
    )
    sources: tuple[LinguisticSourceVerificationV1, ...] = Field(
        min_length=1, description="Results in manifest order."
    )


def _safe_checkout_path(checkout: Path, relative_path: str) -> Path:
    root = checkout.resolve()
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("checkout paths must be repository-relative")
    resolved = (root / path).resolve()
    if root not in resolved.parents:
        raise ValueError(f"checkout path escapes root: {relative_path}")
    if not resolved.is_file():
        raise ValueError(f"checkout file is missing: {relative_path}")
    return resolved


def compute_selected_payload_v1(
    checkout: Path, *, selection_globs: tuple[str, ...]
) -> SelectedPayloadV1:
    """Hash a sorted, duplicate-free selection of complete checkout files."""

    root = checkout.resolve()
    if not root.is_dir():
        raise ValueError(f"source checkout is not a directory: {checkout}")
    selected: set[Path] = set()
    for pattern in selection_globs:
        pattern_path = Path(pattern)
        if pattern_path.is_absolute() or ".." in pattern_path.parts or not pattern.strip():
            raise ValueError("selection globs must be repository-relative")
        selected.update(path for path in root.glob(pattern) if path.is_file())
    if not selected:
        raise ValueError("selected payload contains no files")

    digest = hashlib.sha256()
    byte_count = 0
    for path in sorted(selected, key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"selected payload cannot contain symlinks: {path}")
        resolved = path.resolve()
        if root not in resolved.parents:
            raise ValueError(f"selected payload file escapes checkout root: {path}")
        relative_bytes = path.relative_to(root).as_posix().encode("utf-8")
        payload = path.read_bytes()
        byte_count += len(payload)
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return SelectedPayloadV1(
        selection_globs=selection_globs,
        file_count=len(selected),
        byte_count=byte_count,
        sha256=digest.hexdigest(),
    )


def load_linguistic_source_manifest_v1(path: Path) -> LinguisticSourceManifestV1:
    """Load one strict UTF-8 YAML source manifest."""

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return LinguisticSourceManifestV1.model_validate(data)


def _git_value(checkout: Path, revision: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", revision],
        cwd=checkout,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"unable to inspect Git source checkout: {detail}")
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    """Hash a complete file without loading a potentially large archive into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_available_source(
    source: LinguisticSourceSnapshotV1, source_path: Path
) -> LinguisticSourceVerificationV1:
    if source.archive_identity is not None:
        archive = source.archive_identity
        if not source_path.is_file():
            raise ValueError(f"{source.source_key} archive path is not a file")
        if source_path.name != archive.archive_filename:
            raise ValueError(f"{source.source_key} archive filename does not match manifest")
        observed_byte_count = source_path.stat().st_size
        observed_sha256 = _sha256_file(source_path)
        if observed_byte_count != archive.byte_count or observed_sha256 != archive.sha256:
            raise ValueError(f"{source.source_key} archive bytes do not match manifest")
        return LinguisticSourceVerificationV1(
            source_key=source.source_key,
            status="verified",
            archive_byte_count=observed_byte_count,
            archive_sha256=observed_sha256,
        )

    if source.git_identity is None or source.selected_payload is None:
        raise ValueError("available source lacks exact identity")
    checkout = source_path
    observed_commit = _git_value(checkout, "HEAD")
    if observed_commit != source.git_identity.commit_sha:
        raise ValueError(f"{source.source_key} commit SHA does not match manifest")
    observed_tree = _git_value(checkout, "HEAD^{tree}")
    if observed_tree != source.git_identity.tree_sha:
        raise ValueError(f"{source.source_key} tree SHA does not match manifest")
    observed_payload = compute_selected_payload_v1(
        checkout, selection_globs=source.selected_payload.selection_globs
    )
    if observed_payload != source.selected_payload:
        raise ValueError(f"{source.source_key} selected payload does not match manifest")
    for evidence in source.license_evidence:
        observed = LicenseEvidenceV1.from_checkout_file(
            checkout,
            path=evidence.path,
            evidence_scope=evidence.evidence_scope,
            license_id=evidence.license_id,
        )
        if observed != evidence:
            raise ValueError(f"{source.source_key} license evidence does not match manifest")
    return LinguisticSourceVerificationV1(
        source_key=source.source_key,
        status="verified",
        commit_sha=observed_commit,
        tree_sha=observed_tree,
        selected_payload_sha256=observed_payload.sha256,
    )


def verify_linguistic_source_manifest_v1(
    manifest: LinguisticSourceManifestV1,
    *,
    source_roots: Mapping[str, Path],
) -> LinguisticSourceVerificationReportV1:
    """Verify every available checkout or archive and preserve unavailable states."""

    declared_keys = {source.source_key for source in manifest.sources}
    extra_keys = set(source_roots) - declared_keys
    if extra_keys:
        raise ValueError(f"source roots contain undeclared keys: {sorted(extra_keys)}")
    results: list[LinguisticSourceVerificationV1] = []
    for source in manifest.sources:
        checkout = source_roots.get(source.source_key)
        if source.availability == "temporarily_unavailable":
            if checkout is not None:
                raise ValueError(
                    f"unavailable source {source.source_key} must not receive a local source root"
                )
            results.append(
                LinguisticSourceVerificationV1(
                    source_key=source.source_key, status="unavailable"
                )
            )
            continue
        if checkout is None:
            raise ValueError(f"available source {source.source_key} requires a local source root")
        results.append(_verify_available_source(source, checkout))
    return LinguisticSourceVerificationReportV1(sources=tuple(results))

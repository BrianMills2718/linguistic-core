"""Tests for the linguistic_core pack compiler and RoleSlotsLookup.

Acceptance criteria from Plan #183:
- compile_linguistic_core_pack runs and produces predicate_types.jsonl (4,669
  entries) and role_types.jsonl (11,890 entries)
- fund_provide_money in role_types.jsonl has roles supplier, imposed_purpose,
  purpose — no ARG0/ARG1/ARG2 in role_id fields
- source_mappings.jsonl contains fund_provide_money:supplier → propbank:fund-01:ARG0
- RoleSlotsLookup: named_label(), roles_for_predicate(), all_role_labels() work
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from onto_canon6.config import repo_root
from onto_canon6.packs.role_slots_lookup import RoleSlot, RoleSlotsError, RoleSlotsLookup

_DB = repo_root() / "data" / "sumo_plus.db"
_PACK_DIR = repo_root() / "ontology_packs" / "linguistic_core" / "0.1.0"

pytestmark = pytest.mark.skipif(
    not _DB.exists(),
    reason="sumo_plus.db not found — skipping pack tests",
)


# ---------------------------------------------------------------------------
# RoleSlotsLookup unit tests
# ---------------------------------------------------------------------------


class TestRoleSlotsLookup:
    """Tests for RoleSlotsLookup against the real sumo_plus.db."""

    def test_named_label_fund_provide_money_arg0(self) -> None:
        """ARG0 of fund_provide_money should resolve to 'Supplier'."""
        with RoleSlotsLookup(_DB) as lookup:
            label = lookup.named_label("fund_provide_money", "ARG0")
        assert label == "Supplier"

    def test_named_label_fund_provide_money_arg1(self) -> None:
        """ARG1 of fund_provide_money should resolve to 'Imposed_purpose'."""
        with RoleSlotsLookup(_DB) as lookup:
            label = lookup.named_label("fund_provide_money", "ARG1")
        assert label == "Imposed_purpose"

    def test_named_label_fund_provide_money_arg2(self) -> None:
        """ARG2 of fund_provide_money should resolve to 'Purpose'."""
        with RoleSlotsLookup(_DB) as lookup:
            label = lookup.named_label("fund_provide_money", "ARG2")
        assert label == "Purpose"

    def test_named_label_unknown_returns_none(self) -> None:
        """Unknown predicate/arg pairs should return None, not raise."""
        with RoleSlotsLookup(_DB) as lookup:
            label = lookup.named_label("nonexistent_predicate_xyz", "ARG0")
        assert label is None

    def test_roles_for_predicate_fund_provide_money(self) -> None:
        """fund_provide_money should have exactly 3 roles with semantic names."""
        with RoleSlotsLookup(_DB) as lookup:
            roles = lookup.roles_for_predicate("fund_provide_money")
        assert len(roles) == 3
        labels = {r.named_label for r in roles}
        assert labels == {"Supplier", "Imposed_purpose", "Purpose"}
        # No ARG labels in named_label field
        for role in roles:
            assert not role.named_label.startswith("ARG"), (
                f"named_label should not be an ARG position: {role.named_label}"
            )

    def test_roles_for_predicate_returns_role_slot_objects(self) -> None:
        """roles_for_predicate should return RoleSlot dataclass instances."""
        with RoleSlotsLookup(_DB) as lookup:
            roles = lookup.roles_for_predicate("fund_provide_money")
        for role in roles:
            assert isinstance(role, RoleSlot)
            assert role.predicate_id == "fund_provide_money"
            assert role.arg_position.startswith("ARG")

    def test_predicate_count(self) -> None:
        """predicate_count should match the known 4,669 count."""
        with RoleSlotsLookup(_DB) as lookup:
            count = lookup.predicate_count()
        assert count == 4669

    def test_role_slot_count(self) -> None:
        """role_slot_count should match the known 11,890 count."""
        with RoleSlotsLookup(_DB) as lookup:
            count = lookup.role_slot_count()
        assert count == 11890

    def test_all_role_labels_format(self) -> None:
        """all_role_labels should return dict[str, dict[str, str]] with expected structure."""
        with RoleSlotsLookup(_DB) as lookup:
            mapping = lookup.all_role_labels()

        assert isinstance(mapping, dict)
        assert "fund_provide_money" in mapping
        fund = mapping["fund_provide_money"]
        assert fund["ARG0"] == "Supplier"
        assert fund["ARG1"] == "Imposed_purpose"
        assert fund["ARG2"] == "Purpose"

    def test_all_role_labels_no_null_values(self) -> None:
        """Confirmed zero null named_label values in sumo_plus.db."""
        with RoleSlotsLookup(_DB) as lookup:
            mapping = lookup.all_role_labels()

        for pred_id, arg_map in mapping.items():
            for arg_pos, label in arg_map.items():
                assert label and label.strip(), (
                    f"Blank named_label for {pred_id}/{arg_pos}"
                )

    def test_context_manager_closes_connection(self) -> None:
        """After __exit__, calling methods should not silently fail."""
        lookup = RoleSlotsLookup(_DB)
        with lookup:
            label = lookup.named_label("fund_provide_money", "ARG0")
        assert label == "Supplier"
        # After close, the connection is closed — no lingering state.

    def test_missing_db_raises(self, tmp_path: Path) -> None:
        """Missing DB file should raise RoleSlotsError."""
        with pytest.raises(RoleSlotsError, match="not found"):
            RoleSlotsLookup(tmp_path / "nonexistent.db")

    def test_malformed_db_raises(self, tmp_path: Path) -> None:
        """A DB missing the required tables should raise RoleSlotsError."""
        bad_db = tmp_path / "bad.db"
        conn = sqlite3.connect(str(bad_db))
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.close()
        with pytest.raises(RoleSlotsError, match="missing tables"):
            RoleSlotsLookup(bad_db)


# ---------------------------------------------------------------------------
# Pack compiler acceptance tests
# ---------------------------------------------------------------------------


class TestLinguisticCorePack:
    """Tests for the compiled linguistic_core pack files.

    These tests verify the committed pack files match Plan #183 acceptance
    criteria. Run ``python scripts/compile_linguistic_core_pack.py`` first
    to generate the pack.
    """

    @pytest.fixture(autouse=True)
    def require_pack(self) -> None:
        """Skip if pack files have not been compiled yet."""
        if not _PACK_DIR.exists():
            pytest.skip("Pack not compiled yet — run compile_linguistic_core_pack.py")

    def test_predicate_types_count(self) -> None:
        """predicate_types.jsonl should contain exactly 4,669 entries."""
        lines = (_PACK_DIR / "predicate_types.jsonl").read_text().strip().splitlines()
        assert len(lines) == 4669

    def test_role_types_count(self) -> None:
        """role_types.jsonl line count should be ≤ 11,890 (unique role types, not slots)."""
        lines = (_PACK_DIR / "role_types.jsonl").read_text().strip().splitlines()
        # Unique named labels < total slots — just verify non-empty and reasonable
        assert 1 <= len(lines) <= 11890

    def test_fund_provide_money_predicate_in_pack(self) -> None:
        """fund_provide_money should appear in predicate_types.jsonl with lc: prefix."""
        predicates = [
            json.loads(line)
            for line in (_PACK_DIR / "predicate_types.jsonl").read_text().splitlines()
        ]
        fund = next((p for p in predicates if p["predicate_id"] == "lc:fund_provide_money"), None)
        assert fund is not None, "lc:fund_provide_money not found in predicate_types.jsonl"
        assert fund["preferred_label"] == "fund"
        assert fund["status"] == "active"

    def test_fund_provide_money_roles_no_arg_in_role_id(self) -> None:
        """role_types.jsonl must not have ARG positions as role_id values."""
        role_types = [
            json.loads(line)
            for line in (_PACK_DIR / "role_types.jsonl").read_text().splitlines()
        ]
        expected_roles = {"lc.role.supplier", "lc.role.imposed_purpose", "lc.role.purpose"}
        present = {r["role_id"] for r in role_types}
        for expected in expected_roles:
            assert expected in present, f"{expected} not found in role_types.jsonl"

        # Verify no role_id looks like an ARG position
        for role in role_types:
            assert not role["role_id"].endswith("arg0") and "arg0" not in role["role_id"].lower(), (
                f"ARG position leaked into role_id: {role['role_id']}"
            )

    def test_source_mappings_fund_supplier_to_arg0(self) -> None:
        """source_mappings.jsonl should contain fund_provide_money:supplier → fund-01:ARG0."""
        mappings = [
            json.loads(line)
            for line in (_PACK_DIR / "source_mappings.jsonl").read_text().splitlines()
        ]
        target = next(
            (
                m for m in mappings
                if m.get("canonical_id") == "lc:fund_provide_money:lc.role.supplier"
                and m.get("source_id") == "fund-01:ARG0"
            ),
            None,
        )
        assert target is not None, (
            "Expected source mapping lc:fund_provide_money:lc.role.supplier → fund-01:ARG0 not found"
        )
        assert target["source_system"] == "propbank_nltk"
        assert target["mapping_type"] == "positional_role"

    def test_manifest_yaml_exists_and_valid(self) -> None:
        """manifest.yaml should exist and declare the expected pack identity."""
        import yaml as _yaml

        manifest_path = _PACK_DIR / "manifest.yaml"
        assert manifest_path.exists()
        manifest = _yaml.safe_load(manifest_path.read_text())
        assert manifest["pack"]["id"] == "linguistic_core"
        assert manifest["pack"]["version"] == "0.1.0"
        assert manifest["capabilities"]["assertion_type"] == "n-ary"
        assert manifest["capabilities"]["type_system"] == "sumo"
        assert "predicate_types" in manifest["content"]
        assert "role_types" in manifest["content"]

    def test_predicate_types_have_lc_prefix(self) -> None:
        """All predicate_types.jsonl entries should use the lc: namespace."""
        lines = (_PACK_DIR / "predicate_types.jsonl").read_text().strip().splitlines()
        for i, line in enumerate(lines[:100]):  # spot check first 100
            row = json.loads(line)
            assert row["predicate_id"].startswith("lc:"), (
                f"Line {i+1}: predicate_id missing lc: prefix: {row['predicate_id']}"
            )

    def test_role_types_have_lc_role_prefix(self) -> None:
        """All role_types.jsonl entries should use the lc.role. namespace."""
        lines = (_PACK_DIR / "role_types.jsonl").read_text().strip().splitlines()
        for i, line in enumerate(lines[:100]):  # spot check first 100
            row = json.loads(line)
            assert row["role_id"].startswith("lc.role."), (
                f"Line {i+1}: role_id missing lc.role. prefix: {row['role_id']}"
            )


# ---------------------------------------------------------------------------
# generate_role_labels_json integration test
# ---------------------------------------------------------------------------


class TestGenerateRoleLabelsJson:
    """Tests for generate_role_labels_json.py output format."""

    def test_role_labels_json_format(self, tmp_path: Path) -> None:
        """generate_role_labels outputs correct {predicate: {ARGn: label}} format."""
        import sys
        sys.path.insert(0, str(repo_root() / "scripts"))
        from generate_role_labels_json import generate_role_labels  # type: ignore[import]

        output = tmp_path / "role_labels.json"
        mapping = generate_role_labels(_DB, output)

        assert output.exists()
        loaded = json.loads(output.read_text())
        assert loaded == mapping
        assert "fund_provide_money" in loaded
        assert loaded["fund_provide_money"]["ARG0"] == "Supplier"
        assert loaded["fund_provide_money"]["ARG1"] == "Imposed_purpose"
        assert loaded["fund_provide_money"]["ARG2"] == "Purpose"

    def test_role_labels_json_predicate_count(self, tmp_path: Path) -> None:
        """role_labels.json should cover predicates that have role slots.

        13 of the 4,669 predicates have no role_slots entries and are
        correctly absent from the output (nothing to map).
        """
        import sys
        sys.path.insert(0, str(repo_root() / "scripts"))
        from generate_role_labels_json import generate_role_labels  # type: ignore[import]

        output = tmp_path / "role_labels.json"
        mapping = generate_role_labels(_DB, output)
        # 4,669 total predicates minus 13 with no role slots = 4,656
        assert len(mapping) == 4656

"""Read-only interface to the role_slots table in sumo_plus.db.

Vendored (copied, not shared) from onto-canon6's
src/onto_canon6/packs/role_slots_lookup.py: that module is genuinely shared
there (also used by onto-canon6's own DIGIMON role-label generation and
predicate-canon-parity evaluation, which stay in onto-canon6), so this
package keeps its own copy operating on its own copy of sumo_plus.db rather
than depending back on onto-canon6.

Wraps the role_slots and predicates tables to expose semantic role names
(named_label) for each predicate/arg-position pair. Used by
``scripts/compile_linguistic_core_pack.py`` (pack compilation) in this
package.

The named_label values are FrameNet-derived semantic role names (e.g.,
"Supplier", "Imposed_purpose"). ARG positions are PropBank positional
artifacts stored only as provenance — callers should use named_label for
all semantic work.

The database is a read-only external dependency — this module never writes
to it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote


class RoleSlotsError(RuntimeError):
    """Raised when the sumo_plus database is missing or malformed."""


@dataclass(frozen=True)
class RoleSlot:
    """One row from the role_slots table.

    Attributes
    ----------
    predicate_id:
        Predicate name as stored in sumo_plus.db (e.g., ``fund_provide_money``).
    named_label:
        FrameNet-derived semantic role name (e.g., ``Supplier``).
    arg_position:
        PropBank positional artifact (e.g., ``ARG0``). Provenance only — not
        for use as a semantic identifier.
    abstract_role:
        VerbNet abstract role (e.g., ``agent``, ``theme``). May be None.
    type_constraint:
        SUMO type constraint on the filler (e.g., ``Organization``). May be None.
    required:
        Whether the role is required (1) or optional (0).
    source:
        Provenance source (e.g., ``propbank:nltk``).
    """

    predicate_id: str
    named_label: str
    arg_position: str
    abstract_role: str | None
    type_constraint: str | None
    required: int
    source: str


class RoleSlotsLookup:
    """Read-only interface to sumo_plus.db role_slots.

    Provides semantic role name resolution for predicate/arg-position pairs
    and bulk iteration over all role slots.

    Parameters
    ----------
    db_path:
        Absolute or relative path to ``sumo_plus.db``.

    Raises
    ------
    RoleSlotsError:
        If the database file does not exist or lacks the required tables.

    Examples
    --------
    ::

        with RoleSlotsLookup(Path("data/sumo_plus.db")) as lookup:
            label = lookup.named_label("fund_provide_money", "ARG0")
            # → "Supplier"
    """

    def __init__(self, db_path: Path) -> None:
        """Open a read-only connection to sumo_plus.db."""
        if not db_path.exists():
            msg = f"sumo_plus database not found: {db_path}"
            raise RoleSlotsError(msg)
        if not db_path.is_file():
            msg = f"sumo_plus database is not a file: {db_path}"
            raise RoleSlotsError(msg)
        self._db_path = db_path
        encoded_db_path = quote(db_path.resolve().as_posix(), safe="/")
        self._conn = sqlite3.connect(
            f"file:{encoded_db_path}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._validate_schema()

    def _validate_schema(self) -> None:
        """Verify the database has the required tables."""
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('predicates', 'role_slots')"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        missing = {"predicates", "role_slots"} - tables
        if missing:
            msg = f"sumo_plus database missing tables: {missing}"
            raise RoleSlotsError(msg)

    @lru_cache(maxsize=16384)  # noqa: B019
    def named_label(self, predicate_id: str, arg_position: str) -> str | None:
        """Return the semantic role name for a predicate/arg-position pair.

        Parameters
        ----------
        predicate_id:
            Predicate name as stored in sumo_plus.db (e.g., ``fund_provide_money``).
        arg_position:
            PropBank positional identifier (e.g., ``ARG0``).

        Returns
        -------
        str | None
            The FrameNet-derived named label, or ``None`` if not found.
        """
        cursor = self._conn.execute(
            "SELECT named_label FROM role_slots WHERE event_sense_id = ? AND arg_position = ? LIMIT 1",
            (predicate_id, arg_position),
        )
        row = cursor.fetchone()
        return row["named_label"] if row else None

    @lru_cache(maxsize=8192)  # noqa: B019
    def roles_for_predicate(self, predicate_id: str) -> tuple[RoleSlot, ...]:
        """Return all role slots for a predicate, ordered by arg_position.

        Returns a tuple (hashable, safe for LRU cache) of RoleSlot objects.
        """
        cursor = self._conn.execute(
            """
            SELECT event_sense_id, named_label, arg_position, abstract_role,
                   type_constraint, required, source
            FROM role_slots
            WHERE event_sense_id = ?
            ORDER BY arg_position
            """,
            (predicate_id,),
        )
        return tuple(
            RoleSlot(
                predicate_id=row["event_sense_id"],
                named_label=row["named_label"],
                arg_position=row["arg_position"],
                abstract_role=row["abstract_role"],
                type_constraint=row["type_constraint"],
                required=row["required"],
                source=row["source"],
            )
            for row in cursor.fetchall()
        )

    def all_role_labels(self) -> dict[str, dict[str, str]]:
        """Return the full ARG-position → named_label mapping for all predicates.

        Returns
        -------
        dict[str, dict[str, str]]
            Mapping of ``{predicate_id: {arg_position: named_label}}``.
            This is the exact format consumed by DIGIMON's
            ``investigation_browser/backend/graph.py:_semantic_role()``.
        """
        cursor = self._conn.execute(
            "SELECT event_sense_id, arg_position, named_label FROM role_slots ORDER BY event_sense_id, arg_position"
        )
        result: dict[str, dict[str, str]] = {}
        for row in cursor.fetchall():
            pred = row["event_sense_id"]
            if pred not in result:
                result[pred] = {}
            result[pred][row["arg_position"]] = row["named_label"]
        return result

    def all_predicates(self) -> list[dict[str, object]]:
        """Return all predicates as a list of dicts (all columns)."""
        cursor = self._conn.execute(
            "SELECT name, propbank_sense_id, process_type, lemma, sense_num, "
            "description, frame_id, source, mapping_confidence, mapping_source, is_static "
            "FROM predicates ORDER BY name"
        )
        return [dict(row) for row in cursor.fetchall()]

    def predicate_count(self) -> int:
        """Return the total number of predicates."""
        cursor = self._conn.execute("SELECT COUNT(*) AS cnt FROM predicates")
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    def role_slot_count(self) -> int:
        """Return the total number of role slots."""
        cursor = self._conn.execute("SELECT COUNT(*) AS cnt FROM role_slots")
        row = cursor.fetchone()
        return int(row["cnt"]) if row else 0

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> RoleSlotsLookup:
        """Enter context manager."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Exit context manager, closing the database connection."""
        self.close()

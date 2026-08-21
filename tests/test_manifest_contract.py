from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.catalog import load_catalog
from app.manifest import build_manifest
from app.models import DocumentClassification, LogicalDocument, ClassifiedDocument, PipelineError
from app.pdf_inventory import PersonInventory, SourceFile
from app.policy import (
    CLASSIFICATION_KIND_DUPLICATE,
    CLASSIFICATION_KIND_SUPPORTING,
    DATE_PRECISION_DAY,
    DATE_PRECISION_MONTH,
    DATE_PRECISION_UNKNOWN,
    DATE_PRECISION_YEAR,
)
from app.qc import QCReport
from app.state import StateRegistry, STATE_SCHEMA_VERSION


def _inventory() -> PersonInventory:
    source = SourceFile(Path("P.pdf"), "P.pdf", "a" * 64, 1, 1)
    return PersonInventory("P", Path("input/P"), [source])


def _doc(**policy) -> ClassifiedDocument:
    logical = LogicalDocument("P.pdf", [1], 1)
    classification = DocumentClassification(
        type_id=policy.pop("type_id", "87"),
        confidence=0.99,
        document_date=policy.pop("document_date", "2023-05-19"),
        title_short="Quyết định tổng hợp",
    )
    return ClassifiedDocument(
        logical,
        classification,
        target_file=policy.pop("target_file", "87.Quyet_dinh.pdf"),
        target_dir="output",
        **policy,
    )


def _manifest(doc: ClassifiedDocument) -> dict:
    return build_manifest(
        load_catalog(), _inventory(), [doc], QCReport(), mode="dry-run",
        provider={"name": "test"},
    )


def test_manifest_taxonomy_87_emits_policy_fields():
    row = _manifest(_doc(subtype="promotion_salary", date_precision=DATE_PRECISION_DAY))["documents"][0]
    assert row["logical_document_id"] == "P.pdf#1"
    assert row["classification_kind"] == "TAXONOMY"
    assert row["type_id"] == "87"
    assert row["subtype"] == "promotion_salary"
    assert row["document_date"] == "2023-05-19"
    assert row["date_precision"] == DATE_PRECISION_DAY
    assert row["duplicate_of"] is None


def test_manifest_supporting_has_null_type_and_unknown_date():
    row = _manifest(
        _doc(
            type_id="UNKNOWN", classification_kind=CLASSIFICATION_KIND_SUPPORTING,
            subtype=None, document_date=None, date_precision=DATE_PRECISION_UNKNOWN,
            target_file="SUPPORTING.Phu_luc.pdf",
        )
    )["documents"][0]
    assert row["classification_kind"] == CLASSIFICATION_KIND_SUPPORTING
    assert row["type_id"] is None
    assert row["subtype"] is None
    assert row["document_date"] is None
    assert row["date_precision"] == DATE_PRECISION_UNKNOWN
    assert row["duplicate_of"] is None


def test_manifest_duplicate_has_relation_and_no_second_target():
    row = _manifest(
        _doc(
            type_id="UNKNOWN", classification_kind=CLASSIFICATION_KIND_DUPLICATE,
            subtype=None, document_date=None, date_precision=DATE_PRECISION_UNKNOWN,
            duplicate_of="original-logical-id", target_file=None,
        )
    )["documents"][0]
    assert row["classification_kind"] == CLASSIFICATION_KIND_DUPLICATE
    assert row["type_id"] is None
    assert row["duplicate_of"] == "original-logical-id"
    assert row["target_file"] is None


@pytest.mark.parametrize(
    ("date", "precision"),
    [("2023-05-19", DATE_PRECISION_DAY), ("2023-05", DATE_PRECISION_MONTH),
     ("2023", DATE_PRECISION_YEAR), (None, DATE_PRECISION_UNKNOWN)],
)
def test_manifest_date_precision_roundtrip(date, precision):
    row = _manifest(_doc(document_date=date, date_precision=precision))["documents"][0]
    assert row["document_date"] == date
    assert row["date_precision"] == precision


@pytest.mark.parametrize(
    ("kind", "type_id", "subtype", "date", "precision"),
    [("TAXONOMY", "04", "promotion_salary", "2023-05-19", DATE_PRECISION_DAY),
     (CLASSIFICATION_KIND_SUPPORTING, "UNKNOWN", "promotion_salary", None, DATE_PRECISION_UNKNOWN)],
)
def test_manifest_rejects_invalid_subtype_combinations(kind, type_id, subtype, date, precision):
    with pytest.raises(PipelineError):
        _manifest(_doc(
            type_id=type_id, classification_kind=kind, subtype=subtype,
            document_date=date, date_precision=precision,
            duplicate_of="original" if kind == CLASSIFICATION_KIND_DUPLICATE else None,
        ))


@pytest.mark.parametrize(
    ("date", "precision"),
    [(None, DATE_PRECISION_DAY), ("2023-11", DATE_PRECISION_DAY),
     ("2023", DATE_PRECISION_MONTH), ("2023-11-01", DATE_PRECISION_UNKNOWN)],
)
def test_manifest_rejects_invalid_date_precision(date, precision):
    with pytest.raises(PipelineError):
        _manifest(_doc(document_date=date, date_precision=precision))


def _create_old_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            source_hash TEXT PRIMARY KEY, source_filename TEXT NOT NULL,
            source_relative_path TEXT NOT NULL, person_folder TEXT NOT NULL,
            page_count INTEGER NOT NULL, status TEXT NOT NULL,
            first_seen_at TEXT NOT NULL, processing_started_at TEXT,
            processed_at TEXT, logical_document_count INTEGER, manifest_path TEXT,
            last_error TEXT, pipeline_version TEXT NOT NULL, taxonomy_version TEXT,
            analysis_schema_version TEXT, last_seen_path TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE logical_documents (
            logical_document_id TEXT PRIMARY KEY,
            source_hash TEXT NOT NULL REFERENCES sources(source_hash),
            source_pages TEXT NOT NULL, type_id TEXT NOT NULL, confidence REAL NOT NULL,
            document_date TEXT, date_confidence REAL NOT NULL, title_short TEXT,
            segmentation_flags TEXT NOT NULL, classification_status TEXT NOT NULL,
            classification_reasons TEXT NOT NULL, resolution_status TEXT NOT NULL,
            resolved_type_id TEXT, resolved_document_date TEXT, resolved_by TEXT,
            resolved_at TEXT, current_target_filename TEXT, target_dir TEXT,
            sequence_index INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO sources VALUES
        ('h1', 'old.pdf', 'input/P/old.pdf', 'P', 1, 'ANALYZED_PENDING_APPLY',
         't', NULL, NULL, NULL, NULL, NULL, 'v1', 'tx', '1.0', 'input/P/old.pdf', 't');
        INSERT INTO logical_documents VALUES
        ('d1', 'h1', '[1]', '04', 0.99, NULL, 0.0, 'Old', '[]',
         'AUTO', '[]', 'AUTO_RESOLVED', NULL, NULL, NULL, NULL, NULL, NULL,
         NULL, 't', 't');
        """
    )
    conn.commit()
    conn.close()


def test_old_schema_migration_preserves_rows_and_is_idempotent(tmp_path: Path):
    db = tmp_path / "old.db"
    _create_old_schema(db)
    with StateRegistry(db) as registry:
        assert registry.schema_version == STATE_SCHEMA_VERSION == 2
        row = registry.get_logical_document("d1")
        assert row is not None
        assert row.type_id == "04"
        assert row.effective_date_precision == DATE_PRECISION_UNKNOWN
        columns = {r[1] for r in registry._conn.execute("PRAGMA table_info(logical_documents)")}
        assert {"classification_kind", "subtype", "duplicate_of", "date_precision",
                "resolved_subtype", "resolved_date_precision"} <= columns
    with StateRegistry(db) as registry:
        assert registry.schema_version == 2
        assert registry.get_logical_document("d1").type_id == "04"


def test_old_schema_migration_rolls_back_if_alter_fails(tmp_path: Path, monkeypatch):
    db = tmp_path / "rollback.db"
    _create_old_schema(db)
    original = StateRegistry._LOGICAL_DOC_NEW_COLUMNS
    monkeypatch.setattr(
        StateRegistry,
        "_LOGICAL_DOC_NEW_COLUMNS",
        original + (("bad; DROP TABLE sources; --", "TEXT"),),
    )
    with pytest.raises(sqlite3.Error):
        StateRegistry(db)

    conn = sqlite3.connect(db)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(logical_documents)")}
    assert "classification_kind" not in columns
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
    conn.close()

    # Restoring the migration definition succeeds and remains idempotent.
    monkeypatch.undo()
    with StateRegistry(db) as registry:
        assert registry.schema_version == STATE_SCHEMA_VERSION

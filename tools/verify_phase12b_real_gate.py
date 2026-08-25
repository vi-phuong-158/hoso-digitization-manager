"""Create PII-free evidence for the Phase 12 real-data provenance gate.

This tool refuses to call a root inside the checkout an external operational
workspace. It emits aggregate counts and an aggregate digest only: no names,
paths, individual source hashes, extracted text, or PDF data are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parents[1]


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(dataset_root: Path) -> dict[str, int | str]:
    files = sorted(path for path in dataset_root.rglob("*") if path.is_file())
    pdfs = [path for path in files if path.suffix.lower() == ".pdf"]
    aggregate = hashlib.sha256()
    pages = 0
    unreadable = 0
    for pdf in pdfs:
        anonymized_id = hashlib.sha256(pdf.relative_to(dataset_root).as_posix().encode("utf-8")).hexdigest()[:12]
        aggregate.update(f"{anonymized_id}:{_sha256(pdf)}\n".encode("ascii"))
        try:
            pages += len(PdfReader(str(pdf)).pages)
        except Exception:
            unreadable += 1
    return {
        "folder_count": sum(1 for path in dataset_root.iterdir() if path.is_dir()),
        "file_count": len(files),
        "pdf_count": len(pdfs),
        "page_count": pages,
        "total_bytes": sum(path.stat().st_size for path in files),
        "aggregate_hash_evidence": aggregate.hexdigest(),
        "unreadable_pdf_count": unreadable,
    }


def audit(dataset_root: Path) -> dict[str, int | str | bool]:
    root = dataset_root.resolve()
    inside_repo = _inside(root, REPO_ROOT.resolve())
    components = {part.lower() for part in root.parts}
    fixture = bool(components & {"fixtures", "tests", "test_cases", "synthetic"})
    golden = "golden" in components
    return {
        "dataset_origin": "external_operational_workspace" if not inside_repo else "unverified_workspace_inside_repository",
        "dataset_inside_git_repo": inside_repo,
        "dataset_generated_by_test_fixture": fixture,
        "dataset_generated_by_golden_fixture": golden,
        "source_root": "<EXTERNAL_OPERATIONAL_ROOT>" if not inside_repo else "<REPOSITORY_WORKSPACE_ROOT>",
        **inventory(root),
        "real_data_gate": "PASS" if not inside_repo and not fixture and not golden else "BLOCKED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create anonymized Phase 12 real-data evidence.")
    parser.add_argument("dataset_root", type=Path, help="External operational data root; never a repository fixture.")
    parser.add_argument("--output", type=Path, help="Optional PII-free JSON evidence output, normally outside Git.")
    args = parser.parse_args()
    record = audit(args.dataset_root)
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if record["real_data_gate"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
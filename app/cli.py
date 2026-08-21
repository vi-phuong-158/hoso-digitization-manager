"""CLI vận hành.

    python -m app.cli process "input/<TEN_NGUOI>"            # mặc định dry-run, incremental
    python -m app.cli process "input/<TEN_NGUOI>" --apply
    python -m app.cli status "input/<TEN_NGUOI>"
    python -m app.cli inventory "input/<TEN_NGUOI>"
    python -m app.cli import-state "input/<TEN_NGUOI>"
    python -m app.cli state-export
    python -m app.cli test-golden
    python -m app.cli providers

Mặc định luôn là dry-run: phải gõ rõ --apply mới ghi file.
Mặc định luôn incremental: nguồn đã PROCESSED không bị đọc lại (dùng --no-state để tắt).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .catalog import load_catalog
from .golden import run_all_golden
from .incremental import scan_person_folder
from .models import MODE_APPLY, MODE_DRY_RUN, PipelineError
from .pdf_inventory import build_inventory
from .pipeline import PipelineResult, Workspace, process_person_folder
from .state import StateRegistry
from .state_import import import_person_folder
from .vision_adapter import available_providers

EXIT_OK = 0
EXIT_REVIEW = 0  # REVIEW là kết quả hợp lệ, không phải lỗi
EXIT_BLOCKED = 2
EXIT_ERROR = 3


def _stdout_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:
            pass


def _provider_config(args: argparse.Namespace) -> dict:
    cfg: dict = {}
    if getattr(args, "fixture_root", None):
        cfg["fixture_root"] = args.fixture_root
    if getattr(args, "analysis_root", None):
        cfg["analysis_root"] = args.analysis_root
    return cfg


def _workspace(args: argparse.Namespace) -> Workspace:
    return Workspace(Path(args.root)) if args.root else Workspace.discover()


def print_summary(result: PipelineResult) -> None:
    inv = result.inventory
    print(f"Hồ sơ            : {result.person_folder}")
    print(f"Chế độ           : {result.mode}")
    print(f"Provider         : {json.dumps(result.manifest['provider'], ensure_ascii=False)}")
    print(f"File nguồn       : {len(inv.sources)}")
    for s in inv.sources:
        print(f"    - {s.name}  ({s.pages} trang, sha256 {s.sha256[:12]}…)")
    print(f"Tổng số trang    : {inv.total_pages}")

    if result.incremental is not None:
        c = result.incremental.counts()
        print("\n--- Incremental ---")
        print(f"  Mới bổ sung (NEW)      : {c['NEW']}")
        print(f"  Đã xử lý trước (SKIP)  : {c['ALREADY_PROCESSED']}")
        print(f"  Đang chờ review        : {c['REVIEW_PENDING']}")
        print(f"  Lỗi cũ                 : {c['FAILED_PREVIOUSLY']}")
        print(f"  Bị gián đoạn           : {c['INTERRUPTED']}")
        print(f"  Trùng nội dung         : {c['DUPLICATE_SOURCE']}")
        for d in result.incremental.decisions:
            if d.output_mismatch:
                print(f"  CẢNH BÁO STATE_OUTPUT_MISMATCH: {d.source.name}: {d.output_mismatch_detail}")

    print(f"\nLogical document (lượt này) : {len(result.documents)}")
    auto = [d for d in result.documents if d.final_status == "AUTO"]
    review = [d for d in result.documents if d.final_status == "REVIEW"]
    print(f"AUTO             : {len(auto)}")
    print(f"REVIEW           : {len(review)}")

    if auto:
        print("\n--- AUTO (sẽ ghi vào output/) ---")
        for d in sorted(auto, key=lambda x: (x.classification.type_id, x.target_file or "")):
            print(
                f"  {d.document.source_file} trang {d.document.source_pages} "
                f"-> [{d.classification.type_id}] {d.target_file}"
                f"  (conf {d.classification.confidence:.2f}"
                f"{', ngày ' + d.classification.document_date if d.classification.document_date else ''})"
            )
    if review:
        print("\n--- REVIEW (cần người quyết định) ---")
        for d in sorted(review, key=lambda x: (x.document.source_file, x.document.source_pages[0])):
            reasons = sorted(set(d.classification_reasons) | set(d.final_reasons))
            print(
                f"  {d.document.source_file} trang {d.document.source_pages} "
                f"-> [{d.classification.type_id}] {d.classification.title_short or ''}"
                f"  (conf {d.classification.confidence:.2f}) lý do: {', '.join(reasons)}"
            )

    print("\n--- QC ---")
    if not result.qc.checks:
        print("  (không có gì mới cần kiểm - không có nguồn nào được xử lý lượt này)")
    for c in result.qc.checks:
        print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")

    if result.write_result is not None:
        w = result.write_result
        print("\n--- Ghi file ---")
        print(f"  đã ghi mới       : {len(w.written)}")
        print(f"  bỏ qua (đã đúng) : {len(w.skipped_identical)}")
        for c in w.conflicts:
            print(f"  XUNG ĐỘT: {c}")
        for s in w.stale_in_output:
            print(f"  file lạ còn sót (không đụng tới): {s}")

    for n in result.notes:
        print(f"\nGhi chú: {n}")
    if result.manifest_path:
        print(f"\nManifest: {result.manifest_path}")
    print(f"\nTRẠNG THÁI: {result.status}")


def cmd_process(args: argparse.Namespace) -> int:
    mode = MODE_APPLY if args.apply else MODE_DRY_RUN
    ws = _workspace(args)
    registry: Optional[StateRegistry] = None
    if not args.no_state:
        registry = StateRegistry(ws.state_db_path)
    try:
        result = process_person_folder(
            Path(args.folder),
            mode=mode,
            provider_name=args.provider,
            provider_config=_provider_config(args),
            workspace=ws,
            force=args.force,
            state_registry=registry,
            retry_review=args.retry_review,
            retry_failed=args.retry_failed,
        )
    finally:
        if registry is not None:
            registry.close()

    if args.json:
        print(json.dumps(result.manifest, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_summary(result)
    if result.status in ("BLOCKED_QC", "BLOCKED_RUNTIME"):
        return EXIT_BLOCKED
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    """Chỉ đọc: không mutate registry, không gọi provider, không mở nội dung PDF."""
    ws = _workspace(args)
    inv = build_inventory(Path(args.folder))
    output_dir = ws.output / inv.person_folder
    review_dir = ws.review / inv.person_folder
    with StateRegistry(ws.state_db_path) as registry:
        scan = scan_person_folder(
            inv, registry, mode=MODE_DRY_RUN, output_dir=output_dir, review_dir=review_dir
        )
    if args.json:
        print(json.dumps(scan.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"TOTAL: {len(scan.decisions)}")
        c = scan.counts()
        print(f"NEW: {c['NEW']}")
        print(f"PROCESSED: {c['ALREADY_PROCESSED']}")
        print(f"REVIEW_REQUIRED: {c['REVIEW_PENDING']}")
        print(f"FAILED: {c['FAILED_PREVIOUSLY']}")
        if c["INTERRUPTED"]:
            print(f"INTERRUPTED: {c['INTERRUPTED']}")
        if c["DUPLICATE_SOURCE"]:
            print(f"DUPLICATE_SOURCE: {c['DUPLICATE_SOURCE']}")
        for d in scan.decisions:
            if d.output_mismatch:
                print(f"STATE_OUTPUT_MISMATCH: {d.source.name}: {d.output_mismatch_detail}")
    return EXIT_OK


def cmd_import_state(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    with StateRegistry(ws.state_db_path) as registry:
        report = import_person_folder(Path(args.folder), registry, workspace=ws)
    print(report.summary_text())
    return EXIT_OK


def cmd_state_export(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    with StateRegistry(ws.state_db_path) as registry:
        data = registry.export_json()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"Đã ghi state export: {args.out}")
    else:
        print(text)
    return EXIT_OK


def cmd_inventory(args: argparse.Namespace) -> int:
    inv = build_inventory(Path(args.folder))
    print(json.dumps(inv.as_dict(), ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_test_golden(args: argparse.Namespace) -> int:
    reports = run_all_golden(
        Path(args.root) if args.root else None,
        provider_name=args.provider,
        provider_config=_provider_config(args),
    )
    failed = 0
    for r in reports:
        print(r.summary())
        for f in r.failures:
            print(f"   FAIL {f}")
        for t in r.title_diffs:
            print(f"   (thông tin) tiêu đề khác diễn đạt - không tính lỗi: {t}")
        if not r.passed:
            failed += 1
    print()
    if failed:
        print(f"GOLDEN ACCEPTANCE: FAIL ({failed}/{len(reports)} file golden đỏ)")
        return EXIT_BLOCKED
    print(f"GOLDEN ACCEPTANCE: PASS ({len(reports)}/{len(reports)} file golden xanh)")
    return EXIT_OK


def cmd_providers(args: argparse.Namespace) -> int:
    print("Provider đã đăng ký:", ", ".join(available_providers()))
    cat = load_catalog()
    print(f"Catalog: {cat.path} (schema {cat.schema_version}, {len(cat)} loại)")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="app.cli", description="Pipeline số hóa hồ sơ đảng viên")
    p.add_argument("--root", default=None, help="Thư mục gốc repo (mặc định: tự dò)")
    sub = p.add_subparsers(dest="command", required=True)

    def add_provider_args(sp: argparse.ArgumentParser, default_provider: str = "agent") -> None:
        sp.add_argument(
            "--provider",
            default=default_provider,
            help="agent (Antigravity runtime, mặc định) | fixture (chỉ cho test/golden)",
        )
        sp.add_argument("--fixture-root", default=None, help="Thư mục fixture (provider fixture)")
        sp.add_argument(
            "--analysis-root", default=None, help="Thư mục JSON phân tích của Agent (provider agent)"
        )

    sp = sub.add_parser("process", help="Xử lý một thư mục hồ sơ (mặc định incremental)")
    sp.add_argument("folder")
    g = sp.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True, help="Mặc định")
    g.add_argument("--apply", action="store_true", help="Thực sự ghi output/review")
    sp.add_argument("--force", action="store_true", help="Ghi đè khi file đích khác nội dung")
    sp.add_argument("--json", action="store_true", help="In manifest JSON thay vì summary")
    sp.add_argument(
        "--retry-review", action="store_true",
        help="Xử lý lại các nguồn đang REVIEW_REQUIRED thay vì SKIP mặc định",
    )
    sp.add_argument(
        "--retry-failed", action="store_true",
        help="Xử lý lại các nguồn FAILED/INTERRUPTED thay vì SKIP mặc định",
    )
    sp.add_argument(
        "--no-state", action="store_true",
        help="Tắt incremental processing - xử lý lại TOÀN BỘ nguồn (không dùng state registry)",
    )
    add_provider_args(sp, default_provider="agent")
    sp.set_defaults(func=cmd_process)

    sp = sub.add_parser("status", help="Xem trạng thái NEW/PROCESSED/REVIEW/FAILED (chỉ đọc)")
    sp.add_argument("folder")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("inventory", help="Chỉ liệt kê file nguồn + SHA-256")
    sp.add_argument("folder")
    sp.set_defaults(func=cmd_inventory)

    sp = sub.add_parser(
        "import-state",
        help="Nạp lại state PROCESSED từ manifest/output đã có sẵn (migration, xem LIMITATIONS.md)",
    )
    sp.add_argument("folder")
    sp.set_defaults(func=cmd_import_state)

    sp = sub.add_parser("state-export", help="Xuất toàn bộ state registry ra JSON (backup/kiểm tra)")
    sp.add_argument("--out", default=None, help="Ghi ra file thay vì in stdout")
    sp.set_defaults(func=cmd_state_export)

    sp = sub.add_parser("test-golden", help="Chạy golden acceptance")
    add_provider_args(sp, default_provider="fixture")
    sp.set_defaults(func=cmd_test_golden)

    sp = sub.add_parser("providers", help="Liệt kê provider/catalog")
    sp.set_defaults(func=cmd_providers)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    _stdout_utf8()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except PipelineError as exc:
        print(f"LỖI PIPELINE: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

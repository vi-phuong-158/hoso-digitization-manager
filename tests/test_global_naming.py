"""Global cross-run naming (Phase F/G/H/I): xếp toàn cục, tie-break, rename plan."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.global_naming import (
    NameableDoc,
    R_MISSING_RELIABLE_DATE,
    build_rename_plan,
    compute_global_assignment,
    execute_rename_plan,
    has_collisions,
)
from app.models import PipelineError


def doc(id_, date, title="X", h=None, pages=(1,), date_conf=0.95):
    return NameableDoc(id_, h or id_, tuple(pages), date, date_conf, title)


def test_type_moi_lan_dau_ra_ten_tran(catalog):
    assign, reasons = compute_global_assignment(catalog, "05", [doc("a", "2018-08-19")])
    assert reasons == []
    assert assign[0].sequence_index is None
    assert assign[0].target_filename == "05.Quyet_dinh_ket_nap_dang_vien.pdf"


def test_them_document_cung_type_sequence_global_dung(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", "2015-11-03"), doc("c", "2015-11-10")]
    assign, reasons = compute_global_assignment(catalog, "87", docs)
    assert reasons == []
    got = {a.logical_document_id: a.sequence_index for a in assign}
    assert got == {"a": 1, "b": 2, "c": 3}


def test_them_document_moi_hon_append_dung(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", "2015-11-03"), doc("c", "2015-11-10"), doc("d", "2016-01-01")]
    assign, _ = compute_global_assignment(catalog, "87", docs)
    got = {a.logical_document_id: a.sequence_index for a in assign}
    assert got["d"] == 4


def test_them_document_cu_hon_insert_dung(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", "2015-11-03"), doc("c", "2015-11-10")]
    docs.append(doc("mid", "2015-10-15"))
    assign, _ = compute_global_assignment(catalog, "87", docs)
    got = {a.logical_document_id: a.sequence_index for a in assign}
    assert got == {"a": 1, "mid": 2, "b": 3, "c": 4}


def test_same_date_tie_break_deterministic(catalog):
    docs = [doc("z", "2015-01-01", title="Zebra"), doc("a", "2015-01-01", title="Alpha")]
    assign, reasons = compute_global_assignment(catalog, "86", docs)
    assert reasons == []
    got = {a.logical_document_id: a.sequence_index for a in assign}
    assert got == {"a": 1, "z": 2}  # "alpha" < "zebra"


def test_same_date_ket_qua_khong_doi_khi_dao_thu_tu_scan(catalog):
    base = [doc("a", "2015-09-23"), doc("b", "2015-11-03"), doc("c", "2015-11-10"), doc("mid", "2015-10-15")]
    baseline = {a.logical_document_id: a.sequence_index for a in compute_global_assignment(catalog, "87", base)[0]}
    for _ in range(5):
        shuffled = list(base)
        random.shuffle(shuffled)
        got = {a.logical_document_id: a.sequence_index for a in compute_global_assignment(catalog, "87", shuffled)[0]}
        assert got == baseline


def test_thieu_ngay_khong_xep_duoc(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", None, date_conf=0.0)]
    assign, reasons = compute_global_assignment(catalog, "87", docs)
    assert assign == []
    assert R_MISSING_RELIABLE_DATE in reasons


def test_rerun_khong_doi_gi_thi_khong_co_rename_op(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", "2015-11-03")]
    assign, _ = compute_global_assignment(catalog, "87", docs)
    current = {a.logical_document_id: (a.target_filename, "output") for a in assign}
    ops = build_rename_plan(current, assign)
    assert ops == []  # rerun không renumber vô ích


def test_khong_co_trung_dich_trong_plan(catalog):
    docs = [doc("a", "2015-09-23"), doc("b", "2015-11-03"), doc("mid", "2015-10-15")]
    assign, _ = compute_global_assignment(catalog, "87", docs)
    current = {"a": ("87.X.1.pdf", "output"), "b": ("87.X.2.pdf", "output")}
    ops = build_rename_plan(current, assign)
    assert has_collisions(ops) == []


def test_source_filename_doi_nhung_hash_giong_thi_id_khong_doi():
    d_old = doc("stable-id", "2015-09-23", h="samehash")
    d_new = doc("stable-id", "2015-09-23", h="samehash")
    assert d_old.logical_document_id == d_new.logical_document_id == "stable-id"


# ---------------- thực thi filesystem ----------------
@pytest.fixture()
def dirs(tmp_path: Path):
    out, rev = tmp_path / "output", tmp_path / "review"
    out.mkdir()
    rev.mkdir()
    return out, rev


def test_execute_hoan_vi_khong_mat_du_lieu(dirs):
    out, rev = dirs
    (out / "A.pdf").write_bytes(b"AAA")
    (out / "B.pdf").write_bytes(b"BBB")
    from app.global_naming import RenameOp

    ops = [
        RenameOp("x1", "MOVE", "A.pdf", "output", "B.pdf", "output"),
        RenameOp("x2", "MOVE", "B.pdf", "output", "A.pdf", "output"),
    ]
    execute_rename_plan(out, rev, ops, source_path_of={}, pages_of={})
    assert (out / "A.pdf").read_bytes() == b"BBB"
    assert (out / "B.pdf").read_bytes() == b"AAA"


def test_execute_that_bai_khong_lam_mat_file_cu(dirs):
    out, rev = dirs
    (out / "C.pdf").write_bytes(b"CCC")
    (out / "D.pdf").mkdir()  # ép rename thất bại (đích là thư mục)
    from app.global_naming import RenameOp

    ops = [RenameOp("y1", "MOVE", "C.pdf", "output", "D.pdf", "output")]
    with pytest.raises(PipelineError):
        execute_rename_plan(out, rev, ops, source_path_of={}, pages_of={})
    assert (out / "C.pdf").is_file()
    assert (out / "C.pdf").read_bytes() == b"CCC"


def test_execute_rename_fault_mid_permutation_rolls_back_and_retries(dirs, monkeypatch):
    """A failure after temporary staging restores every canonical filename."""
    out, rev = dirs
    (out / "A.pdf").write_bytes(b"AAA")
    (out / "B.pdf").write_bytes(b"BBB")
    from app.global_naming import RenameOp

    ops = [
        RenameOp("x1", "MOVE", "A.pdf", "output", "B.pdf", "output"),
        RenameOp("x2", "MOVE", "B.pdf", "output", "A.pdf", "output"),
    ]
    real_rename = Path.rename

    def interrupted(path: Path, target):
        if path.parent.name == ".rename_tmp" and Path(target).name == "A.pdf":
            raise OSError("injected finalize failure")
        return real_rename(path, target)

    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(PipelineError, match="rollback"):
        execute_rename_plan(out, rev, ops, source_path_of={}, pages_of={})
    assert (out / "A.pdf").read_bytes() == b"AAA"
    assert (out / "B.pdf").read_bytes() == b"BBB"
    assert not list((out / ".rename_tmp").glob("*.pdf"))

    monkeypatch.undo()
    execute_rename_plan(out, rev, ops, source_path_of={}, pages_of={})
    assert (out / "A.pdf").read_bytes() == b"BBB"
    assert (out / "B.pdf").read_bytes() == b"AAA"


def test_execute_tao_moi_tu_pdf_nguon(dirs, hai_folder: Path):
    out, rev = dirs
    from app.global_naming import RenameOp

    src = hai_folder / "Quyet dinh dieu dong HAI.pdf"
    ops = [RenameOp("z1", "CREATE", None, None, "05.moi.pdf", "output")]
    execute_rename_plan(
        out, rev, ops, source_path_of={"z1": src}, pages_of={"z1": [4]}
    )
    assert (out / "05.moi.pdf").is_file()
    from pypdf import PdfReader

    assert len(PdfReader(str(out / "05.moi.pdf")).pages) == 1

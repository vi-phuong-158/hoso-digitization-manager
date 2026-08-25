from pathlib import Path

import pytest
from pypdf import PdfWriter

from app import cli
from app.golden_fixtures import isolated_golden_workspace
from app.pilot import PilotRunner, generate_run_id
from app.pipeline import Workspace


def test_generate_run_id():
    r1 = generate_run_id()
    r2 = generate_run_id()
    assert r1.startswith("pilot-")
    assert r1 != r2


def test_pilot_runner_full_cycle(repo_root: Path, tmp_path: Path):
    with isolated_golden_workspace(repo_root, temp_parent=tmp_path) as staged:
        ws = Workspace(staged.root)
        runner = PilotRunner(
            staged.person_folder,
            workspace=ws,
            provider_name="agent",
            provider_config={"analysis_root": str(staged.analysis_root)},
            run_id="pilot-test-001",
        )

        report = runner.run_full()
        assert report.run_id == "pilot-test-001"
        assert report.person_folder == staged.person_folder.name
        assert report.source_integrity_intact is True
        assert report.status in ("PASS", "REVIEW_REQUIRED")
        assert report.metrics.files_discovered == 3
        assert report.metrics.documents_created == 15
        assert report.metrics.taxonomy_documents == 18
        assert report.report_path is not None
        assert report.report_path.is_file()

        summary_text = report.summary_text()
        assert "PILOT RUN REPORT" in summary_text
        assert "INVENTORY" in summary_text
        assert "IDEMPOTENCY_RERUN" in summary_text


def test_pilot_cli_execution(repo_root: Path, tmp_path: Path, capsys):
    with isolated_golden_workspace(repo_root, temp_parent=tmp_path) as staged:
        rc = cli.main([
            "--root", str(staged.root),
            "pilot", str(staged.person_folder),
            "--provider", "agent",
            "--analysis-root", str(staged.analysis_root),
            "--run-id", "pilot-cli-test-001",
        ])
        assert rc == 0
        output = capsys.readouterr().out
        assert "PILOT RUN REPORT: pilot-cli-test-001" in output
        assert "PASS" in output

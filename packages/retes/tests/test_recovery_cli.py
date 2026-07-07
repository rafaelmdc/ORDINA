"""End-to-end CLI: `ordina recovery --fixture` builds a report from files, offline."""

from __future__ import annotations

import json
from pathlib import Path

from ordina_retes.cli import app
from typer.testing import CliRunner

_FIXTURES = Path(__file__).parent / "fixtures"
_runner = CliRunner()


def test_recovery_command_writes_a_report(tmp_path: Path):
    out = tmp_path / "recovery_report.json"
    result = _runner.invoke(
        app,
        [
            "recovery",
            "-a",
            str(_FIXTURES / "recovery_associations.tsv"),
            "-t",
            str(_FIXTURES / "recovery_taxonomy.tsv"),
            "--fixture",
            "--k",
            "2",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(out.read_text())
    assert report["n_cases"] > 0
    # The phylogeny walk genuinely recovers close genera — it beats the study-effort null.
    assert report["methods"]["predictor"]["auprc"] > report["methods"]["study_effort"]["auprc"]
    # Slice 1 is single-layer, so no lift over the phylogeny null (that is the Slice-2 gate).
    assert report["lift_vs_phylogeny"] == 0.0


def test_recovery_rejects_unknown_layer(tmp_path: Path):
    result = _runner.invoke(
        app,
        [
            "recovery",
            "-a",
            str(_FIXTURES / "recovery_associations.tsv"),
            "-t",
            str(_FIXTURES / "recovery_taxonomy.tsv"),
            "--fixture",
            "--layers",
            "metabolic.agora2",
            "-o",
            str(tmp_path / "r.json"),
        ],
    )
    assert result.exit_code != 0
    assert "unknown or unconfigured layer" in result.output

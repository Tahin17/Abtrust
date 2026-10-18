"""Saved scientific results must stay identifiable when presentation changes."""

import hashlib
import json

import pandas as pd
import pytest

from abtrust.provenance import file_sha256, write_analysis_manifest
from abtrust.report import load_validation_results, render_validation_report, write_validation_report
from abtrust.validation import run_all


def test_simulation_manifest_records_actual_budget_seed_and_runtime(tmp_path):
    results = run_all(scale=0.01, only=["srm"], verbose=False)
    write_validation_report(results, tmp_path, figures=False)
    manifest = json.loads((tmp_path / "validation/summary.json").read_text(encoding="utf-8"))
    study = manifest["studies"]["srm"]
    assert study["metadata"]["parameters"] == {"n_sims": 50, "seed": 5}
    assert study["metadata"]["scenario_configuration"]["expected_split"] == [0.5, 0.5]
    assert study["metadata"]["runtime"]["dependencies"]["scipy"]
    assert study["metadata"]["runtime"]["source_sha256"]
    assert study["csv_sha256"] == file_sha256(tmp_path / "validation/srm.csv")

    # Rendering can update presentation and its own manifest, never raw results.
    paths = [tmp_path / "validation/srm.csv", tmp_path / "validation/summary.json"]
    before = [p.read_bytes() for p in paths]
    render_validation_report(tmp_path, figures=False)
    assert before == [p.read_bytes() for p in paths]
    rendering = json.loads((tmp_path / "validation/rendering.json").read_text(encoding="utf-8"))
    assert rendering["simulation_manifest_sha256"] == hashlib.sha256(before[1]).hexdigest()
    reloaded = load_validation_results(tmp_path)
    pd.testing.assert_frame_equal(reloaded["srm"].table, results["srm"].table)
    assert reloaded["srm"].metadata == results["srm"].metadata


def test_render_rejects_changed_or_missing_csv(tmp_path):
    results = run_all(scale=0.01, only=["srm"], verbose=False)
    write_validation_report(results, tmp_path, figures=False)
    csv = tmp_path / "validation/srm.csv"
    csv.write_bytes(csv.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        render_validation_report(tmp_path, figures=False)
    csv.unlink()
    with pytest.raises(ValueError, match="missing"):
        load_validation_results(tmp_path)


def test_analysis_manifest_identifies_input_without_recording_private_path(tmp_path):
    data = tmp_path / "input.csv"
    data.write_text("arm,y\nA,1\nB,2\n", encoding="utf-8")
    manifest = write_analysis_manifest(tmp_path / "result.manifest.json", data_kind="user_supplied",
                                       settings={"alpha": 0.05}, input_path=data)
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["input"] == {"file": "input.csv", "sha256": file_sha256(data)}
    assert str(tmp_path) not in manifest.read_text(encoding="utf-8")


@pytest.mark.parametrize("scale,only", [(0, None), (-1, None), (float("nan"), None),
                                       (float("inf"), None), (1, []), (1, ["typo"])])
def test_invalid_simulation_selection_is_rejected(scale, only):
    with pytest.raises(ValueError):
        run_all(scale=scale, only=only, verbose=False)

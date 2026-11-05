import json
from datetime import datetime, timezone

from src.processing import pipeline_report


def test_generate_pipeline_report_writes_one_file_per_season(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline_report, "REPORT_DIR", tmp_path)

    started_at = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 11, 5, 12, 0, 2, tzinfo=timezone.utc)

    for season in (2022, 2023):
        pipeline_report.generate_pipeline_report(
            status="SUCCESS",
            started_at=started_at,
            finished_at=finished_at,
            league_id=39,
            season=season,
            stages={"bucket": "SUCCESS"},
        )

    report_2022 = json.loads(
        (tmp_path / "pipeline_report_league_39_season_2022.json").read_text(
            encoding="utf-8"
        )
    )
    report_2023 = json.loads(
        (tmp_path / "pipeline_report_league_39_season_2023.json").read_text(
            encoding="utf-8"
        )
    )

    assert report_2022["season"] == 2022
    assert report_2023["season"] == 2023
    assert report_2022["duration_seconds"] == 2.0
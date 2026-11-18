
"""Tests for non-destructive legacy report archiving."""

from scripts.archive_legacy_reports import (
    archive_legacy_reports,
    sha256,
)


def test_dry_run_does_not_copy_or_delete(tmp_path):
    source_dir = tmp_path / "reports"
    archive_dir = tmp_path / "archive"
    source_dir.mkdir()

    original = source_dir / "pipeline_report_league_39_season_2023.json"
    original.write_text('{"status": "SUCCESS"}', encoding="utf-8")

    stats = archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=True,
    )

    assert stats["found"] == 1
    assert stats["copied"] == 0
    assert original.exists()
    assert not archive_dir.exists()


def test_archive_preserves_original_and_checksum(tmp_path):
    source_dir = tmp_path / "reports"
    archive_dir = tmp_path / "archive"
    source_dir.mkdir()

    original = source_dir / "pipeline_report_league_39_season_2023.json"
    original.write_text('{"status": "SUCCESS"}', encoding="utf-8")

    stats = archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=False,
    )

    archived = archive_dir / original.name

    assert stats["copied"] == 1
    assert original.exists()
    assert archived.exists()
    assert sha256(original) == sha256(archived)


def test_archive_does_not_overwrite_different_report(tmp_path):
    source_dir = tmp_path / "reports"
    archive_dir = tmp_path / "archive"
    source_dir.mkdir()
    archive_dir.mkdir()

    original = source_dir / "pipeline_report.json"
    archived = archive_dir / "pipeline_report.json"

    original.write_text('{"version": 2}', encoding="utf-8")
    archived.write_text('{"version": 1}', encoding="utf-8")

    stats = archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=False,
    )

    assert stats["conflicts"] == 1
    assert archived.read_text(encoding="utf-8") == '{"version": 1}'
    assert original.read_text(encoding="utf-8") == '{"version": 2}'


def test_archive_ignores_powerbi_and_unrelated_files(tmp_path):
    source_dir = tmp_path / "reports"
    archive_dir = tmp_path / "archive"
    source_dir.mkdir()

    powerbi = source_dir / "powerbi"
    powerbi.mkdir()
    (powerbi / "dashboard.pbix").write_bytes(b"test")

    (source_dir / "unrelated.json").write_text(
        "{}",
        encoding="utf-8",
    )

    stats = archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=False,
    )

    assert stats["found"] == 0
    assert not archive_dir.exists()
    assert (powerbi / "dashboard.pbix").exists()


def test_repeated_archive_does_not_duplicate_files(tmp_path):
    source_dir = tmp_path / "reports"
    archive_dir = tmp_path / "archive"
    source_dir.mkdir()

    (source_dir / "data_quality_report.json").write_text(
        '{"overall_status": "PASS"}',
        encoding="utf-8",
    )

    archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=False,
    )

    second = archive_legacy_reports(
        source_dir,
        archive_dir,
        dry_run=False,
    )

    assert second["copied"] == 0
    assert second["already_archived"] == 1

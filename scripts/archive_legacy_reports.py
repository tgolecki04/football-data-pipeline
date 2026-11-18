
"""Safely archive historical reports without deleting originals."""

import argparse
import hashlib
import shutil
from pathlib import Path

from src.processing.run_context import ROOT


SOURCE_DIR = ROOT / "reports"
ARCHIVE_DIR = ROOT / "artifacts" / "legacy"

LEGACY_NAMES = {
    "pipeline_report.json",
    "data_quality_report.json",
}


def sha256(path: Path) -> str:
    """Calculate a file checksum."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def is_legacy_report(path: Path) -> bool:
    """Match only historical pipeline report JSON files."""

    if not path.is_file() or path.suffix.lower() != ".json":
        return False

    return (
        path.name in LEGACY_NAMES
        or (
            path.name.startswith("pipeline_report_league_")
            and "_season_" in path.name
        )
    )


def archive_legacy_reports(
    source_dir: Path = SOURCE_DIR,
    archive_dir: Path = ARCHIVE_DIR,
    *,
    dry_run: bool = True,
) -> dict:
    """Copy reports to the archive, preserving originals."""

    source_dir = Path(source_dir)
    archive_dir = Path(archive_dir)

    stats = {
        "found": 0,
        "copied": 0,
        "already_archived": 0,
        "conflicts": 0,
    }

    if not source_dir.exists():
        return stats

    for source in sorted(source_dir.iterdir()):
        if not is_legacy_report(source):
            continue

        stats["found"] += 1
        destination = archive_dir / source.name

        if destination.exists():
            if sha256(source) == sha256(destination):
                stats["already_archived"] += 1
                print(f"ALREADY ARCHIVED: {source.name}")
            else:
                stats["conflicts"] += 1
                print(f"CONFLICT, NOT OVERWRITTEN: {source.name}")
            continue

        if dry_run:
            print(f"WOULD COPY: {source.name}")
            continue

        archive_dir.mkdir(parents=True, exist_ok=True)

        # Exclusive creation prevents overwriting an existing file.
        try:
            with source.open("rb") as input_file:
                with destination.open("xb") as output_file:
                    shutil.copyfileobj(input_file, output_file)
        except FileExistsError:
            stats["conflicts"] += 1
            print(f"CONFLICT, NOT OVERWRITTEN: {source.name}")
            continue

        if sha256(source) != sha256(destination):
            raise RuntimeError(
                f"Checksum verification failed: {source.name}"
            )

        stats["copied"] += 1
        print(f"COPIED AND VERIFIED: {source.name}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Archive historical pipeline reports."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy files. Default is dry-run.",
    )

    args = parser.parse_args()

    stats = archive_legacy_reports(
        dry_run=not args.apply,
    )

    print(f"\nSummary: {stats}")


if __name__ == "__main__":
    main()

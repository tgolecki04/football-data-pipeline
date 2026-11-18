
"""Safety checks before replacing a league-season dataset."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def validate_replacement(cursor, df: pd.DataFrame, source: str,
                         league_id: int, season: int) -> None:
    """Prevent a partial Silver dataset from deleting existing fixtures."""

    required_columns = {
        "fixture_id", "league_id", "season",
    }
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing Silver columns: {sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError("Cannot load an empty Silver dataset.")

    if df["fixture_id"].isna().any():
        raise ValueError("Silver contains NULL fixture IDs.")

    if df["fixture_id"].duplicated().any():
        raise ValueError("Silver contains duplicate fixture IDs.")

    if not df["league_id"].eq(league_id).all():
        raise ValueError("Silver contains fixtures from another league.")

    if not df["season"].eq(season).all():
        raise ValueError("Silver contains fixtures from another season.")

    if "source" in df.columns and not df["source"].eq(source).all():
        raise ValueError("Silver contains fixtures from another source.")

    incoming_ids = set(df["fixture_id"].astype(int))

    cursor.execute(
        """
        SELECT fixture_id
        FROM public.fixtures
        WHERE source = %s
          AND league_id = %s
          AND season = %s
        """,
        (source, league_id, season),
    )

    existing_ids = {row[0] for row in cursor.fetchall()}
    missing_ids = existing_ids - incoming_ids

    logger.info(
        "Load guard: source=%s, league=%s, season=%s, "
        "existing=%d, incoming=%d",
        source, league_id, season,
        len(existing_ids), len(incoming_ids),
    )

    if missing_ids:
        raise ValueError(
            f"Unsafe replacement blocked: {len(missing_ids)} "
            f"existing fixtures are absent from Silver. "
            f"Example IDs: {sorted(missing_ids)[:10]}"
        )

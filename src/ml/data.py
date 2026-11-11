import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv(".env")


def load_fixtures() -> pd.DataFrame:
    """Load fixtures from the database."""

    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"]
    ) as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM fixtures ORDER BY date;")
        rows = cur.fetchall()
        columns = [column.name for column in cur.description]

    fixtures = pd.DataFrame(rows, columns=columns)
    
    return fixtures

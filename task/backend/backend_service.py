from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import psycopg2
import os
from datetime import datetime


app = FastAPI()

# PostgreSQL config
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", 5432))
PG_DB = os.getenv("PG_DB", "stocks")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "password")


class PricePoint(BaseModel):
    timestamp: datetime
    price: float


def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


@app.get("/api/prices/{stock_name}", response_model=List[PricePoint])
def get_prices(
    stock_name: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
):
    """
    Retrieve all price points for the given stock_name between start_time and end_time.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT timestamp, price FROM stock_prices
        WHERE stock_name = %s
        """
        params = [stock_name]

        if start_time:
            query += " AND timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= %s"
            params.append(end_time)

        query += " ORDER BY timestamp ASC"

        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return [PricePoint(timestamp=row[0], price=float(row[1])) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/average/{stock_name}")
def get_average(
    stock_name: str,
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
):
    """
    Calculate and return the average price for the given stock_name between start_time and end_time.
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT AVG(price) FROM stock_prices
        WHERE stock_name = %s
        """
        params = [stock_name]

        if start_time:
            query += " AND timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= %s"
            params.append(end_time)

        cur.execute(query, params)
        avg_price = cur.fetchone()[0]
        cur.close()
        conn.close()

        if avg_price is None:
            return {"average_price": None}

        return {"average_price": float(avg_price)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

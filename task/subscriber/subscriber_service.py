import os
import redis
import threading
import time
import requests
import psycopg2
from datetime import datetime

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Centrifugo config
CENTRIFUGO_API_URL = os.getenv("CENTRIFUGO_API_URL", "http://localhost:8000/api")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "centrifugo-api-key")

# PostgreSQL config
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB = os.getenv("POSTGRES_DB", "stocks")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Global batch buffer
batch_buffer = []

# Lock for thread-safe access to buffer
buffer_lock = threading.Lock()


def forward_to_centrifugo(channel, message):
    payload = {
        "method": "publish",
        "params": {
            "channel": channel,
            "data": message
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"apikey {CENTRIFUGO_API_KEY}"
    }
    try:
        response = requests.post(CENTRIFUGO_API_URL, json=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error sending to Centrifugo: {e}")


def insert_batch_to_postgres():
    while True:
        time.sleep(5)
        with buffer_lock:
            if not batch_buffer:
                continue
            to_insert = batch_buffer[:]
            batch_buffer.clear()

        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
            )
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO stock_prices (stock_name, exchange, price, timestamp) VALUES (%s, %s, %s, to_timestamp(%s))",
                to_insert
            )
            conn.commit()
            cur.close()
            conn.close()
            print(f"Inserted {len(to_insert)} records.")
        except Exception as e:
            print(f"PostgreSQL insert error: {e}")


def message_handler(msg):
    try:
        channel = msg['channel']
        data_str = msg['data'].decode("utf-8")
        # data format: "AAPL:(220.4, 1757494917.021389)"
        stock_name, payload = data_str.split(":")
        price_str, timestamp_str = payload.strip("()").split(",")
        price = float(price_str)
        timestamp = float(timestamp_str)

        # Add to batch buffer
        with buffer_lock:
            batch_buffer.append((stock_name, channel, price, timestamp))

        # Forward to Centrifugo
        forward_to_centrifugo(channel, {
            "stock": stock_name,
            "price": price,
            "timestamp": timestamp
        })

    except Exception as e:
        print(f"Error in message handler: {e}")


def start_subscriber():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
        pubsub = r.pubsub()
        pubsub.subscribe(**{"NASDAQ": message_handler, "NYSE": message_handler})
        print("Subscribed to NASDAQ and NYSE")

        # Run subscriber loop (blocking)
        pubsub.run_in_thread(sleep_time=0.01)
    except Exception as e:
        print(f"Redis subscriber error: {e}")


if __name__ == "__main__":
    # Start PostgreSQL batch insert thread
    threading.Thread(target=insert_batch_to_postgres, daemon=True).start()

    # Start Redis subscriber
    start_subscriber()

    # Keep main thread alive
    while True:
        time.sleep(60)

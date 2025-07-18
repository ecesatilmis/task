import os
import redis
import threading
import time
import requests
import psycopg2
import json
import sys
from datetime import datetime

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Centrifugo config
CENTRIFUGO_API_URL = os.getenv("CENTRIFUGO_API_URL", "http://centrifugo:8000/api")
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

        start = time.time()
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD
            )
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO stock_prices (stock_name, exchange_name, price, timestamp) VALUES (%s, %s, %s, to_timestamp(%s))",
                to_insert
            )
            conn.commit()
            cur.close()
            conn.close()
            elapsed = time.time() - start

            # Successful insert log (all fields present)
            print(json.dumps({
                "timestamp": datetime.now().isoformat() + "Z",
                "metric": "insert_latency",
                "value": elapsed,
                "unit": "seconds",
                "event": "insert_success",
                "service": "subscriber"
            }), file=sys.stdout)

        except Exception as e:
            # Error log (all fields present)
            print(json.dumps({
                "timestamp": datetime.now().isoformat() + "Z",
                "metric": "",
                "value": 0,
                "unit": "",
                "event": "postgres_insert_failed",
                "service": "subscriber"
            }), file=sys.stdout)

def message_handler(msg):
    try:
        # If channel is coming from Redis and you use decode_responses=False, 
        # then channel is a bytes object — not a string.
        #  So you need to decode it too
        channel = msg['channel'].decode("utf-8") 
        data_str = msg['data'].decode("utf-8")

        # Example: "AAPL:(220.4, 1757494917.021389)"
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
    def listen():
        while True:
            try:
                # print("Connecting to Redis pubsub...")
                r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
                pubsub = r.pubsub()
                pubsub.subscribe(**{"NASDAQ": message_handler, "NYSE": message_handler})
                # print("Subscribed to NASDAQ and NYSE")

                for message in pubsub.listen():
                    if message['type'] == 'message':
                        message_handler(message)

            except (redis.ConnectionError, redis.TimeoutError, OSError, ValueError) as e:
                print(f"[Subscriber] Redis pubsub error: {e}. Reconnecting in 3 seconds...")
                time.sleep(3)
            except Exception as e:
                print(f"[Subscriber] Unexpected error: {e}")
                time.sleep(3)

    # Run that blocking Redis loop in the background. Let the rest of my code do other things like insert to DB."
    threading.Thread(target=listen, daemon=True).start()

def wait_for_redis(retries=5):
    for i in range(retries):
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
            r.ping()
            # print("Redis is ready.")
            return True
        except redis.exceptions.ConnectionError:
            print(f"[Retry {i+1}] Waiting for Redis...")
            time.sleep(2)
    return False

if __name__ == "__main__":
    # Start PostgreSQL batch insert thread
    # It runs independently, and constantly looks for new data to insert.
    threading.Thread(target=insert_batch_to_postgres, daemon=True).start()

    if not wait_for_redis():
        print("Redis is not available. Exiting...")
        exit(1)

    start_subscriber()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Shutting down...")

import time
import random
import redis
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
except Exception as e:
    print(f"Error connecting to Redis: {e}")
    exit(1)

stocks_nasdaq = {"AMZN": 182.55, "AAPL": 220.00, "MSFT": 421.50}
stocks_nyse = {"TSLA": 700.00, "NFLX": 500.00, "DIS": 145.00}


def generate_price(current_price):
    change = random.uniform(-0.5, 0.5)
    return round(current_price + change, 2)


while True:
    try:
        # Update NASDAQ stocks
        timestamp = time.time()
        for stock, price in stocks_nasdaq.items():
            new_price = generate_price(price)
            if abs(new_price - price) >= 0.10:  # Only update if change is significant
                stocks_nasdaq[stock] = new_price
                # Publish the new price to the NASDAQ Redis channel
                redis_client.publish("NASDAQ", f"{stock}:{new_price, timestamp}")

        # Update NYSE stocks
        for stock, price in stocks_nyse.items():
            new_price = generate_price(price)
            if abs(new_price - price) >= 0.10:  # Only update if change is significant
                stocks_nyse[stock] = new_price
                # Publish the new price to the NYSE Redis channel
                redis_client.publish("NYSE", f"{stock}:{new_price, timestamp}")

        time.sleep(0.1)
    except Exception as e:
        print(f"Error during operation: {e}")
        time.sleep(1)  # Wait a bit before trying again

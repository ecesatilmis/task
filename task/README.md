# Baryonic Space Backend Engineer Task

This project implements a real-time and retrospective monitoring system for time-series built with Dockerized microservices. The system simulates stock price streams, stores them for historical analysis, and broadcasts live updates to clients.

The entire project is Dockerized and can be launched with a single command.

## Architecture

This system monitors time-series stock price data both in real-time and historically, leveraging multiple Dockerized components working together:


- **`stock_generator`** – Simulates stock data and publishes to Redis.
- **`redis`** – Acts as the message broker for live stock updates. Holds Pub/Sub channels subscribed by the subscriber service.
- **`subscriber`** – Listens to Redis Pub/Sub channels for live stock updates. Buffers incoming messages in batches, then inserts them into PostgreSQL. Forwards updates in real-time to clients via Centrifugo.
- **`backend`** – FastAPI REST API to query stock price history and averages.
- **`client`** – Frontend that connects to Centrifugo for live updates.
- **`centrifugo(v6.2.3)`** – WebSocket server for broadcasting real-time stock data.
- **`postgres`** – Stores stock price history.
- **`vector(v0.48.0)`** – Collects and stores logs and metrics for observability.
- **`nginx`** – Proxies `/api/`, `/connection/websocket`, and serves static frontend.
- **`grafana`** – Visualizes observability metrics collected from subscriber.


![Alt text](./diagram.png "Diagram for the Step 1 Architecture")
_The diagram above illustrates the target architecture for Step 1. The final system, after completing Step 2, will build upon this diagram by introducing Nginx, Vector, and Grafana._

---

## Implementation & Design Decisions

### Generator

- Provided service.
- Publishes stock messages to NASDAQ and NYSE Redis channels.

### Subscriber

- Parses and buffers stock messages from Redis.
- Inserts batched entries into PostgreSQL.
- Forwards real-time updates to Centrifugo via HTTP API.
- Emits structured JSON logs for Vector.dev observability.

### Backend (FastAPI)

- Implements:
  - GET /api/prices/{stock_name} — fetches prices in a given time range.
  - GET /api/average/{stock_name} — computes average price over time.

### Centrifugo

- Allows anonymous clients to subscribe to NASDAQ and NYSE channels.
- Publishes real-time updates from subscriber.

### Nginx

- Proxies:
  - /api/* → backend
  - /connection/websocket → Centrifugo
  - / → frontend 
  - /grafana  → grafana dashboard
- Handles CORS and HTTPS.

### Vector.dev + Grafana

- Vector collects logs from the subscriber container.
- Transforms JSON logs to metrics (e.g., insert latency).
- Stores metrics in PostgreSQL.
- Grafana reads metrics and visualizes service performance.

## Project Diagram

  ```sql
  +-------------+        +--------+        +--------------+        +------------+
  |  Generator  |──────▶ | Redis  |──────▶ |  Subscriber  |──────▶ | PostgreSQL |
  +-------------+        +--------+        +--------------+        +------------+
                                              │  ▲
                                              │  │
                                              ▼  │
                                            Centrifugo
                                              │
                                            WebSocket
                                              │
                                            +-----------+
                                            |  Frontend |
                                            +-----------+

                      Vector.dev ───▶ PostgreSQL (metrics) ◀── Grafana

                               All proxied through: NGINX

  ```

## Setup & Run

### 1. Build & Start the Project

```

docker compose up --build

```

This will build and start all containers.

### 2. Access the system

- Frontend & API Access:
  - Open your browser and navigate to:

    ```arduino

    http://localhost/


    ```

- Grafana Dashboard for Metrics Visualization:
  - Grafana visualizes metrics collected by Vector.dev and stored in PostgreSQL.
  - Access it at:

    ```arduino

    http://localhost/grafana


    ```
  - Login Credentials:

    - Username: admin
    - Password: admin

## Observability

The subscriber emits structured logs (JSON) with the latency (duration) of bulk inserts into PostgreSQL metrics, collected by vector and stored in PostgreSQL for analysis. Grafana dashboards visualize insert times.

## API Endpoints

1.  `GET /api/prices/{stock_name}`: Retrieves all price points for a given stock between a `start_time` and `end_time` query parameter.

2.  `GET /api/average/{stock_name}`: Calculates and returns the average price for a given stock between a `start_time` and `end_time`.


## Database Schema

  ```sql
  CREATE TABLE stock_prices (
      timestamp TIMESTAMPTZ NOT NULL,
      stock_name VARCHAR(255) NOT NULL,
      exchange_name VARCHAR(255) NOT NULL,
      price NUMERIC NOT NULL
  );
  -- Consider creating an index for performance on timestamp and stock_name
  CREATE INDEX idx_stock_prices_ts_name ON stock_prices (stock_name, timestamp DESC);

  CREATE TABLE  IF NOT EXISTS metrics (
    timestamp timestamptz NOT NULL,
    service text,
    event text,
    metric text,
    value double precision,
    unit text
  );
  ```

## Notes

- Ports:
  - Backend: 5050 → 5050
  - Centrifugo: 8000 → 8000
  - Grafana: 3000 → 3000
  - Frontend: 8080 → 8080
- Environment variables configured in docker-compose.yml.

## Environment Variables

Set in docker-compose.yml:

  ```

  POSTGRES_HOST=postgres
  POSTGRES_PORT=5432
  POSTGRES_DB=stocks
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=password

  ```

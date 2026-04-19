## Load Testing

This directory contains the first Locust-based load test setup for the
distributed semantic retrieval system.

### What it covers

- User signup and login
- Seed document upload during user startup
- Warm steady-state search traffic
- Search-heavy traffic
- Search-only traffic
- Document-list traffic
- Upload-heavy traffic
- Auth-only traffic
- Mixed traffic

### Prerequisites

Start the system first:

```powershell
docker compose up --build bootstrap
docker compose up -d
```

Wait for the public readiness endpoint to return ready:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/ready
```

### Run Locust UI

```powershell
docker compose --profile loadtest up -d locust
```

Then open:

```text
http://127.0.0.1:8089
```

### Headless example

```powershell
docker compose --profile loadtest run --rm locust --headless -u 12 -r 3 -t 2m
```

### Repeatable benchmark sweeps

Quick validation sweep:

```powershell
python scripts/run_load_benchmarks.py --quick
```

Full benchmark sweep:

```powershell
python scripts/run_load_benchmarks.py
```

Results are written to:

```text
artifacts/load_benchmarks/<timestamp>/
```

Each run includes:

- raw Locust output for each case
- `summary.json`
- `summary.md`
- `latest.json` for the most recent run

### Endpoint-specific runs

Auth-only:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 8 -r 2 -t 1m AuthOnlyUser
```

Search-only:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 10 -r 2 -t 2m SearchOnlyUser
```

Warm search-only:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 25 -r 5 -t 2m WarmSearchUser
```

Document listing:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 10 -r 2 -t 2m DocumentListUser
```

Upload-focused:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 5 -r 1 -t 1m UploadOnlyUser
```

Mixed baseline:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 12 -r 3 -t 2m MixedTrafficUser SearchHeavyUser UploadHeavyUser
```

Tag-filtered runs:

```powershell
docker compose --profile loadtest run --rm locust --headless -u 10 -r 2 -t 2m --tags search
docker compose --profile loadtest run --rm locust --headless -u 8 -r 2 -t 2m --tags documents
docker compose --profile loadtest run --rm locust --headless -u 5 -r 1 -t 1m --tags uploads
docker compose --profile loadtest run --rm locust --headless -u 8 -r 2 -t 1m --tags auth
```

### Suggested first runs

- Search-heavy smoke run:
  - 10 users
  - spawn rate 2/s
  - 1-2 minutes
- Warm steady-state search:
  - 25 users
  - spawn rate 5/s
  - 2 minutes
- Mixed traffic:
  - 15 users
  - spawn rate 3/s
  - 2-3 minutes
- Upload stress:
  - 5 users
  - spawn rate 1/s
  - 1 minute
- Auth burst:
  - 8 users
  - spawn rate 2/s
  - 1 minute

### Metrics to record

- Median and p95 latency
- Requests per second
- Failure rate
- Whether readiness stays healthy during the run
- Which component saturates first:
  - API replicas
  - embedding service
  - worker queue
  - Qdrant

### Notes

- These scenarios intentionally use the public Nginx entry point.
- The compose-managed Locust container targets `http://nginx` inside the Docker network.
- Upload tasks return after the API accepts the file for processing.
- `SearchOnlyUser` includes per-user signup, upload, and indexing during startup.
- `WarmSearchUser` prepares one shared indexed account first, then measures steady-state search traffic without per-user ingestion overhead.

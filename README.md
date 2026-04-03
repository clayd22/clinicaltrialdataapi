# Clinical Trials Middleware

Abstraction layer between clinical trial registries and downstream consumers. Harvests trials from [ClinicalTrials.gov](https://clinicaltrials.gov), normalizes them into a generalizable schema, and exposes a REST API for bulk export and incremental updates.

Designed as middleware: the schema and API are registry-agnostic so additional sources (EU CTIS, ISRCTN, WHO ICTRP) can be added without changing the consumer interface.

## Hosted API

A live instance is running at `http://clintrial-api.com:8000` with **578,873 clinical trials** loaded as of April 2nd. An internal scheduler keeps the data fresh with hourly and daily delta syncs. Server and domain are on Njalla.

Interactive docs: `http://clintrial-api.com:8000/docs`

### Bulk Export

```bash
# Full CSV export (~578K trials)
curl -o trials.csv http://clintrial-api.com:8000/trials/bulk

# NDJSON (recommended for nested fields like conditions, interventions, locations)
curl -o trials.ndjson "http://clintrial-api.com:8000/trials/bulk?format=ndjson"
```

### Incremental Updates

Returns trials updated on or after the given date, plus a `cursor` to use as `since` on the next call.

```bash
curl "http://clintrial-api.com:8000/trials/updates?since=2026-04-01"
# Response includes: "cursor": "2026-04-02T00:00:00"

# Next call — use the cursor
curl "http://clintrial-api.com:8000/trials/updates?since=2026-04-02T00:00:00"
```

### Browse and Search

```bash
# Paginated listing with filters
curl "http://clintrial-api.com:8000/trials?limit=10&status=RECRUITING"

# Single trial by NCT number
curl http://clintrial-api.com:8000/trials/NCT07226206

# Health check
curl http://clintrial-api.com:8000/
```

| Param | Default | Description |
|---|---|---|
| `limit` | 100 | Results per page (max 1000) |
| `offset` | 0 | Pagination offset |
| `status` | — | Filter by status (e.g., RECRUITING, COMPLETED) |
| `registry_source` | — | Filter by source registry |

### Harvest Control

```bash
# Full harvest (~500K trials, takes ~15-25 min)
curl -X POST "http://clintrial-api.com:8000/harvest/trigger?full=true"

# Incremental harvest from a specific date
curl -X POST "http://clintrial-api.com:8000/harvest/trigger?since=2026-03-29"

# Check progress
curl http://clintrial-api.com:8000/harvest/status
```

## Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Trigger full harvest to populate local DB
curl -X POST "http://localhost:8000/harvest/trigger?full=true"
curl http://localhost:8000/harvest/status
```

Replace `clintrial-api.com:8000` with `localhost:8000` for all API examples above.

### Docker

```bash
docker build -t clinical-trials .
docker run -p 8000:8000 -v trials_data:/data clinical-trials
```

### VPS

```bash
git clone https://github.com/clayd22/clinicaltrialdataapi.git && cd clinicaltrialdataapi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Architecture

```
ClinicalTrials.gov API v2 ──> Harvester ──> Transformer ──> SQLite DB ──> REST API ──> OpenAlex
```

## Tradeoffs and what needs to be added

- SQLite is a major tradeoff here for me, for this assignment using it made sense because I was able to get the DB up in literally 10
  minutes, but the write concurrency limit is impractical so I'd have to swap to Postgres or similar.
- There is no systematic testing, the process was essentially manually viewing how 5-10 of the nested Json objects mapped to my flat
  format and ensuring everything looked good.  A systematic way to track loss here to ensure it doesn't get worse in a significant number
  of cases would be something I'd want to add, but like you mentioned we are trading a lot of 1% cases for speed.
- raw_json stored in SQLite, the pro of this is that it keeps full fidelity to source data but bloats the DB (~11GB). Production might store raw payloads in object storage or a separate table.
- There are also a few usability features I wanted to add but couldn't get within the 3 hour window, like delta fetching output as csv,
  accurate download time information, and endpoints to see the number of stored clinical trials without fetching.
  
- **Harvester** (`app/services/harvester.py`): Async HTTP client that paginates through the ClinicalTrials.gov API (1000 trials/page), respecting rate limits (~50 req/min). Supports full and incremental harvests via `LastUpdatePostDate` filtering.
- **Transformer** (`app/services/transformer.py`): Maps CT.gov's deeply nested JSON into a flat, generalizable schema. Each registry would get its own transformer.
- **Scheduler** (`app/services/scheduler.py`): Internal background scheduler that automatically runs incremental harvests hourly (2h lookback) and a wider daily sweep (48h lookback) to catch anything missed.
- **Database**: Single `trials` table with a `(registry_source, registry_id)` composite unique key. Stores both normalized fields and the complete `raw_json` for lossless preservation.
- **API**: FastAPI with streaming bulk export (CSV/NDJSON), paginated JSON listing, cursor-based incremental updates, and harvest management.

## Schema Design

The schema is intentionally registry-agnostic:

| Field | Purpose |
|---|---|
| `registry_id` + `registry_source` | Universal compound key across registries |
| `brief_title`, `official_title` | Every registry has these |
| `status`, `phase`, `study_type` | Universal trial metadata |
| `conditions`, `interventions` | JSON arrays — flexible for varying cardinality |
| `primary_outcome` | What the trial is measuring |
| `eligibility_criteria` | Who can participate |
| `locations` | Where the trial is conducted |
| `sponsor`, `enrollment_count` | Common across registries |
| `start_date`, `completion_date` | Universal timeline |
| `last_updated` | From source — enables incremental sync |
| `raw_json` | Complete original payload for lossless storage |

## Internal Scheduler

The app includes a built-in scheduler that keeps the database fresh without external cron:

- **Hourly**: Fetches trials updated in the last 2 hours. Catches new/modified trials with minimal overhead.
- **Daily**: Wider sweep of the last 48 hours. Safety net for anything missed due to CT.gov posting delays or transient failures.

Upserts make overlap harmless — re-fetching a trial just updates the existing row.

## Future Improvements

These are documented tradeoffs made to deliver working software within the time constraint:

- **Additional registries**: The schema and transformer pattern support this — add a new transformer per registry (EU CTIS, ISRCTN, WHO ICTRP, ANZCTR)
- **Authentication**: API keys or OAuth for the harvest trigger endpoint
- **Rate limiting**: Protect the API from abuse
- **Database migrations**: Currently uses `create_all()`; production would use Alembic
- **PostgreSQL**: For production scale, swap SQLite for Postgres (single env var change)
- **Full-text search**: SQLite FTS5 or Postgres tsvector for searching trial descriptions
- **Comprehensive test suite**: Unit tests for transformer, integration tests for API
- **Data normalization**: Standardize condition names via MeSH ontology, normalize phase values across registries
- **Monitoring/alerting**: Track harvest failures, API latency
- **Caching**: Redis or in-memory cache for hot queries
- **CI/CD pipeline**: Automated testing and deployment

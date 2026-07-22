# Serverless Document Processing Pipeline on Google Cloud

A serverless, event-driven pipeline that automatically processes documents uploaded to Cloud Storage, runs simulated OCR, and streams extracted metadata into BigQuery — all without managing any servers.

## Architecture

```
User → Cloud Storage → Pub/Sub → Cloud Run → BigQuery
         (upload)     (notify)  (OCR + parse)  (store)
```

| Component | GCP Service | Purpose |
|-----------|-------------|---------|
| Ingestion | Cloud Storage | Receives uploaded files |
| Trigger | Pub/Sub | Notifies on new file uploads |
| Processor | Cloud Run | Runs simulated OCR, extracts metadata |
| Storage | BigQuery | Stores structured metadata |

## Metadata Schema

Every processed document produces one BigQuery row:

| Field | Type | Description |
|-------|------|-------------|
| `filename` | STRING | GCS object name (path) |
| `processed_at` | TIMESTAMP | UTC time of processing |
| `tags` | STRING (REPEATED) | Extracted semantic tags |
| `word_count` | INTEGER | Number of words detected |

## Project Structure

```
google-cloud-serverless-app/
├── processor/
│   ├── main.py           # FastAPI webhook server
│   ├── ocr.py            # Simulated OCR and tag extraction
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile        # Multi-stage container build
├── docs/
│   └── gcp_setup.md      # Step-by-step GCP Console setup guide
└── README.md
```

## Quick Start

### 1. Provision GCP Resources

Follow the detailed step-by-step guide in [`docs/gcp_setup.md`](docs/gcp_setup.md).

### 2. Run Locally (optional, for development)

```bash
cd processor

# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export BQ_PROJECT="your-project-id"
export BQ_DATASET="document_pipeline"
export BQ_TABLE="document_metadata"

# Start the server
uvicorn main:app --reload --port 8080
```

The API docs will be available at http://localhost:8080/docs.

### 3. Send a Test Pub/Sub Message Locally

```bash
# Simulate a GCS OBJECT_FINALIZE event
python - <<'EOF'
import base64, json, requests

payload = {
    "message": {
        "data": base64.b64encode(json.dumps({
            "bucket": "your-bucket-name",
            "name": "test-document.txt",
            "eventType": "OBJECT_FINALIZE"
        }).encode()).decode(),
        "messageId": "test-123",
        "publishTime": "2026-01-01T00:00:00Z"
    },
    "subscription": "projects/your-project/subscriptions/test"
}

r = requests.post("http://localhost:8080/webhook", json=payload)
print(r.status_code)  # Expected: 204
EOF
```

### 4. Verify in BigQuery

After uploading a real file to the GCS bucket:

```sql
SELECT *
FROM `your-project-id.document_pipeline.document_metadata`
ORDER BY processed_at DESC
LIMIT 10;
```

## OCR Simulation

The [`processor/ocr.py`](processor/ocr.py) module handles two cases:

- **Text files** (`.txt`, `.md`, `.csv`, `.json`, etc.) — reads content directly, counts words, and extracts semantic tags by matching against a keyword vocabulary (finance, legal, medical, research, etc.).
- **Binary files** (images, PDFs, DOCX, etc.) — simulates OCR with a realistic random word count and derives tags from the filename. To use a real OCR library, replace the binary branch in `process_document()`.

## Environment Variables (Cloud Run)

| Variable | Description | Example |
|----------|-------------|---------|
| `BQ_PROJECT` | GCP project owning BigQuery | `my-project-123` |
| `BQ_DATASET` | BigQuery dataset name | `document_pipeline` |
| `BQ_TABLE` | BigQuery table name | `document_metadata` |

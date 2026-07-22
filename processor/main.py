"""
main.py — FastAPI Cloud Run service for the document processing pipeline.

Flow:
  1. Pub/Sub Push subscription sends a POST to /webhook.
  2. We decode the base64-encoded GCS notification from the message data.
  3. We download the file from Cloud Storage.
  4. We pass the content through Gemini 1.5 Flash (Vertex AI) for:
       - Text extraction / image description
       - Document type classification
       - Entity extraction (dates, names, orgs, locations, amounts)
  5. We insert the enriched metadata as a row into BigQuery.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from google.cloud import bigquery, storage

from ocr import process_document

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variables (set these in Cloud Run)
# ---------------------------------------------------------------------------
BQ_PROJECT  = os.environ["BQ_PROJECT"]       # GCP project that owns BigQuery
BQ_DATASET  = os.environ["BQ_DATASET"]       # e.g. "document_pipeline"
BQ_TABLE    = os.environ["BQ_TABLE"]         # e.g. "document_metadata"

# ---------------------------------------------------------------------------
# GCP clients (initialised once at startup, reused across requests)
# ---------------------------------------------------------------------------
gcs_client = storage.Client()
bq_client  = bigquery.Client(project=BQ_PROJECT)
bq_table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Document Processing Service",
    description="Receives Pub/Sub push messages for GCS uploads, processes documents with Gemini 1.5 Flash (Vertex AI), and stores enriched metadata in BigQuery.",
    version="2.0.0",
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health() -> dict:
    """Lightweight liveness probe used by Cloud Run."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Webhook – Pub/Sub push endpoint
# ---------------------------------------------------------------------------
@app.post("/webhook", status_code=204, tags=["pipeline"])
async def pubsub_webhook(request: Request) -> Response:
    """
    Receives a Pub/Sub push message that encodes a GCS object-finalize event.

    Expected body (application/json):
    {
      "message": {
        "data": "<base64-encoded GCS notification JSON>",
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "projects/.../subscriptions/..."
    }
    """
    body = await request.json()

    # ------------------------------------------------------------------ #
    # 1. Parse the Pub/Sub envelope
    # ------------------------------------------------------------------ #
    try:
        message = body["message"]
        raw_data = base64.b64decode(message["data"]).decode("utf-8")
        gcs_event: dict = json.loads(raw_data)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        log.error("Malformed Pub/Sub message: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")

    bucket_name: str = gcs_event.get("bucket", "")
    object_name: str = gcs_event.get("name", "")
    event_type:  str = gcs_event.get("eventType", "")

    log.info("Event received | type=%s | bucket=%s | object=%s",
             event_type, bucket_name, object_name)

    # Only process object-finalize events (new / overwritten files)
    if "OBJECT_FINALIZE" not in event_type and event_type != "":
        log.info("Skipping non-finalize event: %s", event_type)
        return Response(status_code=204)

    if not bucket_name or not object_name:
        log.error("Missing bucket or object name in event payload.")
        raise HTTPException(status_code=400, detail="Missing bucket/object in event")

    # ------------------------------------------------------------------ #
    # 2. Download file from Cloud Storage
    # ------------------------------------------------------------------ #
    try:
        bucket = gcs_client.bucket(bucket_name)
        blob   = bucket.blob(object_name)
        content: bytes = blob.download_as_bytes()
        log.info("Downloaded %d bytes from gs://%s/%s", len(content), bucket_name, object_name)
    except Exception as exc:
        log.exception("Failed to download object from GCS: %s", exc)
        raise HTTPException(status_code=500, detail="GCS download failed")

    # ------------------------------------------------------------------ #
    # 3. Gemini-powered extraction: text, document type, entities
    # ------------------------------------------------------------------ #
    processed_at = datetime.now(timezone.utc)
    metadata = process_document(
        filename=object_name,
        content=content,
        processed_at=processed_at,
    )
    log.info(
        "Metadata extracted | doc_type=%s | words=%d | tags=%s",
        metadata.get("document_type"),
        metadata.get("word_count"),
        metadata.get("tags"),
    )

    # ------------------------------------------------------------------ #
    # 4. Insert enriched metadata row into BigQuery
    # ------------------------------------------------------------------ #
    row = {
        "filename":       metadata["filename"],
        "processed_at":   metadata["processed_at"],
        "tags":           metadata["tags"],           # REPEATED STRING
        "word_count":     metadata["word_count"],
        "extracted_text": metadata.get("extracted_text", ""),
        "document_type":  metadata.get("document_type", "unknown"),
        "entities":       metadata.get("entities", "{}"),  # JSON string
    }

    errors = bq_client.insert_rows_json(bq_table_id, [row])
    if errors:
        log.error("BigQuery insert errors: %s", errors)
        raise HTTPException(status_code=500, detail="BigQuery insert failed")

    log.info("Row successfully inserted into %s", bq_table_id)
    return Response(status_code=204)

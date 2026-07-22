"""
ocr.py — Gemini-powered document processing module.

Uses Gemini 1.5 Flash via Vertex AI to:
  1. Extract actual text / describe image content (multimodal)
  2. Classify document type (invoice, contract, resume, …)
  3. Extract entities (dates, names, organizations, locations, amounts)

Supported formats:
  - Text:   .txt  .md  .csv  .html
  - Images: .jpg  .jpeg  .png  .gif  .webp
  - PDF:    .pdf
  - Other:  Gemini receives filename + description fallback

Fallback (Option B): on any Gemini error, returns a row with empty AI fields
so the pipeline never loses a document event.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
)

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Vertex AI initialisation (once at module import)
# ─────────────────────────────────────────────────────────────────────────────
_VERTEX_PROJECT  = os.environ["BQ_PROJECT"]                        # reuse GCP project
_VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
_GEMINI_MODEL    = "gemini-1.5-flash"

vertexai.init(project=_VERTEX_PROJECT, location=_VERTEX_LOCATION)
_model = GenerativeModel(_GEMINI_MODEL)

# ─────────────────────────────────────────────────────────────────────────────
# MIME type map
# ─────────────────────────────────────────────────────────────────────────────
_MIME_MAP: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".txt":  "text/plain",
    ".md":   "text/plain",
    ".csv":  "text/csv",
    ".html": "text/html",
    ".htm":  "text/html",
    ".log":  "text/plain",
}

_EMPTY_ENTITIES: dict = {
    "dates":         [],
    "names":         [],
    "organizations": [],
    "locations":     [],
    "amounts":       [],
}

# ─────────────────────────────────────────────────────────────────────────────
# Gemini prompt
# ─────────────────────────────────────────────────────────────────────────────
_PROMPT = """Analyze this document carefully and respond ONLY with a valid JSON object.
Do NOT include markdown fences, explanations, or any text outside the JSON.

Return exactly this structure:
{
  "extracted_text": "<full extracted text or detailed description of the document content, max 3000 characters>",
  "document_type": "<exactly one of: invoice, contract, resume, report, letter, image, spreadsheet, medical, legal, other>",
  "tags": ["<tag1>", "<tag2>"],
  "word_count": <integer — count of words in visible/extracted text>,
  "entities": {
    "dates":         ["<YYYY-MM-DD or natural date string>"],
    "names":         ["<full person name>"],
    "organizations": ["<company or institution name>"],
    "locations":     ["<city, country, or address>"],
    "amounts":       ["<monetary amount with currency symbol>"]
  }
}

Rules:
- tags: 1 to 4 lowercase single-word tags describing the document topic
- All list fields must be [] if nothing relevant is found
- For images without readable text: describe what you see in extracted_text
- word_count must be a plain integer, not a string
"""

_SAFETY = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH:        HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT:         HarmBlockThreshold.BLOCK_NONE,
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────
def _detect_mime(filename: str) -> str | None:
    return _MIME_MAP.get(Path(filename).suffix.lower())


def _parse_gemini_json(raw: str) -> dict:
    """Strip any accidental markdown fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content between first pair of fences
        text = parts[1]
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _call_gemini(filename: str, content: bytes, mime_type: str | None) -> dict:
    """
    Send the document to Gemini and return the parsed JSON result.
    Raises on network / parsing errors — caller handles fallback.
    """
    if mime_type:
        file_part = Part.from_data(data=content, mime_type=mime_type)
        contents = [file_part, _PROMPT]
    else:
        # Unsupported binary format — send just filename context
        contents = [
            f"The uploaded file is named '{filename}' "
            f"({len(content)} bytes, format not directly readable). "
            f"Based on the filename alone, do your best. \n\n{_PROMPT}"
        ]

    response = _model.generate_content(contents, safety_settings=_SAFETY)
    result = _parse_gemini_json(response.text)

    # Validate / coerce key fields
    result["word_count"] = int(result.get("word_count", 0))
    result.setdefault("tags", ["unclassified"])
    result.setdefault("document_type", "other")
    result.setdefault("extracted_text", "")
    result.setdefault("entities", _EMPTY_ENTITIES)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def process_document(
    filename: str,
    content: bytes,
    processed_at: datetime | None = None,
) -> dict:
    """
    Extract rich metadata from a document using Gemini 1.5 Flash.

    Parameters
    ----------
    filename:     GCS object name (used for MIME detection and context).
    content:      Raw file bytes downloaded from Cloud Storage.
    processed_at: UTC timestamp; defaults to now.

    Returns
    -------
    dict with keys:
        filename, processed_at, tags, word_count,
        extracted_text, document_type, entities (JSON string)
    """
    if processed_at is None:
        processed_at = datetime.now(timezone.utc)

    mime_type = _detect_mime(filename)
    log.info("Processing '%s' | mime=%s | size=%d bytes", filename, mime_type, len(content))

    gemini_result: dict | None = None
    try:
        gemini_result = _call_gemini(filename, content, mime_type)
        log.info(
            "Gemini result | type=%s | words=%d | tags=%s",
            gemini_result["document_type"],
            gemini_result["word_count"],
            gemini_result["tags"],
        )
    except Exception as exc:
        # Fallback B: log warning, continue with empty AI fields
        log.warning("Gemini call failed for '%s': %s — saving row with empty AI fields.", filename, exc)

    if gemini_result:
        return {
            "filename":       filename,
            "processed_at":   processed_at.isoformat(),
            "tags":           gemini_result["tags"],
            "word_count":     gemini_result["word_count"],
            "extracted_text": gemini_result["extracted_text"][:3000],  # BQ string safety
            "document_type":  gemini_result["document_type"],
            "entities":       json.dumps(gemini_result["entities"], ensure_ascii=False),
        }

    # ── Fallback row (Gemini unavailable) ────────────────────────────────────
    return {
        "filename":       filename,
        "processed_at":   processed_at.isoformat(),
        "tags":           ["unclassified"],
        "word_count":     0,
        "extracted_text": "",
        "document_type":  "unknown",
        "entities":       json.dumps(_EMPTY_ENTITIES),
    }

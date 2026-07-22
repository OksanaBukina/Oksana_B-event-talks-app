# Serverless Event-Driven Document Processing Pipeline on Google Cloud

We will build a pipeline where:
1. A file is uploaded to Google Cloud Storage (GCS).
2. GCS publishes a notification to a Pub/Sub topic.
3. Pub/Sub triggers a Python-based Cloud Run service via a Push Subscription.
4. The Cloud Run service downloads the file, performs simulated OCR, extracts metadata, and streams it to a BigQuery table.

Based on your selections:
- **Infrastructure Provisioning**: We will write step-by-step manual console instructions.
- **Trigger Mechanism**: GCS Pub/Sub Notifications + Pub/Sub Push Subscription.
- **Python Web Framework**: FastAPI (Option A).
- **Simulated OCR**: Python simulation extracting text (Option A - reads txt/pdf/images, counts words, generates tags).

---

## Proposed Architecture & File Structure

Here is the project file structure we will create:

```
google-cloud-serverless-app/
├── processor/                  # Cloud Run service code
│   ├── main.py                 # FastAPI application server
│   ├── ocr.py                  # Simulated OCR logic
│   ├── requirements.txt        # Python packages
│   └── Dockerfile              # Docker container configuration
├── docs/
│   └── gcp_setup.md            # Step-by-step manual console instructions
└── README.md                   # Setup and usage guide
```

---

## Proposed Changes

### Processor Service

#### [NEW] [main.py](file:///d:/Education/Antigravity/google-cloud-serverless-app/processor/main.py)
A FastAPI HTTP server exposing a POST endpoint (`/webhook` or `/`) to receive the Pub/Sub push messages. It will:
- Parse the GCS event data (bucket, object name).
- Download the file from GCS.
- Run simulated OCR (`ocr.py`) to count words and extract tags.
- Insert a record into BigQuery with: `filename`, `date`, `tags` (array of strings), and `word_count`.

#### [NEW] [ocr.py](file:///d:/Education/Antigravity/google-cloud-serverless-app/processor/ocr.py)
Simulated OCR module:
- Reads text contents (or simulates reading for binary files).
- Extracts word counts and metadata.
- Automatically generates tags based on keywords or length.

#### [NEW] [Dockerfile](file:///d:/Education/Antigravity/google-cloud-serverless-app/processor/Dockerfile)
Packages the FastAPI application.

#### [NEW] [requirements.txt](file:///d:/Education/Antigravity/google-cloud-serverless-app/processor/requirements.txt)
Includes `fastapi`, `uvicorn`, `google-cloud-storage`, and `google-cloud-bigquery`.

### Documentation

#### [NEW] [gcp_setup.md](file:///d:/Education/Antigravity/google-cloud-serverless-app/docs/gcp_setup.md)
Detailed step-by-step manual instructions to provision the resources in GCP Console:
1. Create a Cloud Storage bucket.
2. Create a Pub/Sub topic and setup bucket notifications.
3. Create a BigQuery dataset and table.
4. Build and deploy the Cloud Run service.
5. Create a Pub/Sub Push subscription pointing to the Cloud Run service URL.
6. Configure necessary service accounts and permissions.

---

## Verification Plan

### Local Verification
We will run the FastAPI server locally and send a mock Pub/Sub request using `curl` or a test script to verify:
- Pub/Sub message parsing.
- GCS file download mock.
- Simulated OCR word count and tag generation.
- Mocked or real BigQuery insertion.

### GCP Verification
- Deploying the container to Cloud Run.
- Uploading a text document to the bucket.
- Querying BigQuery to verify the metadata insertion.

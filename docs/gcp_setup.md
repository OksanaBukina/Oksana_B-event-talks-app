# Руководство по настройке GCP Console

Пошаговые инструкции по развёртыванию всех ресурсов для **бессерверного конвейера обработки документов** исключительно через GCP Console (без CLI).

---

## Предварительные требования

| Элемент | Описание |
|---------|----------|
| Аккаунт GCP | С включённой оплатой |
| Проект GCP | Запомните **Project ID** — он понадобится на каждом шаге |
| API для включения | Cloud Storage, Pub/Sub, Cloud Run, BigQuery, Artifact Registry, Cloud Build |

### Включение API

1. Откройте [APIs & Services → Library](https://console.cloud.google.com/apis/library).
2. Найдите и **включите** каждый из следующих API:
   - `Cloud Storage API`
   - `Cloud Pub/Sub API`
   - `Cloud Run Admin API`
   - `BigQuery API`
   - `Artifact Registry API`
   - `Cloud Build API`
   - `Vertex AI API` ← **новый (для Gemini)**

---

## Шаг 1 — Создание бакета для загрузки файлов (Cloud Storage)

1. Перейдите в **Cloud Storage → Buckets** → **+ Create**.
2. Задайте глобально уникальное **Name**, например `doc-pipeline-ingest-<your-project-id>`.
3. Выберите предпочтительный **Region** (например `us-central1`). Используйте этот регион для всех ресурсов.
4. Оставьте остальные параметры по умолчанию и нажмите **Create**.

> [!NOTE]
> Запомните имя бакета — оно понадобится на шагах 2 и 6.

---

## Шаг 2 — Создание топика Pub/Sub

1. Перейдите в **Pub/Sub → Topics** → **+ Create Topic**.
2. Задайте **Topic ID**: `doc-pipeline-topic`.
3. Снимите галочку **Add a default subscription** (подписку вы создадите позже).
4. Нажмите **Create**.

---

## Шаг 3 — Выдача разрешения GCS на публикацию в Pub/Sub

GCS должен иметь право публиковать уведомления в ваш топик.

1. Перейдите в **Cloud Storage → Settings** и скопируйте email **сервисного аккаунта Cloud Storage** (он выглядит как `service-<project-number>@gs-project-accounts.iam.gserviceaccount.com`).
2. Перейдите в **Pub/Sub → Topics → `doc-pipeline-topic`**.
3. Нажмите **Permissions** (правая панель) → **+ Grant Access**.
4. В поле **New principals** вставьте скопированный email.
5. Назначьте роль **Pub/Sub Publisher** (`roles/pubsub.publisher`).
6. Нажмите **Save**.

---

## Шаг 4 — Настройка уведомлений бакета GCS

1. Перейдите в **Cloud Storage → Buckets → `doc-pipeline-ingest-<your-project-id>`**.
2. Нажмите на вкладку **Notifications** (или выберите **три точки → Edit notifications**).

> [!IMPORTANT]
> Уведомления бакета пока нельзя настроить напрямую через интерфейс GCP Console — требуется `gsutil` CLI или Cloud Storage JSON API. Используйте команду `gcloud` ниже (запускается в Cloud Shell — без локальной установки):

Откройте **Cloud Shell** (иконка терминала в правом верхнем углу Console) и выполните:

```bash
PROJECT_ID="<your-project-id>"
BUCKET_NAME="doc-pipeline-ingest-${PROJECT_ID}"
TOPIC="doc-pipeline-topic"

gcloud storage buckets notifications create \
  gs://${BUCKET_NAME} \
  --topic=projects/${PROJECT_ID}/topics/${TOPIC} \
  --event-types=OBJECT_FINALIZE \
  --payload-format=json
```

> [!NOTE]
> Cloud Shell — это браузерный терминал, **ничего устанавливать локально не нужно**. Это **единственная** команда в инструкции; всё остальное настраивается через интерфейс Console.

---

## Шаг 5 — Создание датасета и таблицы BigQuery

### 5a — Создание датасета

1. Перейдите в **BigQuery → Studio** → **+ Add → Create Dataset**.
2. Задайте **Dataset ID**: `document_pipeline`.
3. Выберите тот же **Region**, что и для бакета (например `us-central1`).
4. Нажмите **Create Dataset**.

### 5b — Создание таблицы

1. Внутри `document_pipeline` нажмите **+ Create Table**.
2. Задайте **Table name**: `document_metadata`.
3. В разделе **Schema** нажмите **Edit as text** и вставьте:

```json
[
  {"name": "filename",     "type": "STRING",    "mode": "REQUIRED"},
  {"name": "processed_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "tags",         "type": "STRING",    "mode": "REPEATED"},
  {"name": "word_count",   "type": "INTEGER",   "mode": "REQUIRED"}
]
```

4. Нажмите **Create Table**.

---

## Шаг 6 — Сборка и развёртывание сервиса Cloud Run

### 6a — Отправка образа контейнера через Cloud Build

1. Перейдите в **Artifact Registry → Repositories** → **+ Create Repository**.
   - Name: `doc-pipeline-repo`
   - Format: **Docker**
   - Region: тот же, что и у остальных ресурсов
   - Нажмите **Create**.
2. Откройте **Cloud Shell** и выполните:

```bash
PROJECT_ID="<your-project-id>"
REGION="us-central1"

# Если вы ещё не загрузили код — скопируйте папку processor/ в Cloud Shell
# через функцию загрузки файлов (три точки → Upload).

cd processor/

gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/doc-pipeline-repo/processor:latest \
  .
```

### 6b — Создание сервисного аккаунта для Cloud Run

1. Перейдите в **IAM & Admin → Service Accounts** → **+ Create Service Account**.
2. Задайте имя `doc-pipeline-sa`, нажмите **Create and Continue**.
3. Назначьте следующие роли:
   - `Storage Object Viewer` (`roles/storage.objectViewer`)
   - `BigQuery Data Editor` (`roles/bigquery.dataEditor`)
   - `BigQuery Job User` (`roles/bigquery.jobUser`)
4. Нажмите **Done**.

### 6c — Развёртывание сервиса Cloud Run

1. Перейдите в **Cloud Run → Services** → **+ Create Service**.
2. Выберите **Deploy one revision from an existing container image**.
3. Нажмите **Select** и выберите собранный образ: `REGION-docker.pkg.dev/<PROJECT_ID>/doc-pipeline-repo/processor:latest`.
4. Задайте **Service name**: `doc-processor`.
5. Укажите тот же **Region**, что и для остальных ресурсов.
6. В разделе **Authentication** выберите **Require authentication** (подписка Pub/Sub будет вызывать сервис с токеном).
7. Разверните раздел **Container, Volumes, Networking, Security**:
   - В **Container → Environment variables** добавьте:
     | Имя | Значение |
     |-----|----------|
     | `BQ_PROJECT` | `<your-project-id>` |
     | `BQ_DATASET` | `document_pipeline` |
     | `BQ_TABLE` | `document_metadata` |
   - В разделе **Security** выберите **Service account**: `doc-pipeline-sa`.
8. Нажмите **Create** и дождитесь появления URL сервиса. **Скопируйте URL**.

---

## Шаг 7 — Создание Push-подписки Pub/Sub

1. Перейдите в **Pub/Sub → Subscriptions** → **+ Create Subscription**.
2. Задайте **Subscription ID**: `doc-pipeline-push-sub`.
3. Выберите топик `doc-pipeline-topic`.
4. Установите **Delivery type**: **Push**.
5. В поле **Endpoint URL** введите `<CLOUD_RUN_URL>/webhook`.
6. Разверните раздел **Authentication** и выберите **Enable authentication**.
   - Service account: `doc-pipeline-sa`
   - Audience: оставьте пустым (заполняется автоматически).
7. Установите **Acknowledgement deadline**: `60 seconds`.
8. Нажмите **Create**.

---

## Шаг 8 — Выдача Pub/Sub разрешения на вызов Cloud Run

1. Перейдите в **Cloud Run → Services → `doc-processor`** → вкладка **Security**.
2. Нажмите **+ Grant Access**.
3. Добавьте сервисный агент Pub/Sub: `service-<project-number>@gcp-sa-pubsub.iam.gserviceaccount.com`
4. Роль: **Cloud Run Invoker** (`roles/run.invoker`).
5. Нажмите **Save**.

> [!TIP]
> Номер проекта можно найти в **IAM & Admin → Settings**.

---

## Проверка работы

### 1. Загрузите тестовый файл

1. Перейдите в **Cloud Storage → `doc-pipeline-ingest-<project-id>`**.
2. Нажмите **Upload files** и загрузите любой файл `.txt`.

### 2. Проверьте логи Cloud Run

1. Перейдите в **Cloud Run → `doc-processor` → Logs**.
2. Вы должны увидеть записи: `Event received`, `Downloaded X bytes`, `Metadata extracted` и `Row successfully inserted`.

### 3. Выполните запрос в BigQuery

1. Перейдите в **BigQuery → Studio**.
2. Выполните запрос:

```sql
SELECT *
FROM `<your-project-id>.document_pipeline.document_metadata`
ORDER BY processed_at DESC
LIMIT 10;
```

В результате должна появиться строка с именем файла, временной меткой, извлечёнными тегами и количеством слов.

---

## Схема архитектуры

```
Пользователь
     │
     │  загрузка файла
     ▼
Cloud Storage Bucket
     │
     │  уведомление OBJECT_FINALIZE
     ▼
Pub/Sub Topic (doc-pipeline-topic)
     │
     │  Push-доставка (HTTPS)
     ▼
Cloud Run Service (doc-processor)
     │                    │              │
     │ скачать файл        │ Gemini 1.5   │ вставить строку
     ▼                    ▼  Flash       ▼
Cloud Storage       Vertex AI        BigQuery
                  (классификация,  (document_metadata)
                   сущности, OCR)
```

---

## Шаг 9 — Gemini / Vertex AI: IAM и обновление схемы BigQuery

### 9a — Выдать роль Vertex AI сервисному аккаунту

1. Перейдите в **IAM & Admin → IAM** → [открыть](https://console.cloud.google.com/iam-admin/iam).
2. Найдите сервисный аккаунт `doc-pipeline-sa@<project-id>.iam.gserviceaccount.com`.
3. Нажмите на карандаш ✏️ (редактировать).
4. Добавьте роль: **Vertex AI User** (`roles/aiplatform.user`).
5. Нажмите **Save**.

> [!NOTE]
> Эта роль позволяет Cloud Run вызывать Gemini через Vertex AI API без дополнительных API-ключей.

### 9b — Обновить схему таблицы BigQuery

Добавьте 3 новых поля к существующей таблице `document_metadata`:

1. Перейдите в **BigQuery → Studio** → [открыть](https://console.cloud.google.com/bigquery).
2. В левой панели разверните: `<project-id>` → `document_pipeline` → `document_metadata`.
3. Нажмите на таблицу `document_metadata`, затем перейдите на вкладку **Schema**.
4. Нажмите кнопку **Edit Schema**.
5. Нажмите **+ Add field** три раза и заполните:

| Field name | Type | Mode | Описание |
|------------|------|------|----------|
| `extracted_text` | `STRING` | `NULLABLE` | Текст / описание документа от Gemini |
| `document_type` | `STRING` | `NULLABLE` | Тип документа (invoice, contract, resume…) |
| `entities` | `STRING` | `NULLABLE` | JSON со списками дат, имён, организаций, адресов, сумм |

6. Нажмите **Save**.

> [!IMPORTANT]
> BigQuery позволяет **добавлять** поля к существующей схеме без потери данных.
> Старые строки получат `NULL` в новых полях — это нормально.

### 9c — Пересобрать и передеплоить Cloud Run сервис

После изменения кода (`ocr.py`, `main.py`, `requirements.txt`) нужно пересобрать образ:

```bash
PROJECT_ID="elevated-analog-453314-j5"
REGION="us-central1"

cd processor/

gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/doc-pipeline-repo/processor:latest \
  .
```

Затем передеплоить Cloud Run сервис:

1. Перейдите в **Cloud Run → Services → `doc-processor`**.
2. Нажмите **Edit & Deploy New Revision**.
3. Убедитесь что выбран тег `:latest`.
4. Нажмите **Deploy**.

---

## Проверка Gemini-интеграции

### 1. Загрузите тестовый файл

Загрузите `.txt` файл с содержимым, например:
```
Invoice #1234
Date: 2024-03-15
Bill To: John Smith, Acme Corp, New York
Amount Due: $1,250.00
Due Date: 2024-04-01
```

### 2. Проверьте логи Cloud Run

В **Cloud Run → `doc-processor` → Logs** должны появиться записи:
```
Gemini result | type=invoice | words=24 | tags=['finance', 'payment']
Row successfully inserted into ...
```

### 3. Запросите BigQuery с новыми полями

```sql
SELECT
    filename,
    processed_at,
    document_type,
    tags,
    word_count,
    extracted_text,
    JSON_EXTRACT_SCALAR(entities, '$.dates[0]')         AS first_date,
    JSON_EXTRACT_SCALAR(entities, '$.names[0]')         AS first_name,
    JSON_EXTRACT_SCALAR(entities, '$.organizations[0]') AS first_org,
    JSON_EXTRACT_SCALAR(entities, '$.amounts[0]')       AS first_amount
FROM `elevated-analog-453314-j5.document_pipeline.document_metadata`
ORDER BY processed_at DESC
LIMIT 10;
```

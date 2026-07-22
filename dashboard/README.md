# Dashboard — Document Processing Pipeline

Streamlit-приложение для просмотра документов, обработанных конвейером Cloud Run.

## Возможности

- 📋 Таблица всех обработанных документов из BigQuery
- 🔍 Фильтрация по тегам (один или несколько)
- 📊 Фильтрация по диапазону количества слов
- 📈 Диаграмма распределения тегов
- 🔄 Кнопка ручного обновления данных

## Запуск локально

### 1. Установите зависимости

```bash
cd dashboard/
pip install -r requirements.txt
```

### 2. Авторизуйтесь в Google Cloud

```bash
gcloud auth application-default login
```

### 3. Запустите приложение

```bash
streamlit run app.py
```

Приложение откроется в браузере по адресу **http://localhost:8501**

---

## Переменные окружения (опционально)

По умолчанию используется проект `elevated-analog-453314-j5`. Для изменения:

```bash
export BQ_PROJECT="your-project-id"
export BQ_DATASET="document_pipeline"
export BQ_TABLE="document_metadata"

streamlit run app.py
```

## Если BigQuery пустой

Загрузите любой `.txt` файл в ваш бакет Cloud Storage:
```
doc-pipeline-ingest-1
```
Через несколько секунд строка появится в таблице.

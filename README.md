# 🚀 BigQuery Release Radar & Serverless GCP Suite

Комплексный проект на базе **Google Cloud Platform** и **Python**, включающий веб-приложение **BigQuery Release Radar** для отслеживания релизов BigQuery и публикаций в X (Twitter), а также событийный бессерверный конвейер **Serverless Document Processing Pipeline**.

---

## 📌 Основные компоненты проекта

### 1. 📡 BigQuery Release Radar (Flask Web Application)
Веб-приложение на **Python (Flask)**, **HTML5**, **CSS3** и **Vanilla JavaScript**, которое подключается к официальному Atom-фиду Google Cloud и в режиме реального времени отображает обновления BigQuery.

- **Сбор обновлений в реальном времени**: автоматический парсинг RSS/Atom фида (`https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`) с серверным кэшированием (5 минут).
- **Кнопка обновления с спиннером**: повторный запрос к фиду и мгновенное обновление списка новостей без перезагрузки страницы.
- **Интерактивный конструктор твитов**:
  - Публикация любого обновления в X (Twitter) в один клик через `https://twitter.com/intent/tweet`.
  - **Всплывающий поповер для выделенного текста**: при выделении мышью любого фрагмента текста на карточке релиза появляется кнопка *«Tweet Selection»*.
  - Динамический счетчик 280 символов с интерактивным прогресс-кольцом и предупреждением о превышении лимита.
  - Автоматическая подгонка текста (*Auto-Fit*) под лимит и переключаемые хэштеги (`#BigQuery`, `#GoogleCloud`, `#DataEngineering`).
- **Современный UI/UX**:
  - Поддержка **Темной** и **Светлой** темы (с сохранением предпочтения в `localStorage`).
  - Живой поиск и фильтрация по категориям (*Features*, *Changed*, *Issues*, *Deprecated*).
  - Информационная панель статистики с подсчетом количества релизов и категорий.

---

### 2. ⚡ Serverless Document Processing Pipeline
Бессерверный событийный конвейер обработки документов в Google Cloud Platform.

```
Пользователь → Cloud Storage → Pub/Sub → Cloud Run → BigQuery
              (загрузка)     (событие)  (FastAPI/OCR) (хранение)
```

- **Cloud Storage (GCS)**: приём загружаемых документов.
- **Pub/Sub**: отправка событий `OBJECT_FINALIZE` при создании файлов.
- **Cloud Run (FastAPI + Docker)**: обработка текстов, симуляция OCR и извлечение семантических тегов.
- **BigQuery**: хранение структурированных метаданных документов.

---

## 🛠 Структура проекта

```
Oksana_B-event-talks-app/
├── app.py                      # Flask веб-сервер BigQuery Release Radar
├── templates/
│   └── index.html              # HTML5 интерфейс приложения
├── static/
│   ├── css/
│   │   └── style.css           # CSS стили, переменные тем, анимации
│   └── js/
│       └── app.js              # JS логика: поиск, фильтры, Tweet Composer, поповер
├── processor/
│   ├── main.py                 # FastAPI вебхук для обработки файлов из GCS
│   ├── ocr.py                  # Модуль OCR и извлечения тегов
│   ├── Dockerfile              # Dockerfile для сборки контейнера Cloud Run
│   └── requirements.txt        # Зависимости сервиса обработки
├── dashboard/                  # Streamlit аналитическая панель
├── docs/
│   └── gcp_setup.md            # Инструкция по настройке ресурсов в GCP Console
├── .gitignore                  # Файл исключений Git
├── README.md                   # Документация проекта
└── upload_to_drive.py          # Скрипт интеграции с Google Drive
```

---

## 🚀 Быстрый запуск

### 1. Запуск веб-приложения BigQuery Release Radar

```bash
# Клонирование репозитория
git clone https://github.com/OksanaBukina/Oksana_B-event-talks-app.git
cd Oksana_B-event-talks-app

# Установка зависимостей
pip install flask

# Запуск Flask сервера
python app.py
```

Откройте браузер по адресу: **`http://127.0.0.1:5000`**

---

### 2. Запуск сервиса обработки документов (FastAPI)

```bash
cd processor

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
export BQ_PROJECT="your-gcp-project-id"
export BQ_DATASET="document_pipeline"
export BQ_TABLE="document_metadata"

# Запуск FastAPI сервера
uvicorn main:app --reload --port 8080
```

Интерактивная документация API доступна по адресу: `http://localhost:8080/docs`

---

## 📄 Схема метаданных BigQuery

| Поле | Тип | Описание |
|---|---|---|
| `filename` | STRING | Путь к файлу в бакете GCS |
| `processed_at` | TIMESTAMP | Время обработки (UTC) |
| `tags` | STRING (REPEATED) | Семантические теги, извлеченные из файла |
| `word_count` | INTEGER | Количество слов в документе |

---

## 🔗 Ссылки и авторство

- **Автор**: [OksanaBukina](https://github.com/OksanaBukina)
- **GitHub Репозиторий**: [Oksana_B-event-talks-app](https://github.com/OksanaBukina/Oksana_B-event-talks-app)

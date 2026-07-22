"""
app.py — Streamlit dashboard for the Document Processing Pipeline.

Displays documents processed by Cloud Run + Gemini and stored in BigQuery.
Supports filtering by tag, document type, date range, and word count.
"""

import json
import os
import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Document Processing Dashboard",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BQ_PROJECT = os.environ.get("BQ_PROJECT", "elevated-analog-453314-j5")
BQ_DATASET = os.environ.get("BQ_DATASET", "document_pipeline")
BQ_TABLE   = os.environ.get("BQ_TABLE",   "document_metadata")
TABLE_ID   = f"`{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`"

DOC_TYPE_EMOJI = {
    "invoice":     "🧾",
    "contract":    "📑",
    "resume":      "👤",
    "report":      "📊",
    "letter":      "✉️",
    "image":       "🖼️",
    "spreadsheet": "📈",
    "medical":     "🏥",
    "legal":       "⚖️",
    "other":       "📄",
    "unknown":     "❓",
}

# ─────────────────────────────────────────────────────────────────────────────
# BigQuery client
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_bq_client():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=BQ_PROJECT, credentials=creds)
    return bigquery.Client(project=BQ_PROJECT)


@st.cache_data(ttl=30, show_spinner=False)
def load_data() -> pd.DataFrame:
    client = get_bq_client()
    query = f"""
        SELECT
            filename,
            TIMESTAMP_TRUNC(processed_at, SECOND) AS processed_at,
            tag,
            word_count,
            COALESCE(document_type, 'unknown')  AS document_type,
            COALESCE(extracted_text, '')         AS extracted_text,
            COALESCE(entities, '{{}}')           AS entities
        FROM {TABLE_ID},
        UNNEST(tags) AS tag
        ORDER BY processed_at DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=30, show_spinner=False)
def load_filter_options() -> tuple[list[str], list[str]]:
    client = get_bq_client()
    tags_q = f"SELECT DISTINCT tag FROM {TABLE_ID}, UNNEST(tags) AS tag ORDER BY tag"
    type_q = f"SELECT DISTINCT COALESCE(document_type,'unknown') AS t FROM {TABLE_ID} ORDER BY t"
    tags  = client.query(tags_q).to_dataframe()["tag"].tolist()
    types = client.query(type_q).to_dataframe()["t"].tolist()
    return tags, types


# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp {
        background: linear-gradient(135deg, #0f0c29, #1a1a2e, #16213e);
        color: #e2e8f0;
    }
    [data-testid="stSidebar"] {
        background: rgba(255,255,255,0.04);
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* Header */
    .dashboard-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 28px;
        box-shadow: 0 8px 32px rgba(102,126,234,0.3);
    }
    .dashboard-header h1 { margin:0; font-size:2rem; font-weight:700; color:white; }
    .dashboard-header p  { margin:6px 0 0; color:rgba(255,255,255,0.8); font-size:.95rem; }

    /* Metric cards */
    .metric-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: transform .2s, box-shadow .2s;
    }
    .metric-card:hover { transform:translateY(-2px); box-shadow:0 8px 24px rgba(0,0,0,.3); }
    .metric-value { font-size:2rem; font-weight:700; color:#a78bfa; }
    .metric-label { font-size:.8rem; color:rgba(255,255,255,.55); text-transform:uppercase; letter-spacing:.05em; margin-top:4px; }

    /* Section titles */
    .section-title {
        font-size:1rem; font-weight:600; color:rgba(255,255,255,.9);
        margin:20px 0 12px; padding-bottom:6px;
        border-bottom:1px solid rgba(255,255,255,.1);
    }

    /* Doc type pill */
    .doc-type-pill {
        display:inline-block;
        background: rgba(102,126,234,0.25);
        border: 1px solid rgba(102,126,234,0.5);
        color:#a78bfa;
        padding:3px 12px; border-radius:20px;
        font-size:.8rem; font-weight:600;
    }

    /* Entity section */
    .entity-group { margin-bottom:10px; }
    .entity-label { font-size:.75rem; color:rgba(255,255,255,.5); text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }
    .entity-chip {
        display:inline-block;
        background:rgba(255,255,255,0.07);
        border:1px solid rgba(255,255,255,0.12);
        color:#e2e8f0; padding:2px 10px;
        border-radius:6px; font-size:.8rem; margin:2px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color:white; border:none; border-radius:8px;
        padding:8px 20px; font-weight:600; width:100%;
        transition: opacity .2s;
    }
    .stButton > button:hover { opacity:.85; }

    /* Empty state */
    .empty-state { text-align:center; padding:60px 20px; color:rgba(255,255,255,.4); }
    .empty-state .icon { font-size:3rem; margin-bottom:12px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dashboard-header">
    <h1>📄 Document Processing Dashboard</h1>
    <p>Powered by Gemini 1.5 Flash · Cloud Run · BigQuery</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Загрузка данных из BigQuery…"):
    try:
        df_raw = load_data()
        all_tags, all_doc_types = load_filter_options()
        load_error = None
    except Exception as e:
        df_raw = pd.DataFrame()
        all_tags, all_doc_types = [], []
        load_error = str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Filters
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Фильтры")

    # Tag filter
    st.markdown('<div class="section-title">По тегу</div>', unsafe_allow_html=True)
    selected_tags = st.multiselect(
        "Tags", options=all_tags, default=[], placeholder="Все теги",
        label_visibility="collapsed",
    )

    # Document type filter
    st.markdown('<div class="section-title">По типу документа</div>', unsafe_allow_html=True)
    type_options = [f"{DOC_TYPE_EMOJI.get(t, '📄')} {t}" for t in all_doc_types]
    selected_type_labels = st.multiselect(
        "Doc type", options=type_options, default=[], placeholder="Все типы",
        label_visibility="collapsed",
    )
    selected_types = [lbl.split(" ", 1)[1] for lbl in selected_type_labels]

    # Word count range
    st.markdown('<div class="section-title">Количество слов</div>', unsafe_allow_html=True)
    if not df_raw.empty and df_raw["word_count"].max() > 0:
        min_wc = int(df_raw["word_count"].min())
        max_wc = int(df_raw["word_count"].max())
        if min_wc == max_wc:
            max_wc = min_wc + 1
        wc_range = st.slider("wc", min_value=min_wc, max_value=max_wc,
                             value=(min_wc, max_wc), label_visibility="collapsed")
    else:
        wc_range = (0, 10000)

    st.markdown("---")
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

    st.markdown(
        f"<div style='color:rgba(255,255,255,0.3);font-size:0.75rem;margin-top:12px;'>"
        f"Project: {BQ_PROJECT}<br>{BQ_DATASET}.{BQ_TABLE}</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Error state
# ─────────────────────────────────────────────────────────────────────────────
if load_error:
    st.error(f"❌ Не удалось подключиться к BigQuery:\n\n```\n{load_error}\n```")
    st.info("Авторизуйтесь: `gcloud auth application-default login`")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Apply filters
# ─────────────────────────────────────────────────────────────────────────────
df = df_raw.copy()

if selected_tags:
    df = df[df["tag"].isin(selected_tags)]
if selected_types:
    df = df[df["document_type"].isin(selected_types)]
df = df[(df["word_count"] >= wc_range[0]) & (df["word_count"] <= wc_range[1])]

# Collapse to one row per file
if not df.empty:
    df_display = (
        df.groupby(["filename", "processed_at", "word_count",
                    "document_type", "extracted_text", "entities"], as_index=False)
        .agg(tags=("tag", lambda x: ", ".join(sorted(set(x)))))
        [["filename", "processed_at", "document_type", "tags", "word_count",
          "extracted_text", "entities"]]
    )
else:
    df_display = pd.DataFrame(columns=[
        "filename", "processed_at", "document_type",
        "tags", "word_count", "extracted_text", "entities"
    ])


# ─────────────────────────────────────────────────────────────────────────────
# KPI metrics
# ─────────────────────────────────────────────────────────────────────────────
total_docs  = df_display.shape[0]
total_words = int(df["word_count"].sum()) if not df.empty else 0
unique_tags = df["tag"].nunique() if not df.empty else 0
doc_types   = df["document_type"].nunique() if not df.empty else 0

col1, col2, col3, col4 = st.columns(4)
for col, value, label in [
    (col1, total_docs,  "Документов"),
    (col2, unique_tags, "Уникальных тегов"),
    (col3, doc_types,   "Типов документов"),
    (col4, total_words, "Всего слов"),
]:
    with col:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{value:,}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Documents table
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📋 Обработанные документы</div>', unsafe_allow_html=True)

if df_display.empty:
    st.markdown("""
    <div class="empty-state">
        <div class="icon">🗂️</div>
        <p>Нет документов по выбранным фильтрам.<br>
        Загрузите файл в Cloud Storage бакет.</p>
    </div>""", unsafe_allow_html=True)
else:
    # Table (hide raw extracted_text and entities columns)
    table_cols = ["filename", "processed_at", "document_type", "tags", "word_count"]
    st.dataframe(
        df_display[table_cols].rename(columns={
            "filename":      "📁 Файл",
            "processed_at":  "🕐 Обработан",
            "document_type": "📂 Тип",
            "tags":          "🏷️ Теги",
            "word_count":    "📝 Слов",
        }),
        use_container_width=True,
        hide_index=True,
        column_config={
            "📁 Файл":     st.column_config.TextColumn(width="large"),
            "🕐 Обработан": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
            "📝 Слов":     st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption(f"Показано {len(df_display):,} документ(ов)")

    # ── Document detail expanders ──────────────────────────────────────────
    st.markdown('<div class="section-title">🔎 Детали документа</div>', unsafe_allow_html=True)

    for _, row in df_display.iterrows():
        doc_emoji = DOC_TYPE_EMOJI.get(row["document_type"], "📄")
        label = f"{doc_emoji} **{row['filename']}** — {row['document_type']} · {row['word_count']} слов"

        with st.expander(label):
            col_a, col_b = st.columns([1, 1])

            with col_a:
                st.markdown("**📝 Извлечённый текст / описание**")
                text = row.get("extracted_text", "")
                if text:
                    st.text_area("", value=text, height=200, disabled=True,
                                 label_visibility="collapsed")
                else:
                    st.caption("Текст не извлечён (Gemini fallback)")

            with col_b:
                st.markdown("**🗂️ Сущности**")
                try:
                    entities = json.loads(row.get("entities", "{}") or "{}")
                except json.JSONDecodeError:
                    entities = {}

                entity_labels = {
                    "dates":         "📅 Даты",
                    "names":         "👤 Имена",
                    "organizations": "🏢 Организации",
                    "locations":     "📍 Местоположения",
                    "amounts":       "💰 Суммы",
                }
                has_entities = False
                for key, label_str in entity_labels.items():
                    items = entities.get(key, [])
                    if items:
                        has_entities = True
                        chips = "".join(f'<span class="entity-chip">{i}</span>' for i in items)
                        st.markdown(
                            f'<div class="entity-group">'
                            f'<div class="entity-label">{label_str}</div>'
                            f'{chips}</div>',
                            unsafe_allow_html=True,
                        )
                if not has_entities:
                    st.caption("Сущности не найдены")

            st.markdown(f"**🏷️ Теги:** `{row['tags']}`")
            st.markdown(f"**🕐 Обработан:** {row['processed_at']}")


# ─────────────────────────────────────────────────────────────────────────────
# Charts
# ─────────────────────────────────────────────────────────────────────────────
if not df.empty:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown('<div class="section-title">🏷️ Распределение тегов</div>', unsafe_allow_html=True)
        tag_counts = df.groupby("tag")["filename"].nunique().reset_index()
        tag_counts.columns = ["Тег", "Документов"]
        st.bar_chart(tag_counts.set_index("Тег"), color="#667eea", use_container_width=True)

    with chart_col2:
        st.markdown('<div class="section-title">📂 Типы документов</div>', unsafe_allow_html=True)
        type_counts = df.groupby("document_type")["filename"].nunique().reset_index()
        type_counts.columns = ["Тип", "Документов"]
        type_counts["Тип"] = type_counts["Тип"].apply(
            lambda t: f"{DOC_TYPE_EMOJI.get(t, '📄')} {t}"
        )
        st.bar_chart(type_counts.set_index("Тип"), color="#764ba2", use_container_width=True)

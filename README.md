# 🛡️ Incident Intelligence Dashboard

Real-time incident monitoring dashboard built with **Streamlit** + **Supabase** + **Claude AI**.

---

## Project structure

```
incident_dashboard/
├── app.py                        # Main dashboard entry point
├── requirements.txt
├── .streamlit/
│   └── secrets.toml              # Your credentials (never commit this!)
└── utils/
    ├── supabase_client.py        # Supabase connection & data fetching
    ├── charts.py                 # All Plotly & WordCloud chart functions
    └── chatbot.py                # Claude AI analyst chatbot
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure credentials
```bash
mkdir -p .streamlit
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Then edit .streamlit/secrets.toml with your real keys
```

Your `.streamlit/secrets.toml` should look like:
```toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
key = "your-anon-public-key"        # Found in Supabase → Settings → API

[anthropic]
api_key = "sk-ant-..."              # From console.anthropic.com
```

### 3. Supabase table schema
Your Supabase table (default name: `incidents`) should have these columns:

| Column | Type |
|---|---|
| id | int8 / uuid |
| title | text |
| publication_date | timestamptz |
| source | text |
| url | text |
| summary | text |
| relevant_keywords | text |
| category | text |
| country | text |
| impact | text |
| incident_type | text |
| entity_affected | text |
| incident_date | timestamptz |

> If your table has a different name, change `get_data("incidents")` in `app.py`.

### 4. Run the dashboard
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## Features

| Feature | Description |
|---|---|
| **KPI Cards** | Total incidents, sources, critical count, countries, new this week |
| **Category Bar Chart** | Horizontal bar — incidents per category |
| **Incident Type Donut** | Pie/donut by incident_type |
| **Timeline Area Chart** | Weekly trend, stacked by category |
| **Impact Funnel** | Critical → High → Medium → Low |
| **Choropleth Map** | World map coloured by incident count per country |
| **Source Breakdown** | Top crawled sources |
| **Word Clouds** | Summary text & relevant_keywords columns |
| **Raw Data Table** | Filterable, sortable incident table |
| **AI Chatbot** | Claude-powered analyst; answers questions about the loaded data |
| **Sidebar Filters** | Date range, category, country, impact |
| **Auto-refresh** | Toggle 60-second live refresh |

---

## Adding deep learning predictions

In `app.py`, after the charts section add:

```python
from utils.predictor import render_predictions   # your DL module
st.markdown("<div class='section-header'>🔮 Predictions</div>", unsafe_allow_html=True)
render_predictions(df)
```

Create `utils/predictor.py` with your model loading and inference logic.
The filtered `df` DataFrame is passed in automatically.

---

## Free deployment on Streamlit Community Cloud

1. Push your project to a **public** GitHub repo  
   (make sure `.streamlit/secrets.toml` is in `.gitignore`)
2. Go to https://share.streamlit.io → **New app**
3. Select your repo and set `app.py` as the main file
4. Add your secrets under **Advanced settings → Secrets**
5. Click **Deploy** — free, no credit card needed

---

## Cost summary (all free tiers)

| Service | Free tier |
|---|---|
| Supabase | 500 MB DB, 2 GB bandwidth / month |
| Streamlit Community Cloud | Unlimited public apps |
| Anthropic API | Pay-per-use (chatbot only triggers on user questions) |

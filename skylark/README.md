# Skylark Drones — Monday.com Business Intelligence Agent

A Python conversational BI agent that answers founder-level questions across **Deals (pipeline)** and **Work Orders (operations)** boards.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Streamlit  │────▶│   BI Agent   │────▶│ BusinessAnalytics│
│     UI      │     │ (NL parser)  │     │  + Leadership    │
└─────────────┘     └──────┬───────┘     └────────▲────────┘
                           │                        │
                    ┌──────▼───────┐         ┌──────┴───────┐
                    │ DataRepository│────────▶│ Data Cleaner │
                    └──────┬───────┘         └──────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      Monday.com API              Local Excel
      (production)                (dev/fallback)
```

## Features

- **Monday.com integration** — read-only GraphQL client
- **Data resilience** — normalizes dates, sectors, statuses; handles nulls
- **Query understanding** — keyword/intent parser with clarifying questions
- **Business intelligence** — pipeline, revenue, sector, operations, owner metrics
- **Leadership updates** — one-click executive brief
- **Optional OpenAI** — richer narrative answers when `OPENAI_API_KEY` is set

## Quick Start (Local)

```bash
cd skylark
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

Open http://localhost:8501

## Monday.com Setup

1. Create two boards: **Deals** and **Work Orders**
2. Import the provided Excel files (or use `scripts/import_to_monday.py`)
3. Generate an API token: Monday.com → Profile → Admin → API
4. Configure `.env`:

```env
DATA_SOURCE=monday
MONDAY_API_TOKEN=your_token
MONDAY_DEALS_BOARD_ID=1234567890
MONDAY_WORK_ORDERS_BOARD_ID=0987654321
```

5. Restart the app and select **monday** as data source in the sidebar

### Recommended column types (Deals)

| Column | Type |
|--------|------|
| Deal Status | Status |
| Deal Stage | Status |
| Sector/service | Dropdown |
| Masked Deal value | Numbers |
| Closure Probability | Dropdown |
| Close / Tentative Close / Created Date | Date |

### Recommended column types (Work Orders)

| Column | Type |
|--------|------|
| Execution Status | Status |
| Sector | Dropdown |
| Contract / Billed / Collected amounts | Numbers |
| PO / Start / End dates | Date |

## Hosting (Streamlit Cloud)

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy `app.py`
4. Add secrets (`MONDAY_API_TOKEN`, board IDs, optional `OPENAI_API_KEY`)

## Example Questions

- *How's our pipeline looking for Mining this quarter?*
- *What's our revenue and billing status?*
- *Show sector performance*
- *Prepare a leadership update*
- *How is OWNER_001 performing?*

## Project Structure

```
skylark/
├── app.py                  # Streamlit UI
├── src/
│   ├── config.py
│   ├── data/               # Loaders, cleaner, Monday client
│   ├── bi/                 # Analytics + leadership brief
│   └── agent/              # Query parser + responder
├── scripts/import_to_monday.py
├── data/                   # Excel sample files
├── DECISION_LOG.md
└── requirements.txt
```

## License

Assignment prototype for Skylark Drones / Amity University.

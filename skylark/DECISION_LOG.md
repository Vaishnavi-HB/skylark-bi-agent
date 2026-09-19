# Decision Log — Skylark BI Agent

## Key Assumptions

1. **Energy sector ≈ Renewables** — When founders ask about "energy," we map to the Renewables vertical (largest energy-adjacent segment in the data).
2. **Masked values are analytics-ready** — Deal and billing amounts are treated as INR despite masking; relative comparisons remain valid.
3. **Quarter filter uses tentative/close dates** — Open pipeline for "this quarter" filters on `tentative_close_date` or `close_date` within the current calendar quarter.
4. **Missing closure probability → 25% weight** — For weighted pipeline, open deals without probability use a conservative default and we disclose this.
5. **Work Orders header row** — The WO Excel file has headers in row 0; we promote that row before cleaning.

## Trade-offs

| Choice | Why | Cost |
|--------|-----|------|
| **Streamlit over FastAPI+React** | Fastest path to a hosted, conversational demo within 6 hours | Less customizable UI |
| **Rule-based NLU + optional LLM** | Works offline; LLM only polishes answers | Less flexible than full LLM agent |
| **Local Excel fallback** | Enables development without Monday credentials | Must switch `DATA_SOURCE=monday` for production eval |
| **Read-only Monday API** | Matches assignment constraint; simpler auth | No write-back or board setup automation |
| **Pandas analytics vs SQL/DB** | Dataset size (~500 rows) fits in memory; simpler deploy | Won't scale to very large boards without refactor |

## Leadership Updates — Interpretation

We implemented **"Prepare data for leadership updates"** as a one-click **Executive Brief** that includes:

- Headline summary (pipeline + billed revenue)
- Pipeline breakdown with data caveats
- Operations/revenue snapshot
- Top 3 sectors by open pipeline
- Top 5 at-risk open deals (low probability, missing dates/values)
- Data quality flags for the founder

This is exportable markdown suitable for email, Notion, or Monday.com docs.

## What I'd Do With More Time

1. **Monday MCP server** — Native MCP tooling for board discovery and column mapping
2. **Column mapping config** — JSON map from Monday column IDs to canonical fields (boards vary)
3. **Automated tests** — Golden-file tests for cleaner and query parser
4. **Caching layer** — Redis/in-memory TTL cache for Monday API pagination
5. **Full LLM agent** — Tool-calling agent that selects analytics functions dynamically
6. **Auth on hosted demo** — Simple password gate for Streamlit Cloud deployment

## Data Quality Observations

- **52% of deals** missing closure probability — weighted pipeline uses defaults
- **52% of deals** missing deal value — excluded from value sums where null
- **Work Orders billing fields** heavily sparse — revenue metrics are directional, not audit-grade
- Duplicate header strings (`Deal Status`, `Sector/service`) appear as data rows — filtered during cleaning

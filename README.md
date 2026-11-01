# ArthLens

ArthLens is a Streamlit financial dashboard for exploring transactions from a CSV,
reviewing cash flow, and optionally asking Sarvam AI questions about aggregate
financial figures.

## Run locally

Use Python 3.10 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The dashboard starts in demo mode and does not require an API key. To use the AI
analyst, create a `.env` file in the project directory:

```text
SARVAM_API_KEY=your_sarvam_api_key
```

Keep `.env` private; it is excluded from version control.

## Import transactions

Upload a CSV with these required columns:

| Column | Meaning |
| --- | --- |
| `date` | Transaction date |
| `description` | Short transaction label |
| `amount` | Signed INR amount; income is positive and expenses are negative |

Headers are case-insensitive. Rows with an invalid date, description, or amount
are skipped and counted in the dashboard. The selected date range filters the
metrics, charts, transaction table, download, and AI analysis.

## Backend and privacy

`backend.py` contains CSV normalization, categorization, cash-flow aggregation,
and the Sarvam AI integration. AI prompts include aggregate totals and expense
category totals, not individual transaction descriptions. AI output is for
informational analysis only and is not investment advice.

## Tests

Run the backend unit tests with:

```powershell
python -m unittest -v
```

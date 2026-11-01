import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from backend import (
    analyze_transactions,
    ask_financial_question,
    categorize,
    prepare_transactions,
    sample_data,
)

load_dotenv()

st.set_page_config(
    page_title="ArthLens | Financial Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    .stApp { background: #0b1120; color: #e5e7eb; }
    [data-testid="stSidebar"] { background: #101a2b; }
    [data-testid="stMetric"] {
        background: #151f32;
        border: 1px solid #26344d;
        border-radius: 12px;
        padding: 18px;
    }
    [data-testid="stMetricLabel"] { color: #9fb0c9; }
    h1, h2, h3 { color: #f1f5f9; }
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def get_api_key() -> str | None:
    api_key = os.getenv("SARVAM_API_KEY")
    if api_key:
        return api_key.strip()

    try:
        secret = st.secrets["SARVAM_API_KEY"]
        return secret.strip() if secret else None
    except (KeyError, StreamlitSecretNotFoundError):
        return None


st.sidebar.markdown("# ARTHLENS")
st.sidebar.caption("FINANCIAL INTELLIGENCE")
st.sidebar.divider()
st.sidebar.markdown("### Your data")
uploaded_file = st.sidebar.file_uploader(
    "Upload transaction CSV",
    type=["csv"],
    help="Required columns: date, description, amount. Positive amounts are income.",
)
st.sidebar.caption(
    "Your transactions stay in this app. Only aggregate totals are sent to Sarvam "
    "when you request an AI analysis."
)
st.sidebar.divider()
st.sidebar.caption("Demo mode uses illustrative sample transactions.")

if uploaded_file is None:
    raw_data = sample_data()
    source_label = "Illustrative demo data"
else:
    source_label = uploaded_file.name
    try:
        raw_data = pd.read_csv(uploaded_file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
        st.error(f"Could not read this CSV. Check the file encoding and formatting. ({error})")
        st.stop()

try:
    transactions, rejected_rows = prepare_transactions(raw_data)
except ValueError as error:
    st.error(str(error))
    st.stop()

date_min = transactions["date"].min().date()
date_max = transactions["date"].max().date()
selected_period = st.sidebar.date_input(
    "Date range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max,
)

if isinstance(selected_period, tuple) and len(selected_period) == 2:
    start_date, end_date = selected_period
else:
    start_date = end_date = selected_period

filtered = transactions.loc[
    transactions["date"].dt.date.between(start_date, end_date)
].copy()

st.title("📊 ArthLens")
st.markdown("### See the story behind your money.")
st.caption(
    f"{source_label} · {len(transactions):,} valid transactions · "
    f"{date_min:%d %b %Y} – {date_max:%d %b %Y}"
)

if rejected_rows:
    st.warning(
        f"{rejected_rows:,} row(s) were skipped because their date, description, "
        "or amount was missing or invalid."
    )

if filtered.empty:
    st.info("There are no transactions in the selected date range.")
    st.stop()

summary = analyze_transactions(filtered)

metric_columns = st.columns(4)
metric_columns[0].metric("Total income", format_inr(summary["income"]))
metric_columns[1].metric("Total expenses", format_inr(summary["expenses"]))
metric_columns[2].metric(
    "Net cash flow",
    format_inr(summary["net_cashflow"]),
)
metric_columns[3].metric("Transactions", f'{summary["transaction_count"]:,}')

if summary["income"] > 0:
    st.caption(
        f"Net cash flow is {summary['net_cashflow'] / summary['income']:.1%} "
        "of income for the selected period."
    )

st.divider()
chart_left, chart_right = st.columns([1.35, 1])

with chart_left:
    st.subheader("Cash flow over time")
    monthly = summary["monthly"]
    if monthly.empty:
        st.info("Not enough data to show a cash-flow chart.")
    else:
        monthly_chart = px.bar(
            monthly,
            x="month",
            y="amount",
            color="type",
            barmode="group",
            color_discrete_map={
                "Income": "#22c55e",
                "Expense": "#f97316",
                "Neutral": "#94a3b8",
            },
            labels={"amount": "Amount (₹)", "month": "Month", "type": ""},
        )
        monthly_chart.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b1120",
            plot_bgcolor="#0b1120",
            margin=dict(l=8, r=8, t=24, b=8),
            legend_title_text="",
        )
        st.plotly_chart(monthly_chart, use_container_width=True)

with chart_right:
    st.subheader("Where expenses go")
    category_summary = summary["expense_categories"]
    if category_summary.empty:
        st.info("No expenses in the selected date range.")
    else:
        expense_chart = px.pie(
            category_summary,
            names="category",
            values="amount",
            hole=0.58,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        expense_chart.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0b1120",
            margin=dict(l=8, r=8, t=12, b=8),
            showlegend=True,
        )
        st.plotly_chart(expense_chart, use_container_width=True)

st.divider()
table_header, download_column = st.columns([3, 1])
with table_header:
    st.subheader("Transactions")
    st.caption("Search, sort, and review transactions in the selected date range.")
with download_column:
    export_data = filtered[
        ["date", "description", "category", "type", "amount"]
    ].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=export_data,
        file_name="arthlens-transactions.csv",
        mime="text/csv",
        use_container_width=True,
    )

display_data = filtered.sort_values("date", ascending=False).copy()
display_data["date"] = display_data["date"].dt.strftime("%d %b %Y")
display_data["amount"] = display_data["amount"].map(lambda value: f"₹{value:,.2f}")
st.dataframe(
    display_data[["date", "description", "category", "type", "amount"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("✨ ArthLens AI analyst")
st.caption(
    "Ask a question about this period. Sarvam receives aggregate figures only, "
    "not your individual transaction descriptions."
)

with st.form("financial_question_form"):
    question = st.text_area(
        "Your question",
        placeholder="What changed my cash flow this month?",
        max_chars=500,
        height=90,
    )
    analyze_button = st.form_submit_button(
        "Analyse with Sarvam AI",
        type="primary",
    )

if analyze_button:
    st.session_state.pop("analysis_result", None)
    if not question.strip():
        st.warning("Enter a question before requesting an analysis.")
    else:
        api_key = get_api_key()
        if not api_key:
            st.error(
                "Sarvam AI is not configured. Add SARVAM_API_KEY to your .env "
                "file or Streamlit secrets to enable analysis."
            )
        else:
            try:
                with st.spinner("Analysing your financial summary…"):
                    answer = ask_financial_question(question, summary, api_key)
                st.session_state["analysis_result"] = {
                    "answer": answer,
                    "signature": (
                        int(pd.util.hash_pandas_object(filtered).sum()),
                        start_date,
                        end_date,
                    ),
                }
            except Exception as error:
                st.error(
                    f"Sarvam AI analysis failed ({type(error).__name__}): {error}"
                )

analysis = st.session_state.get("analysis_result")
current_signature = (
    int(pd.util.hash_pandas_object(filtered).sum()),
    start_date,
    end_date,
)
if analysis and analysis["signature"] == current_signature:
    st.markdown("#### Analysis")
    st.write(analysis["answer"])

st.divider()
st.caption("ArthLens · Financial insights for understanding, not investment advice.")

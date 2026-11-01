import math
import os
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {"date", "description", "amount"}


def sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [
                "2026-10-01",
                "2026-10-02",
                "2026-10-03",
                "2026-10-05",
                "2026-10-07",
                "2026-10-09",
                "2026-10-11",
                "2026-10-13",
                "2026-10-15",
                "2026-10-17",
                "2026-10-19",
                "2026-10-21",
                "2026-10-23",
                "2026-10-25",
                "2026-10-27",
                "2026-10-29",
                "2026-10-30",
                "2026-10-31",
            ],
            "description": [
                "Client payment",
                "Office rent",
                "Groceries",
                "Electricity bill",
                "Product sales",
                "Uber travel",
                "Restaurant",
                "Supplier payment",
                "Client payment",
                "Internet bill",
                "Shopping",
                "Raw materials",
                "Product sales",
                "Medical expenses",
                "Fuel",
                "Client payment",
                "Restaurant",
                "Supplier payment",
            ],
            "amount": [
                85000,
                -18000,
                -4200,
                -3500,
                42000,
                -900,
                -1800,
                -12000,
                65000,
                -1200,
                -5500,
                -14500,
                38000,
                -2500,
                -2200,
                55000,
                -1600,
                -9000,
            ],
        }
    )


def categorize(description: str) -> str:
    normalized = str(description).casefold()
    rules = {
        "Food": ("grocery", "groceries", "restaurant", "food"),
        "Housing": ("rent", "mortgage"),
        "Utilities": ("electricity", "internet", "utility", "bill"),
        "Transport": ("uber", "fuel", "travel", "taxi", "transport"),
        "Shopping": ("shopping", "amazon", "retail"),
        "Healthcare": ("medical", "hospital", "healthcare", "pharmacy"),
        "Operations": ("supplier", "raw material", "inventory", "business"),
        "Income": ("client", "sales", "salary", "payment received"),
    }

    for category, keywords in rules.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "Other"


def prepare_transactions(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        raise ValueError("The CSV does not contain any transactions.")

    transactions = frame.copy()
    transactions.columns = [
        str(column).strip().casefold() for column in transactions.columns
    ]

    duplicated_columns = transactions.columns[transactions.columns.duplicated()].tolist()
    if duplicated_columns:
        duplicates = ", ".join(sorted(set(duplicated_columns)))
        raise ValueError(f"The CSV contains duplicate column names: {duplicates}.")

    missing_columns = REQUIRED_COLUMNS.difference(transactions.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"CSV is missing required column(s): {missing}. "
            "Required columns are date, description, and amount."
        )

    transactions["date"] = pd.to_datetime(
        transactions["date"],
        errors="coerce",
        utc=True,
    ).dt.tz_convert(None)
    transactions["description"] = (
        transactions["description"].fillna("").astype(str).str.strip()
    )
    amount_text = (
        transactions["amount"]
        .astype("string")
        .str.replace(r"[,\s₹]", "", regex=True)
    )
    transactions["amount"] = pd.to_numeric(amount_text, errors="coerce")

    valid_rows = (
        transactions["date"].notna()
        & transactions["description"].ne("")
        & transactions["amount"].notna()
        & transactions["amount"].map(
            lambda amount: math.isfinite(float(amount)) if pd.notna(amount) else False
        )
    )
    rejected_rows = int((~valid_rows).sum())
    transactions = transactions.loc[valid_rows].copy()

    if transactions.empty:
        raise ValueError(
            f"No valid transactions found; {rejected_rows} row(s) were rejected."
        )

    transactions["category"] = transactions["description"].map(categorize)
    transactions["type"] = transactions["amount"].map(
        lambda amount: "Income"
        if amount > 0
        else "Expense"
        if amount < 0
        else "Neutral"
    )
    return transactions.sort_values("date").reset_index(drop=True), rejected_rows


def analyze_transactions(transactions: pd.DataFrame) -> dict[str, Any]:
    if transactions.empty:
        raise ValueError("There are no transactions to analyse.")

    income = float(transactions.loc[transactions["amount"] > 0, "amount"].sum())
    expenses = float(-transactions.loc[transactions["amount"] < 0, "amount"].sum())
    monthly_source = transactions.assign(
        month=transactions["date"].dt.to_period("M").astype(str),
        amount=transactions["amount"].abs(),
    )
    monthly = (
        monthly_source.groupby(["month", "type"], as_index=False)["amount"]
        .sum()
        .sort_values("month")
    )

    expense_categories = (
        transactions.loc[transactions["amount"] < 0]
        .assign(amount=lambda data: data["amount"].abs())
        .groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )

    return {
        "income": income,
        "expenses": expenses,
        "net_cashflow": income - expenses,
        "transaction_count": int(len(transactions)),
        "monthly": monthly,
        "expense_categories": expense_categories,
        "period_start": transactions["date"].min().date().isoformat(),
        "period_end": transactions["date"].max().date().isoformat(),
    }


def ask_financial_question(
    question: str,
    summary: dict[str, Any],
    api_key: str | None = None,
) -> str:
    if not question.strip():
        raise ValueError("The question cannot be empty.")

    configured_key = (api_key or os.getenv("SARVAM_API_KEY") or "").strip()
    if not configured_key:
        raise ValueError("SARVAM_API_KEY is not configured.")

    from sarvamai import SarvamAI

    category_data = summary["expense_categories"]
    expense_breakdown = (
        category_data.to_dict(orient="records") if not category_data.empty else []
    )
    prompt = f"""
You are ArthLens, a financial analysis assistant.
Use only the aggregate figures below, all in Indian rupees (INR).
Do not invent missing information or give investment advice. Mention limitations.

Period: {summary["period_start"]} to {summary["period_end"]}
Total income: {summary["income"]}
Total expenses: {summary["expenses"]}
Net cash flow: {summary["net_cashflow"]}
Transaction count: {summary["transaction_count"]}
Expense categories: {expense_breakdown}

User question: {question.strip()}
"""

    client = SarvamAI(api_subscription_key=configured_key)
    response = client.chat.completions(
        model="sarvam-105b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
    )
    answer = response.choices[0].message.content
    if not answer or not answer.strip():
        raise RuntimeError("Sarvam returned an empty analysis.")
    return answer.strip()

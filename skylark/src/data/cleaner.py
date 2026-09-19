"""Normalize messy Monday.com / Excel data for analytics."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

HEADER_VALUES = {
    "deal status",
    "deal name",
    "sector/service",
    "closure probability",
    "deal name masked",
    "execution status",
}

SECTOR_ALIASES = {
    "renewable": "Renewables",
    "renewables": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "mining": "Mining",
    "railway": "Railways",
    "railways": "Railways",
    "powerline": "Powerline",
    "power line": "Powerline",
    "construction": "Construction",
    "energy": "Renewables",
    "others": "Others",
    "other": "Others",
    "dsp": "DSP",
    "tender": "Tender",
    "manufacturing": "Manufacturing",
    "security and surveillance": "Security and Surveillance",
    "aviation": "Aviation",
}

STATUS_ALIASES = {
    "won": "Won",
    "open": "Open",
    "dead": "Dead",
    "lost": "Dead",
    "on hold": "On Hold",
    "hold": "On Hold",
}

PROBABILITY_ALIASES = {
    "high": "High",
    "medium": "Med",
    "med": "Med",
    "low": "Low",
}


def _is_header_row(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in HEADER_VALUES


def _clean_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or _is_header_row(text):
        return None
    return text


def normalize_sector(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    key = re.sub(r"\s+", " ", text.lower())
    return SECTOR_ALIASES.get(key, text.title())


def normalize_status(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return STATUS_ALIASES.get(text.lower(), text)


def normalize_probability(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return PROBABILITY_ALIASES.get(text.lower(), text)


def parse_date(value: Any) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, datetime):
        return pd.Timestamp(value)

    text = str(value).strip()
    if not text or text.lower() in {"nat", "none", "nan", "-"}:
        return None

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return pd.Timestamp(datetime.strptime(text[:10], fmt))
        except ValueError:
            continue

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    return None if pd.isna(parsed) else parsed


def parse_numeric(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text or text in {"nan", "none", "-", "na"}:
        return None

    text = re.sub(r"[₹,\s]", "", text)
    text = re.sub(r"[^\d.\-]", "", text)
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def clean_deals(df: pd.DataFrame) -> pd.DataFrame:
    """Clean deals / pipeline board data."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    rename_map = {
        "Deal Name": "deal_name",
        "Owner code": "owner_code",
        "Client Code": "client_code",
        "Deal Status": "deal_status",
        "Close Date (A)": "close_date",
        "Closure Probability": "closure_probability",
        "Masked Deal value": "deal_value",
        "Tentative Close Date": "tentative_close_date",
        "Deal Stage": "deal_stage",
        "Product deal": "product",
        "Sector/service": "sector",
        "Created Date": "created_date",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    for col in ["deal_name", "owner_code", "client_code", "deal_stage", "product"]:
        if col in out.columns:
            out[col] = out[col].map(_clean_text)

    if "deal_status" in out.columns:
        out["deal_status"] = out["deal_status"].map(normalize_status)
    if "sector" in out.columns:
        out["sector"] = out["sector"].map(normalize_sector)
    if "closure_probability" in out.columns:
        out["closure_probability"] = out["closure_probability"].map(normalize_probability)

    for col in ["close_date", "tentative_close_date", "created_date"]:
        if col in out.columns:
            out[col] = out[col].map(parse_date)

    if "deal_value" in out.columns:
        out["deal_value"] = out["deal_value"].map(parse_numeric)

    if "deal_name" in out.columns:
        out = out[~out["deal_name"].isna()].copy()

    out["data_quality_notes"] = out.apply(_deals_quality_note, axis=1)
    return out.reset_index(drop=True)


def _deals_quality_note(row: pd.Series) -> str | None:
    issues = []
    if pd.isna(row.get("deal_value")):
        issues.append("missing value")
    if pd.isna(row.get("closure_probability")) and row.get("deal_status") == "Open":
        issues.append("missing probability")
    if pd.isna(row.get("tentative_close_date")) and row.get("deal_status") == "Open":
        issues.append("missing close date")
    return "; ".join(issues) if issues else None


def clean_work_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Clean work orders board data."""
    out = df.copy()

    if out.iloc[0].astype(str).str.contains("Deal name masked", case=False, na=False).any():
        out.columns = out.iloc[0]
        out = out.iloc[1:].reset_index(drop=True)

    out.columns = [str(c).strip() for c in out.columns]

    rename_map = {
        "Deal name masked": "deal_name",
        "Customer Name Code": "client_code",
        "Serial #": "serial_no",
        "Nature of Work": "nature_of_work",
        "Execution Status": "execution_status",
        "Data Delivery Date": "data_delivery_date",
        "Date of PO/LOI": "po_date",
        "Probable Start Date": "start_date",
        "Probable End Date": "end_date",
        "BD/KAM Personnel code": "owner_code",
        "Sector": "sector",
        "Type of Work": "type_of_work",
        "Amount in Rupees (Excl of GST) (Masked)": "contract_value_ex_gst",
        "Amount in Rupees (Incl of GST) (Masked)": "contract_value_incl_gst",
        "Billed Value in Rupees (Excl of GST.) (Masked)": "billed_ex_gst",
        "Billed Value in Rupees (Incl of GST.) (Masked)": "billed_incl_gst",
        "Collected Amount in Rupees (Incl of GST.) (Masked)": "collected",
        "Amount Receivable (Masked)": "receivable",
        "WO Status (billed)": "wo_status",
        "Billing Status": "billing_status",
        "Collection status": "collection_status",
        "Invoice Status": "invoice_status",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    for col in ["deal_name", "client_code", "serial_no", "nature_of_work", "execution_status",
                "type_of_work", "wo_status", "billing_status", "collection_status", "invoice_status"]:
        if col in out.columns:
            out[col] = out[col].map(_clean_text)

    if "sector" in out.columns:
        out["sector"] = out["sector"].map(normalize_sector)

    for col in ["data_delivery_date", "po_date", "start_date", "end_date"]:
        if col in out.columns:
            out[col] = out[col].map(parse_date)

    for col in ["contract_value_ex_gst", "contract_value_incl_gst", "billed_ex_gst",
                "billed_incl_gst", "collected", "receivable"]:
        if col in out.columns:
            out[col] = out[col].map(parse_numeric)

    if "deal_name" in out.columns:
        out = out[~out["deal_name"].isna()].copy()

    out["data_quality_notes"] = out.apply(_wo_quality_note, axis=1)
    return out.reset_index(drop=True)


def _wo_quality_note(row: pd.Series) -> str | None:
    issues = []
    if pd.isna(row.get("contract_value_ex_gst")):
        issues.append("missing contract value")
    if pd.isna(row.get("billed_ex_gst")):
        issues.append("missing billed value")
    if pd.isna(row.get("execution_status")):
        issues.append("missing execution status")
    return "; ".join(issues) if issues else None

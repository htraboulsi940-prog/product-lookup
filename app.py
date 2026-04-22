import re
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
CSV_FILE = "products.csv"
BUSINESS_PHONE = "+220 4033340"

# Expected CSV columns:
# - Product Name
# - Keywords
# - Units
# - Price
#
# Stock status can come from one of these columns if present:
# - In Stock
# - Availability
# - Stock Status
# - Status
#
# Optional extra columns are fine.


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase and remove extra punctuation/spaces for easier matching."""
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def parse_keywords(row: pd.Series) -> List[str]:
    """Build a list of searchable terms from Product Name + Keywords."""
    product_name = normalize_text(row.get("Product Name", ""))
    raw_keywords = str(row.get("Keywords", "") or "")

    keywords = [normalize_text(product_name)] if product_name else []
    for keyword in raw_keywords.split(","):
        cleaned = normalize_text(keyword)
        if cleaned:
            keywords.append(cleaned)

    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    return unique_keywords


def score_match(query: str, keywords: List[str]) -> int:
    """
    Simple scoring:
    - exact keyword match gets highest score
    - substring matches score based on keyword length
    - token overlap gives partial score
    """
    if not query or not keywords:
        return 0

    query_tokens = set(query.split())
    best_score = 0

    for keyword in keywords:
        if query == keyword:
            best_score = max(best_score, 100)
            continue

        if keyword in query or query in keyword:
            best_score = max(best_score, 50 + len(keyword))
            continue

        keyword_tokens = set(keyword.split())
        overlap = len(query_tokens.intersection(keyword_tokens))
        if overlap > 0:
            best_score = max(best_score, overlap * 10)

    return best_score


def normalize_stock_value(value) -> bool:
    """Convert common stock formats into True/False."""
    text = normalize_text(value)
    if text in {"yes", "y", "true", "1", "in stock", "available", "available in stock", "instock", "availability yes"}:
        return True
    if text in {"no", "n", "false", "0", "out of stock", "unavailable", "sold out"}:
        return False

    try:
        return float(value) > 0
    except Exception:
        return False


def detect_stock_column(df: pd.DataFrame) -> Optional[str]:
    """Prefer an explicit stock-status column over deriving from units."""
    stock_column_candidates = ["In Stock", "Availability", "Stock Status", "Status"]
    for col in stock_column_candidates:
        if col in df.columns:
            return col
    return None

    try:
        return float(value) > 0
    except Exception:
        return False


def format_price(value) -> str:
    """Format price consistently for display."""
    try:
        number = float(str(value).replace(",", ""))
        if number.is_integer():
            return f"{int(number):,}"
        return f"{number:,.2f}"
    except Exception:
        return str(value)


@st.cache_data

def load_products(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)

    required_columns = {"Product Name", "Keywords", "Units", "Price"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing_columns))}"
        )

    stock_column = detect_stock_column(df)
    if stock_column is None:
        raise ValueError(
            "Missing stock column. Add one of these columns: In Stock, Availability, Stock Status, Status"
        )

    df = df.copy()
    df["_stock_source_column"] = stock_column
    df["_keywords_list"] = df.apply(parse_keywords, axis=1)
    df["_stock_bool"] = df[stock_column].apply(normalize_stock_value)
    df["_product_name_norm"] = df["Product Name"].apply(normalize_text)
    return df


def find_matching_rows(query: str, df: pd.DataFrame, min_score: int = 10) -> pd.DataFrame:
    query_norm = normalize_text(query)
    if not query_norm:
        return df.iloc[0:0].copy()

    scored_rows = []

    for _, row in df.iterrows():
        score = score_match(query_norm, row["_keywords_list"])
        if score >= min_score:
            row_dict = row.to_dict()
            row_dict["_match_score"] = score
            scored_rows.append(row_dict)

    if not scored_rows:
        return df.iloc[0:0].copy()

    results_df = pd.DataFrame(scored_rows)
    results_df = results_df.sort_values(
        by=["_match_score", "_stock_bool", "Units"],
        ascending=[False, False, False]
    )
    return results_df


def build_single_response(row: pd.Series) -> str:
    product_name = row["Product Name"]
    price = format_price(row["Price"])
    in_stock = row["_stock_bool"]

    if in_stock:
        return f"{product_name} is available. Price: {price} dalasis."
    return f"{product_name} is currently out of stock. Please call {BUSINESS_PHONE}."


def build_multiple_response(matches_df: pd.DataFrame) -> List[str]:
    responses = []
    for _, row in matches_df.iterrows():
        status = "In stock" if row["_stock_bool"] else "Out of stock"
        price = format_price(row["Price"])
        responses.append(
            f"- {row['Product Name']} — {status} — {price} dalasis"
        )
    return responses


# ------------------------------------------------------------
# App
# ------------------------------------------------------------

st.set_page_config(page_title="Product Lookup Prototype", page_icon="🛒")
st.image(r"C:\\Users\\htrab\\Malak_Chat Bot_Project\\Logo.jpeg", width=200)
st.title("Check Product Availability & Prices")
st.caption("Search for a product to see availability and price")

st.markdown(
    """
    Type the product name below.
    If we find a match, we will show availability and price.
    If not, please call +220 4033340.
    """
)

try:
    products_df = load_products(CSV_FILE)
except FileNotFoundError:
    st.error(
        "products.csv was not found. Export your Google Sheet as CSV and save it in the same folder as this script."
    )
    st.stop()
except Exception as exc:
    st.error(f"Error loading file: {exc}")
    st.stop()

query = st.text_input(
    "Customer query",
    placeholder="e.g. aferin, abidec, accu chek strips",
)

if query:
    matches_df = find_matching_rows(query, products_df)

    if not matches_df.empty:
        if len(matches_df) == 1:
            best_match = matches_df.iloc[0]
            st.write(build_single_response(best_match))
        else:
            st.write("We found these matching products:")
            for response_line in build_multiple_response(matches_df):
                st.write(response_line)
    else:
        st.warning(f"Sorry, we could not find that product. Please call {BUSINESS_PHONE}.")

st.divider()



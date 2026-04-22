import re
from typing import List
import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
CSV_FILE = "products.csv"
BUSINESS_PHONE = "+220 4033340"

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def parse_keywords(row: pd.Series) -> List[str]:
    product_name = normalize_text(row.get("Product Name", ""))
    raw_keywords = str(row.get("Keywords", "") or "")

    keywords = [product_name] if product_name else []

    for keyword in raw_keywords.split(","):
        cleaned = normalize_text(keyword)
        if cleaned:
            keywords.append(cleaned)

    return list(dict.fromkeys(keywords))


def score_match(query: str, keywords: List[str]) -> int:
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


def is_in_stock(units_value) -> bool:
    try:
        return float(units_value) > 0
    except Exception:
        return False


def format_price(value) -> str:
    try:
        number = float(str(value).replace(",", ""))
        if number.is_integer():
            return f"{int(number):,}"
        return f"{number:,.2f}"
    except Exception:
        return str(value)


# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------

def load_products(csv_file: str) -> pd.DataFrame:
    df = pd.read_csv(csv_file)

    required_columns = {"Product Name", "Keywords", "Units", "Price"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")

    df = df.copy()
    df["_keywords_list"] = df.apply(parse_keywords, axis=1)
    df["_stock_bool"] = df["Units"].apply(is_in_stock)
    return df


def find_matching_rows(query: str, df: pd.DataFrame, min_score: int = 10) -> pd.DataFrame:
    query_norm = normalize_text(query)

    results = []

    for _, row in df.iterrows():
        score = score_match(query_norm, row["_keywords_list"])
        if score >= min_score:
            r = row.to_dict()
            r["_match_score"] = score
            results.append(r)

    if not results:
        return pd.DataFrame()

    df_results = pd.DataFrame(results)

    return df_results.sort_values(
        by=["_match_score", "_stock_bool", "Units"],
        ascending=[False, False, False]
    )


# ------------------------------------------------------------
# App UI
# ------------------------------------------------------------

st.set_page_config(page_title="Product Lookup", page_icon="🛒")

# Logo (must be in same folder as this file)
st.image("Logo.jpeg", width=200)

st.title("Check Product Availability & Prices")

st.markdown(
    """
    Find out if a product is available and see the price instantly.

    Type the product name below (e.g. aferin, abidec, accu chek).
    """
)

# ------------------------------------------------------------
# Main logic
# ------------------------------------------------------------

try:
    products_df = load_products(CSV_FILE)
except Exception as e:
    st.error(str(e))
    st.stop()

query = st.text_input("Search for a product")

if query:
    matches = find_matching_rows(query, products_df)

    if not matches.empty:

        if len(matches) == 1:
            row = matches.iloc[0]

            if row["_stock_bool"]:
                st.success(f"✅ {row['Product Name']} is available")
                st.write(f"Price: {format_price(row['Price'])} dalasis")
            else:
                st.error(f"❌ {row['Product Name']} is out of stock")
                st.write(f"Please call {BUSINESS_PHONE}")

        else:
            st.write("We found these matching products:")

            for _, row in matches.iterrows():
                if row["_stock_bool"]:
                    st.success(f"{row['Product Name']} — {format_price(row['Price'])} dalasis")
                else:
                    st.warning(f"{row['Product Name']} — Out of stock")

    else:
        st.warning(f"Sorry, we could not find that product. Please call {BUSINESS_PHONE}.")
import re
import argparse
from io import StringIO
from typing import Any, Dict, Iterable, List

import pandas as pd
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nutrition-charts.com/",
}

RESTAURANTS = [
    {
        "name": "McDonald's",
        "url": "https://www.nutrition-charts.com/mcdonalds-nutrition-facts/",
    },
    {
        "name": "Burger King",
        "url": "https://www.nutrition-charts.com/burger-king-nutritional-information/",
    },
    {
        "name": "Taco Bell",
        "url": "https://www.nutrition-charts.com/taco-bell-nutrition-facts/",
    },
    {
        "name": "Chipotle",
        "url": "https://www.nutrition-charts.com/chipotle-nutrition-facts/",
    },
    {
        "name": "Chick-fil-A",
        "url": "https://www.nutrition-charts.com/chick-fil-a-nutrition-information/",
    },
    {
        "name": "Jimmy John's",
        "url": "https://www.nutrition-charts.com/jimmy-johns-nutrition-facts/",
    },
]

COLUMN_SYNONYMS = {
    "calories": {"calories"},
    "protein": {"protein", "protein_g"},
    "carbohydrates": {"carbs", "carbs_g", "total_carbs", "total_carbs_g"},
    "fat": {"total_fat", "total_fat_g", "fat", "fat_g"},
}

IGNORED_ITEMS = {"daily value", "weight watchers pnts", "total", "totals", "serving size", "menu item"}

TRANSLATION_MAP = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "\u2013": "-",
        "\u2014": "-",
    }
)


def flatten_columns(columns) -> List[str]:
    if isinstance(columns, pd.MultiIndex):
        flattened: List[str] = []
        for tup in columns:
            parts = [str(part) for part in tup if pd.notna(part)]
            flattened.append(" ".join(parts).strip())
        return flattened
    return [str(col) for col in columns]


def normalize_header(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text)
    text = text.translate(TRANSLATION_MAP)
    text = text.replace("\u00ae", "")
    text = text.replace("\u2122", "")
    text = text.replace("\xa0", " ")
    text = text.replace("\ufffd", "")
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_").lower()


def clean_menu_item(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).translate(TRANSLATION_MAP)
    text = text.replace("\u00ae", "")
    text = text.replace("\u2122", "")
    text = text.replace("\ufffd", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_number(value: Any) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, float) and pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = re.search(r"-?\d*\.?\d+", text)
    if not match:
        return float("nan")
    return float(match.group())


def extract_records(table: pd.DataFrame, restaurant: str) -> List[Dict[str, Any]]:
    raw_columns = flatten_columns(table.columns)
    cleaned_columns = [normalize_header(col) for col in raw_columns]
    table = table.copy()
    table.columns = cleaned_columns
    first_col = table.columns[0]
    table = table.rename(columns={first_col: "menu_item"})
    records: List[Dict[str, Any]] = []
    for _, row in table.iterrows():
        menu_item = clean_menu_item(row.get("menu_item"))
        if not menu_item:
            continue
        lower_item = menu_item.lower()
        if lower_item in IGNORED_ITEMS:
            continue
        record: Dict[str, Any] = {
            "Restaurant": restaurant,
            "Menu Item": menu_item,
        }
        for key, aliases in COLUMN_SYNONYMS.items():
            value = float("nan")
            for alias in aliases:
                if alias in row.index and not pd.isna(row[alias]):
                    value = to_number(row[alias])
                    break
            record[key.capitalize()] = value
        if all(pd.isna(record[col]) for col in ("Calories", "Protein", "Carbohydrates", "Fat")):
            continue
        records.append(record)
    return records


def scrape_restaurant(name: str, url: str) -> List[Dict[str, Any]]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - network errors
        print(f"Warning: {name} at {url} returned HTTP error: {exc}")
        return []
    except requests.RequestException as exc:  # pragma: no cover - network errors
        print(f"Warning: request to {url} for {name} failed: {exc}")
        return []
    try:
        tables = pd.read_html(StringIO(response.text))
    except ValueError:
        print(f"Warning: no tables detected for {name} at {url}")
        return []
    records: List[Dict[str, Any]] = []
    for table in tables:
        records.extend(extract_records(table, name))
    return records


def scrape_nutrition(pages: Iterable[Dict[str, str]]) -> pd.DataFrame:
    all_records: List[Dict[str, Any]] = []
    for page in pages:
        all_records.extend(scrape_restaurant(page["name"], page["url"]))
    df = pd.DataFrame(all_records)
    if df.empty:
        return pd.DataFrame(
            columns=["Restaurant", "Menu Item", "Calories", "Protein", "Carbohydrates", "Fat"]
        )
    numeric_cols = ["Calories", "Protein", "Carbohydrates", "Fat"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["Restaurant", "Menu Item", "Calories", "Protein", "Carbohydrates", "Fat"]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape nutrition data from nutrition-charts.com."
    )
    parser.add_argument(
        "--output",
        default="fast_food_nutrition.csv",
        help="Path for the generated CSV file.",
    )
    args = parser.parse_args()

    dataframe = scrape_nutrition(RESTAURANTS)
    dataframe.to_csv(args.output, index=False)
    if dataframe.empty:
        print(f"No data scraped; wrote headers to {args.output}")
    else:
        print(f"Saved {len(dataframe)} rows to {args.output}")
        print()
        print(dataframe.head(20).to_string(index=False))
        print(f"\nTotal rows: {len(dataframe)}")

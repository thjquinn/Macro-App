
import streamlit as st
import pandas as pd
import numpy as np
import re
from itertools import combinations

st.set_page_config(page_title="MacroFinder – Rule-Based Fast Food Finder", layout="wide")

@st.cache_data
def load_data(path: str):
    df = pd.read_csv(path)
    df = df.rename(columns={
        "Menu Item": "Item",
        "Carbohydrates": "Carbs",
        "Protein": "Protein",
        "Calories": "Calories",
        "Fat": "Fat",
        "Restaurant": "Restaurant"
    })
    # Ensure numeric
    for c in ["Calories", "Protein", "Carbs", "Fat"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Calories", "Protein", "Carbs", "Fat"])
    df["Restaurant"] = df["Restaurant"].astype(str).str.strip()
    df["Item"] = df["Item"].astype(str).str.strip()
    return df

df = load_data("fast_food_nutrition_updated.csv")

st.title("🍔 MacroFinder: Rule-Based Fast Food Finder")
st.write("Say things like **'over 30 grams of protein and under 600 calories'** or use the sidebar to set exact rules.")

# -----------------------------
# Helper: parse simple natural-language constraints
# -----------------------------
NAMES = {
    "calories": "Calories",
    "calorie": "Calories",
    "protein": "Protein",
    "proteins": "Protein",
    "carbs": "Carbs",
    "carb": "Carbs",
    "fat": "Fat",
    "fats": "Fat"
}

OPS_MAP = {
    "over": ">=",
    "at least": ">=",
    ">=": ">=",
    "greater than or equal to": ">=",
    "greater than": ">",
    ">": ">",

    "under": "<=",
    "at most": "<=",
    "<=": "<=",
    "less than or equal to": "<=",
    "less than": "<",
    "<": "<",

    "exactly": "==",
    "equal to": "==",
    "=": "==",
}

def parse_freeform(q: str):
    """
    Lightweight parser for patterns like:
      - "over 30 grams of protein and under 600 calories"
      - "protein >= 30, calories < 600"
      - "between 20 and 40g protein"
    Returns a list of dicts: [{'col': 'Protein', 'op': '>=', 'val': 30}, ...]
    """
    if not q or not q.strip():
        return []

    text = q.lower()
    constraints = []

    # between A and B (macro)
    for m in re.finditer(r"between\s+(\d+(?:\.\d+)?)\s*(?:g|grams|kcal)?\s*(?:and|-)\s*(\d+(?:\.\d+)?)\s*(?:g|grams|kcal)?\s*(calories|calorie|protein|proteins|carbs|carb|fat|fats)", text):
        a = float(m.group(1)); b = float(m.group(2))
        col = NAMES[m.group(3)]
        lo, hi = sorted([a, b])
        constraints.append({"col": col, "op": ">=", "val": lo})
        constraints.append({"col": col, "op": "<=", "val": hi})

    # simple "over/under/equal" phrases like "over 30 grams of protein"
    for phrase, op in OPS_MAP.items():
        # forms: "<phrase> 30 (g|grams)? (of)? protein"
        pattern = rf"{re.escape(phrase)}\s+(\d+(?:\.\d+)?)\s*(?:g|grams|kcal)?\s*(?:of\s+)?(calories|calorie|protein|proteins|carbs|carb|fat|fats)"
        for m in re.finditer(pattern, text):
            val = float(m.group(1))
            col = NAMES[m.group(2)]
            constraints.append({"col": col, "op": op.strip(), "val": val})

        # forms: "protein < 30", "calories >= 600"
        pattern2 = rf"(calories|calorie|protein|proteins|carbs|carb|fat|fats)\s*{re.escape(phrase)}\s*(\d+(?:\.\d+)?)"
        for m in re.finditer(pattern2, text):
            col = NAMES[m.group(1)]
            val = float(m.group(2))
            constraints.append({"col": col, "op": op.strip(), "val": val})

    # de-duplicate identical constraints
    unique = []
    seen = set()
    for c in constraints:
        key = (c["col"], c["op"], c["val"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique

# -----------------------------
# Sidebar: Rule builder & app options
# -----------------------------
with st.sidebar:
    st.header("🧠 Optional: Type your rule")
    free_q = st.text_input("e.g., 'over 30g protein and under 600 calories'")

    st.caption("Or use the rule builder below:")
    st.markdown("---")

    def rule_block(label):
        st.subheader(label)
        use = st.checkbox(f"Enable {label}", value=(label in ["Protein", "Calories"]))  # default enable Protein & Calories
        op = st.selectbox(f"{label} operator", ["≥", "≤", "=", ">", "<", "between"], index=0, key=f"op_{label}")
        if op == "between":
            v1 = st.number_input(f"{label} min", min_value=0.0, value=0.0, step=1.0, key=f"{label}_min")
            v2 = st.number_input(f"{label} max", min_value=0.0, value=9999.0, step=1.0, key=f"{label}_max")
            vals = (v1, v2)
        else:
            default = 30.0 if label=="Protein" else (600.0 if label=="Calories" else 0.0)
            v = st.number_input(f"{label} value", min_value=0.0, value=default, step=1.0, key=f"{label}_val")
            vals = (v,)
        return {"use": use, "op": op, "vals": vals}

    rule_cal = rule_block("Calories")
    rule_pro = rule_block("Protein")
    rule_carb = rule_block("Carbs")
    rule_fat = rule_block("Fat")

    st.markdown("---")
    st.header("🍽️ Filters")
    restaurants = ["All"] + sorted(df["Restaurant"].unique().tolist())
    restaurant_filter = st.selectbox("Restaurant", restaurants, index=0)
    mode = st.radio("Match type", ["Single Item", "2-Item Combo"], horizontal=True)
    same_restaurant = st.checkbox("For combos: require same restaurant", value=True)

    st.markdown("---")
    st.header("↕️ Sorting")
    sort_col = st.selectbox("Sort by", ["Protein", "Calories", "Carbs", "Fat"])
    ascending = st.checkbox("Ascending order", value=False)

    max_results = st.slider("Max results to show", 5, 200, 50, 5)

# -----------------------------
# Build constraints from UI and free-form text
# -----------------------------
constraints = []

# From free-form parser
constraints += parse_freeform(free_q)

# From rule builder
def ui_to_constraints(label, rule):
    if not rule["use"]:
        return []
    col = label
    op = rule["op"]
    vals = rule["vals"]
    out = []
    if op == "≥":
        out.append({"col": col, "op": ">=", "val": float(vals[0])})
    elif op == "≤":
        out.append({"col": col, "op": "<=", "val": float(vals[0])})
    elif op == "=":
        out.append({"col": col, "op": "==", "val": float(vals[0])})
    elif op == ">":
        out.append({"col": col, "op": ">", "val": float(vals[0])})
    elif op == "<":
        out.append({"col": col, "op": "<", "val": float(vals[0])})
    elif op == "between":
        lo, hi = sorted([float(vals[0]), float(vals[1])])
        out.append({"col": col, "op": ">=", "val": lo})
        out.append({"col": col, "op": "<=", "val": hi})
    return out

constraints += ui_to_constraints("Calories", rule_cal)
constraints += ui_to_constraints("Protein", rule_pro)
constraints += ui_to_constraints("Carbs", rule_carb)
constraints += ui_to_constraints("Fat", rule_fat)

# Apply restaurant filter
filtered = df.copy()
if restaurant_filter != "All":
    filtered = filtered[filtered["Restaurant"] == restaurant_filter]

# -----------------------------
# Filtering functions
# -----------------------------
def apply_constraints_frame(frame: pd.DataFrame, constraints_list):
    if not constraints_list:
        return frame
    mask = pd.Series(True, index=frame.index)
    for c in constraints_list:
        col, op, val = c["col"], c["op"], c["val"]
        if op == ">=":
            mask &= frame[col] >= val
        elif op == "<=":
            mask &= frame[col] <= val
        elif op == "==":
            mask &= frame[col] == val
        elif op == ">":
            mask &= frame[col] > val
        elif op == "<":
            mask &= frame[col] < val
    return frame[mask]

# -----------------------------
# Run search
# -----------------------------
if mode == "Single Item":
    out = apply_constraints_frame(filtered, constraints).copy()
    out = out.sort_values(by=sort_col, ascending=ascending).head(max_results)
    st.subheader("Results — Single Items")
    st.dataframe(out[["Restaurant", "Item", "Calories", "Protein", "Carbs", "Fat"]], use_container_width=True)
    if not out.empty:
        csv = out.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download results (CSV)", data=csv, file_name="macro_rules_single.csv", mime="text/csv")

else:
    # Build 2-item combos with exact rule checks on the summed macros
    combos = []

    def valid_pair(r1, r2):
        cal = r1["Calories"] + r2["Calories"]
        pro = r1["Protein"] + r2["Protein"]
        carb = r1["Carbs"] + r2["Carbs"]
        fat = r1["Fat"] + r2["Fat"]
        vals = {"Calories": cal, "Protein": pro, "Carbs": carb, "Fat": fat}
        # check constraints
        for c in constraints:
            v = vals[c["col"]]
            if c["op"] == ">=" and not (v >= c["val"]): return False
            if c["op"] == "<=" and not (v <= c["val"]): return False
            if c["op"] == ">"  and not (v >  c["val"]): return False
            if c["op"] == "<"  and not (v <  c["val"]): return False
            if c["op"] == "==" and not (v == c["val"]): return False
        return True

    base = filtered.copy()
    # modest cap per group for performance
    max_per_group = 250

    if same_restaurant:
        for rest, group in base.groupby("Restaurant"):
            g = group.head(max_per_group).reset_index(drop=True)
            for i, j in combinations(range(len(g)), 2):
                r1 = g.iloc[i]; r2 = g.iloc[j]
                if valid_pair(r1, r2):
                    combos.append({
                        "Restaurant": rest,
                        "Item 1": r1["Item"],
                        "Item 2": r2["Item"],
                        "Calories": r1["Calories"] + r2["Calories"],
                        "Protein": r1["Protein"] + r2["Protein"],
                        "Carbs": r1["Carbs"] + r2["Carbs"],
                        "Fat": r1["Fat"] + r2["Fat"],
                    })
    else:
        g = base.head(500).reset_index(drop=True)
        for i, j in combinations(range(len(g)), 2):
            r1 = g.iloc[i]; r2 = g.iloc[j]
            if valid_pair(r1, r2):
                combos.append({
                    "Restaurant": f"{r1['Restaurant']} + {r2['Restaurant']}",
                    "Item 1": f"{r1['Item']} ({r1['Restaurant']})",
                    "Item 2": f"{r2['Item']} ({r2['Restaurant']})",
                    "Calories": r1["Calories"] + r2["Calories"],
                    "Protein": r1["Protein"] + r2["Protein"],
                    "Carbs": r1["Carbs"] + r2["Carbs"],
                    "Fat": r1["Fat"] + r2["Fat"],
                })

    result_df = pd.DataFrame(combos)
    if not result_df.empty:
        result_df = result_df.sort_values(by=sort_col, ascending=ascending).head(max_results)

    st.subheader("Results — 2-Item Combos")
    st.dataframe(result_df, use_container_width=True)

    if not result_df.empty:
        csv = result_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download results (CSV)", data=csv, file_name="macro_rules_combo2.csv", mime="text/csv")

st.markdown("---")
st.markdown("**How it works**")
st.markdown("- Type a quick natural phrase (over/under/at least/at most/equal/between).")
st.markdown("- Or toggle each macronutrient in the sidebar and pick an operator with a value.")
st.markdown('- Switch to "2-Item Combo" to check the **sum** of two items against your rules.')

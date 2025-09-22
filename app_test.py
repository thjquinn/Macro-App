
import streamlit as st
import pandas as pd
import numpy as np
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
    for c in ["Calories", "Protein", "Carbs", "Fat"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Calories", "Protein", "Carbs", "Fat"])
    df["Restaurant"] = df["Restaurant"].astype(str).str.strip()
    df["Item"] = df["Item"].astype(str).str.strip()
    return df

df = load_data("fast_food_nutrition_updated.csv")

st.title("🍔 MacroFinder: Rule-Based Fast Food Finder")
st.write("Use the sidebar to set exact rules for macros.")

with st.sidebar:
    st.header("Rule Builder")
    def rule_block(label):
        st.subheader(label)
        use = st.checkbox(f"Enable {label}", value=(label in ["Protein", "Calories"]))
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

# Build constraints
constraints = []
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

if mode == "Single Item":
    out = apply_constraints_frame(filtered, constraints).copy()
    out = out.sort_values(by=sort_col, ascending=ascending).head(max_results)
    st.subheader("Results — Single Items")
    st.dataframe(out[["Restaurant", "Item", "Calories", "Protein", "Carbs", "Fat"]], use_container_width=True)
    if not out.empty:
        csv = out.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download results (CSV)", data=csv, file_name="macro_rules_single.csv", mime="text/csv")

else:
    combos = []
    def valid_pair(r1, r2):
        cal = r1["Calories"] + r2["Calories"]
        pro = r1["Protein"] + r2["Protein"]
        carb = r1["Carbs"] + r2["Carbs"]
        fat = r1["Fat"] + r2["Fat"]
        vals = {"Calories": cal, "Protein": pro, "Carbs": carb, "Fat": fat}
        for c in constraints:
            v = vals[c["col"]]
            if c["op"] == ">=" and not (v >= c["val"]): return False
            if c["op"] == "<=" and not (v <= c["val"]): return False
            if c["op"] == ">" and not (v > c["val"]): return False
            if c["op"] == "<" and not (v < c["val"]): return False
            if c["op"] == "==" and not (v == c["val"]): return False
        return True

    base = filtered.copy()
    max_per_group = 250

    if same_restaurant:
        for rest, group in base.groupby("Restaurant"):
            g = group.head(max_per_group).reset_index(drop=True)
            for i in range(len(g)):
                for j in range(i+1, len(g)):
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
        for i in range(len(g)):
            for j in range(i+1, len(g)):
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

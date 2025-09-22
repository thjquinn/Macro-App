import re
from pathlib import Path

path = Path("app_fixed.py")
text = path.read_text(encoding="utf-8", errors="ignore")

text = text.replace(
    "st.write(\"Say things like **'over 30 grams of protein and under 600 calories'** or use the sidebar to set exact rules.\")",
    "st.write(\"Use the sidebar to set exact macronutrient rules for your search.\")"
)

text = re.sub(
    r"# -----------------------------\s*\n# Helper: parse simple natural-language constraints\s*\n# -----------------------------\s*\n.*?return unique\n\n",
    "",
    text,
    count=1,
    flags=re.S,
)

text = re.sub(
    r"with st\.sidebar:\n(?:    .*\n)*?    def rule_block",
    "with st.sidebar:\n    st.header(\"Filters\")\n    st.caption(\"Use the controls below to set macronutrient rules.\")\n    st.markdown(\"---\")\n\n    def rule_block",
    text,
    count=1,
    flags=re.S,
)

text = text.replace("# Build constraints from UI and free-form text", "# Build constraints from UI controls")
text = text.replace("# From free-form parser\nconstraints += parse_freeform(free_q)\n\n", "")

text = text.replace(
    "st.markdown(\"- Type a quick natural phrase (over/under/at least/at most/equal/between).\")\n",
    "",
)

path.write_text(text, encoding="utf-8")

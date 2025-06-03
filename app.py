
import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Investiční AI v4.1", layout="wide")
st.title("Investiční analýza s doporučením – Verze 4.1")

file_report = st.file_uploader("Historie investic (.xlsx)", type=["xlsx"])
file_rizika = st.file_uploader("Rizikovost slotů (.xlsx)", type=["xlsx"])

budgets = {}
for typ in ["Hodinové", "Jednodenní", "Týdenní", "Měsíční", "Dlouhodobé"]:
    budgets[typ] = st.number_input(f"Budget pro {typ.lower()} sloty (Kč)", min_value=0, value=20000, step=1000)

if file_report and file_rizika:
    report = pd.read_excel(file_report)
    rizika = pd.read_excel(file_rizika)

    relevant_cols = ["Datum", "ID slotu", "Zdroj", "Typ slotu", "Předmět těžby", "Typ", "Vložená částka", "Zisk/Ztráta", "Souhrná částka"]
    report = report.rename(columns=lambda x: x.strip())
    rizika = rizika.rename(columns=lambda x: x.strip())
    report = report[[col for col in relevant_cols if col in report.columns]]
    report["ID slotu"] = pd.to_numeric(report["ID slotu"], errors="coerce")
    rizika["ID slotu"] = pd.to_numeric(rizika["ID slotu"], errors="coerce")

    df = pd.merge(report, rizika[["ID slotu", "Maximální ztráta (%)"]], on="ID slotu", how="left")
    df["Maximální ztráta (%)"] = df["Maximální ztráta (%)"].fillna("neuvedeno")

    vklady = df[df["Typ"] == "Vklady"].copy()
    vysledky = df[df["Typ"] != "Vklady"].copy()

    vklady["Datum"] = pd.to_datetime(vklady["Datum"], errors="coerce")
    vklady["Vložená částka"] = pd.to_numeric(vklady["Vložená částka"], errors="coerce")
    vysledky["Zisk/Ztráta"] = pd.to_numeric(vysledky["Zisk/Ztráta"], errors="coerce")

    zisky = vysledky.groupby("ID slotu")["Zisk/Ztráta"].sum()
    info = vklady.sort_values("Datum").drop_duplicates("ID slotu", keep="first")
    info = info[["Datum", "ID slotu", "Zdroj", "Typ slotu", "Předmět těžby", "Vložená částka", "Souhrná částka", "Maximální ztráta (%)"]]

    result = pd.merge(info, zisky, on="ID slotu", how="left")
    result["Souhrná částka"] = result["Vložená částka"] + result["Zisk/Ztráta"]
    result["Výnos %"] = (result["Zisk/Ztráta"] / result["Vložená částka"]) * 100

    def risk_group(x):
        try:
            x = float(x)
            if x <= 5:
                return "0–5 %"
            elif x <= 10:
                return "6–10 %"
            elif x <= 25:
                return "11–25 %"
            elif x <= 50:
                return "26–50 %"
            elif x <= 80:
                return "51–80 %"
            else:
                return "81–100 %"
        except:
            return "neuvedeno"

    result["Riziková skupina"] = result["Maximální ztráta (%)"].apply(risk_group)

    st.subheader("📊 Průměrná výnosnost podle typu slotu a rizikové skupiny")
    grouped = result[result["Riziková skupina"] != "neuvedeno"].groupby(["Typ slotu", "Riziková skupina"])["Výnos %"].mean().reset_index()
    st.dataframe(grouped, use_container_width=True)

    limit_vkladu = {
        "0–5 %": 1500,
        "6–10 %": 1200,
        "11–25 %": 1000,
        "26–50 %": 700,
        "51–80 %": 500,
        "81–100 %": 300,
    }

    result["Doporučený vklad"] = result["Riziková skupina"].map(limit_vkladu).fillna(100)

    final_result = pd.DataFrame()
    for typ in result["Typ slotu"].unique():
        df_typ = result[result["Typ slotu"] == typ].copy()
        total = df_typ["Doporučený vklad"].sum()
        if total > 0:
            df_typ["Poměr (%)"] = df_typ["Doporučený vklad"] / total
            df_typ["AI návrh vkladu (Kč)"] = df_typ["Poměr (%)"] * budgets.get(typ, 0)
        final_result = pd.concat([final_result, df_typ])

    st.subheader("🤖 AI doporučení vkladu podle typu slotu a rizika")
    st.dataframe(final_result[["Typ slotu", "ID slotu", "Předmět těžby", "Riziková skupina", "Výnos %", "Doporučený vklad", "AI návrh vkladu (Kč)"]], use_container_width=True)

    @st.cache_data
    def convert_df(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()

    st.download_button(
        label="📥 Stáhnout výstup",
        data=convert_df(final_result),
        file_name="investice_ai_doporuceni_v41.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

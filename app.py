import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(page_title="Aluminium Production Decision Model", layout="wide")
st.title("⚡ Aluminium Production — Integrated Decision Model")

# -------------------------------------------------
# Load CSV data
# -------------------------------------------------
tech_df = pd.read_csv("data/electricity_tech_data.csv")
country_df = pd.read_csv("data/country_electricity_mix.csv")
materials_df = pd.read_csv("data/materials_trade.csv")

# -------------------------------------------------
# Electricity dictionaries
# -------------------------------------------------
LCOE_KWH = dict(zip(tech_df["technology"], tech_df["lcoe_eur_per_kwh"]))
DEFAULT_CO2_KWH = dict(zip(tech_df["technology"], tech_df["co2_kg_per_kwh"]))
TECHS = list(LCOE_KWH.keys())

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.header("Scenario controls")

    countries_selected = st.multiselect(
        "Select countries",
        sorted(country_df["country"].unique()),
        default=["China", "Canada"]
    )

    carbon_tax = st.number_input("Carbon tax (€/t CO₂)", 0.0, 300.0, 60.0, 1.0)

    margin_rate = st.number_input(
        "Margin (% of operational cost)",
        0.0, 50.0, 15.0, 0.5
    ) / 100.0

    st.markdown("---")
    use_manual_mix = st.checkbox("Manual electricity mix override")

    if use_manual_mix:
        st.subheader("Manual electricity mix (%)")
        manual_mix_raw = {
            t: st.slider(t.capitalize(), 0.0, 100.0, 100.0 / len(TECHS), 1.0)
            for t in TECHS
        }

# -------------------------------------------------
# Core calculations
# -------------------------------------------------
results = []

for country in countries_selected:

    cdata = country_df[country_df["country"] == country].iloc[0]
    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    # ----- Electricity mix -----
    if use_manual_mix:
        total = sum(manual_mix_raw.values())
        if total == 0:
            st.error("Manual electricity mix cannot sum to zero.")
            st.stop()
        mix = {t: manual_mix_raw[t] / total for t in TECHS}
    else:
        mix = (
            country_df[country_df["country"] == country]
            .set_index("tech")["share"]
            .to_dict()
        )

    electricity_price = sum(mix[t] * LCOE_KWH[t] for t in TECHS)
    grid_co2_intensity = sum(mix[t] * DEFAULT_CO2_KWH[t] for t in TECHS)

    electricity_cost = E * electricity_price
    electricity_co2 = E * grid_co2_intensity

    # -------------------------------------------------
    # Materials — NEW WEIGHTED TRADE FORMULA
    # -------------------------------------------------
    mat = materials_df[materials_df["aluminium_country"] == country]

    material_cost = (
        mat["weight"] * mat["price_eur_per_t"]
    ).sum()

    # (Optional extension later: weighted CO₂ per supplier)
    material_co2 = 0.0

    # -------------------------------------------------
    # Costs
    # -------------------------------------------------
    carbon_cost = ((electricity_co2 + material_co2) / 1000) * carbon_tax

    operational_cost = electricity_cost + labour_cost + material_cost
    margin_cost = operational_cost * margin_rate
    total_cost = operational_cost + margin_cost + carbon_cost

    results.append({
        "Country": country,
        "Electricity price (€/kWh)": electricity_price,
        "Electricity CO₂ intensity (kg/kWh)": grid_co2_intensity,
        "Electricity cost (€/t)": electricity_cost,
        "Labour cost (€/t)": labour_cost,
        "Material cost (€/t)": material_cost,
        "Carbon cost (€/t)": carbon_cost,
        "Margin (€/t)": margin_cost,
        "Total cost (€/t)": total_cost,
        "CO₂ footprint (kg/t)": electricity_co2 + material_co2,
    })

df = pd.DataFrame(results)

# -------------------------------------------------
# Visuals
# -------------------------------------------------
PALETTE = pc.qualitative.Alphabet
country_colors = {
    c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)
}

# -------------------------------------------------
# Table
# -------------------------------------------------
st.subheader("Integrated country cost summary")
st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# Plot 1 — Electricity sensitivity
# -------------------------------------------------
st.markdown("---")
st.subheader("Electricity cost + carbon cost vs electricity price")

price_range = np.linspace(0.03, 0.20, 200)
fig_el = go.Figure()

for _, r in df.iterrows():
    E = country_df[country_df["country"] == r["Country"]]["energy_kwh_per_t"].iloc[0]
    curve = E * price_range + r["Carbon cost (€/t)"]

    fig_el.add_trace(go.Scatter(
        x=price_range,
        y=curve,
        mode="lines",
        name=r["Country"],
        line=dict(color=country_colors[r["Country"]], width=2)
    ))

fig_el.update_layout(
    xaxis_title="Electricity price (€/kWh)",
    yaxis_title="Electricity + carbon cost (€/t)",
    hovermode="x unified"
)

st.plotly_chart(fig_el, use_container_width=True)

# -------------------------------------------------
# Plot 2 — Electricity price vs CO₂
# -------------------------------------------------
st.markdown("---")
st.subheader("Electricity price vs CO₂ footprint")

fig_co2 = px.scatter(
    df,
    x="CO₂ footprint (kg/t)",
    y="Electricity price (€/kWh)",
    text="Country"
)

fig_co2.update_traces(textposition="top center")
st.plotly_chart(fig_co2, use_container_width=True)

# -------------------------------------------------
# Plot 3 — Cost structure
# -------------------------------------------------
st.markdown("---")
st.subheader("Cost structure by country")

cost_cols = [
    "Electricity cost (€/t)",
    "Labour cost (€/t)",
    "Material cost (€/t)",
    "Margin (€/t)",
    "Carbon cost (€/t)",
]

fig_stack = go.Figure()
for col in cost_cols:
    fig_stack.add_trace(go.Bar(x=df["Country"], y=df[col], name=col))

fig_stack.update_layout(
    barmode="stack",
    yaxis_title="€/t Aluminium",
    xaxis_title="Country"
)

st.plotly_chart(fig_stack, use_container_width=True)



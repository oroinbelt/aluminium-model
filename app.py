import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Aluminium Production Decision Model",
    layout="wide"
)
st.title("⚡ Aluminium Production — Integrated Decision Model")

# -------------------------------------------------
# Load CSV data
# -------------------------------------------------
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")
materials_df = pd.read_csv("data/materials_trade.csv")

# Define energy sources and factors for dynamic calculations
sources = ["coal", "gas", "other fossil", "nuclear", "bioenergy", "hydro", "solar", "wind", "other renewables"]

co2_factors = {
    "coal": 0.82,  # kg CO2/kWh (lifecycle average)
    "gas": 0.49,
    "other fossil": 0.74,
    "nuclear": 0.012,
    "bioenergy": 0.23,
    "hydro": 0.004,
    "solar": 0.041,
    "wind": 0.011,
    "other renewables": 0.038
}

price_factors = {
    "coal": 0.074,  # EUR/kWh (approximate LCOE global average)
    "gas": 0.046,
    "other fossil": 0.064,
    "nuclear": 0.129,
    "bioenergy": 0.055,
    "hydro": 0.046,
    "solar": 0.040,
    "wind": 0.031,
    "other renewables": 0.037
}

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

    carbon_tax = st.number_input(
        "Carbon tax (€/t CO₂)",
        min_value=0.0,
        max_value=300.0,
        value=60.0,
        step=1.0
    )

    margin_rate = st.number_input(
        "Margin (% of operational cost)",
        min_value=0.0,
        max_value=50.0,
        value=15.0,
        step=0.5
    ) / 100.0

    st.header("Grid Mix Scenarios")
    country_mixes = {}
    for country in countries_selected:
        cdata = country_df[country_df["country"] == country].iloc[0]
        with st.expander(f"{country} Grid Mix"):
            mix = {}
            for source in sources:
                mix[source] = st.slider(
                    source.capitalize(),
                    min_value=0.0,
                    max_value=1.0,
                    value=float(cdata[source]),
                    step=0.01,
                    key=f"{country}_{source}"
                )
            total = sum(mix.values())
            if total > 0:
                for source in sources:
                    mix[source] /= total
            else:
                # Fallback to original if sum is zero (unlikely)
                for source in sources:
                    mix[source] = float(cdata[source])
            country_mixes[country] = mix

# -------------------------------------------------
# Core calculations
# -------------------------------------------------
results = []

for country in countries_selected:

    # --- Country-level data ---
    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]

    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    # Use adjusted mix for electricity price and CO2 intensity
    mix = country_mixes[country]
    electricity_price = sum(mix[source] * price_factors[source] for source in sources)
    grid_co2_intensity = sum(mix[source] * co2_factors[source] for source in sources)

    # --- Electricity ---
    electricity_cost = E * electricity_price
    electricity_co2 = E * grid_co2_intensity

    # --- Materials (weighted trade) ---
    mat = materials_df[materials_df["aluminium_country"] == country]
    material_cost = (mat["weight"] * mat["price_eur_per_t"]).sum()
    material_co2 = 0.0  # placeholder (can be extended later)

    # --- Costs ---
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
# Visual styling
# -------------------------------------------------
PALETTE = pc.qualitative.Alphabet
country_colors = {
    c: PALETTE[i % len(PALETTE)]
    for i, c in enumerate(countries_selected)
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
    E = country_df[
        country_df["country"] == r["Country"]
    ]["energy_kwh_per_t"].iloc[0]

    curve = E * price_range + r["Carbon cost (€/t)"]

    fig_el.add_trace(go.Scatter(
        x=price_range,
        y=curve,
        mode="lines",
        name=r["Country"],
        line=dict(
            color=country_colors[r["Country"]],
            width=2
        )
    ))

fig_el.update_layout(
    xaxis_title="Electricity price (€/kWh)",
    yaxis_title="Electricity + carbon cost (€/t)",
    hovermode="x unified"
)

st.plotly_chart(fig_el, use_container_width=True)

# -------------------------------------------------
# Plot 2 — Electricity price vs CO₂ footprint
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
    fig_stack.add_trace(go.Bar(
        x=df["Country"],
        y=df[col],
        name=col
    ))

fig_stack.update_layout(
    barmode="stack",
    yaxis_title="€/t Aluminium",
    xaxis_title="Country"
)

st.plotly_chart(fig_stack, use_container_width=True)

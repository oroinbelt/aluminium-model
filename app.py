import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc

# =================================================
# Page configuration
# =================================================
st.set_page_config(
    page_title="Aluminium Production Decision Support Tool",
    layout="wide"
)

st.title("⚡ Aluminium Production — Decision Support Tool")
st.caption(
    "Decision-support model evaluating cost and carbon trade-offs "
    "in primary aluminium production under alternative electricity scenarios."
)

# =================================================
# Data loading (UNCHANGED)
# =================================================
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")
materials_df = pd.read_csv("data/materials_trade.csv")

sources = [
    "coal", "gas", "other fossil", "nuclear", "bioenergy",
    "hydro", "solar", "wind", "other renewables"
]

# Technology-specific parameters (manual mode only)
co2_factors = {
    "coal": 0.9,
    "gas": 0.45,
    "other fossil": 0.7,
    "nuclear": 0.01,
    "bioenergy": 0.23,
    "hydro": 0.004,
    "solar": 0.035,
    "wind": 0.015,
    "other renewables": 0.038,
}

price_factors = {
    "coal": 0.09,
    "gas": 0.10,
    "other fossil": 0.064,
    "nuclear": 0.12,
    "bioenergy": 0.055,
    "hydro": 0.046,
    "solar": 0.05,
    "wind": 0.10,
    "other renewables": 0.037,
}

# =================================================
# Sidebar
# =================================================
with st.sidebar:
    st.header("Select Countries")

    countries_selected = st.multiselect(
        "Countries included in comparison",
        sorted(country_df["country"].unique()),
        default=["China", "Canada"],
    )

    st.markdown("---")
    carbon_tax = st.number_input(
        "Carbon price (€/t CO₂)",
        0.0, 300.0, 60.0, 5.0
    )

    margin_rate = st.number_input(
        "Producer margin (% of operational cost)",
        0.0, 50.0, 15.0, 1.0
    ) / 100

    st.markdown("---")
    model_mode = st.radio(
        "Electricity system representation",
        ["Automated (country averages)", "Manual (scenario grid)"],
        index=0,
    )

    manual_mode = model_mode == "Manual (scenario grid)"

# =================================================
# Grid mixes (manual mode only)
# =================================================
country_mixes_manual = {}

for country in countries_selected:
    row = country_df[country_df["country"] == country].iloc[0]
    country_mixes_manual[country] = {s: float(row[s]) for s in sources}

# =================================================
# Core model calculations
# =================================================
results = []

for country in countries_selected:
    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]

    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    # -------------------------------
    # AUTOMATED MODE (NO GRID MIX)
    # -------------------------------
    if not manual_mode:
        electricity_price = edata["avg_electricity_price_eur_per_kwh"]
        grid_co2_intensity = edata["avg_co2_kg_per_kwh"]

    # -------------------------------
    # MANUAL MODE (GRID RECONSTRUCTION)
    # -------------------------------
    else:
        mix = country_mixes_manual[country]
        electricity_price = sum(mix[s] * price_factors[s] for s in sources)
        grid_co2_intensity = sum(mix[s] * co2_factors[s] for s in sources)

    electricity_cost = E * electricity_price
    electricity_co2 = E * grid_co2_intensity

    mat = materials_df[materials_df["aluminium_country"] == country]
    material_cost = (mat["weight"] * mat["price_eur_per_t"]).sum()
    material_co2 = 0.0

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

# =================================================
# Visuals
# =================================================
PALETTE = pc.qualitative.Alphabet
country_colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)}

tab_scenario, tab_grid, tab_costs = st.tabs(
    ["⚙️ Scenario outcomes", "⚡ Electricity system", "💰 Cost structure"]
)

# =================================================
# TAB — Scenario outcomes
# =================================================
with tab_scenario:
    fig = px.scatter(
        df,
        x="CO₂ footprint (kg/t)",
        y="Total cost (€/t)",
        color="Country",
        text="Country",
        color_discrete_map=country_colors,
    )
    fig.update_traces(textposition="top center")
    st.plotly_chart(fig, use_container_width=True)

# =================================================
# TAB — Electricity system
# =================================================
with tab_grid:
    country = st.selectbox("Select country", countries_selected)

    if manual_mode:
        st.subheader("Manual grid definition")
        new_mix = {}
        for s in sources:
            new_mix[s] = st.slider(
                s.capitalize(),
                0.0, 1.0,
                country_mixes_manual[country][s],
                0.01,
                key=f"{country}_{s}"
            )

        total = sum(new_mix.values())

        if abs(total - 1.0) > 1e-6:
            st.error(f"⚠️ Grid not normalized (sum = {total:.3f})")
        else:
            country_mixes_manual[country] = new_mix
            st.success("Grid normalized ✔")

            st.info(
                f"Electricity price: "
                f"{sum(new_mix[s]*price_factors[s] for s in sources):.3f} €/kWh\n\n"
                f"CO₂ intensity: "
                f"{sum(new_mix[s]*co2_factors[s] for s in sources):.3f} kg/kWh"
            )
    else:
        st.info("Automated mode uses country-average electricity data.")

# =================================================
# TAB — Cost structure
# =================================================
with tab_costs:
    cost_cols = [
        "Electricity cost (€/t)",
        "Labour cost (€/t)",
        "Material cost (€/t)",
        "Margin (€/t)",
        "Carbon cost (€/t)",
    ]

    fig = go.Figure()
    for col in cost_cols:
        fig.add_bar(x=df["Country"], y=df[col], name=col)

    fig.update_layout(barmode="stack", yaxis_title="€/t aluminium")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(df.round(2), use_container_width=True)

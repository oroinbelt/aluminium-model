import streamlit as st
import pandas as pd
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
    "in primary aluminium production using country-average electricity data."
)

# =================================================
# Data loading
# =================================================
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")
materials_df = pd.read_csv("data/materials_trade.csv")

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
        min_value=0.0,
        max_value=300.0,
        value=60.0,
        step=5.0,
    )

    margin_rate = st.number_input(
        "Producer margin (% of operational cost)",
        min_value=0.0,
        max_value=50.0,
        value=15.0,
        step=1.0,
    ) / 100.0

# =================================================
# Core model calculations (AUTOMATED MODE ONLY)
# =================================================
results = []

for country in countries_selected:
    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]

    # Country-level parameters
    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    electricity_price = edata["avg_electricity_price_eur_per_kwh"]
    grid_co2_intensity = edata["avg_co2_kg_per_kwh"]

    # Electricity cost and emissions
    electricity_cost = E * electricity_price
    electricity_co2 = E * grid_co2_intensity

    # Material cost
    mat = materials_df[materials_df["aluminium_country"] == country]
    material_cost = (mat["weight"] * mat["price_eur_per_t"]).sum()
    material_co2 = 0.0

    # Carbon cost
    carbon_cost = ((electricity_co2 + material_co2) / 1000) * carbon_tax

    # Total cost
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
# Visual styling
# =================================================
PALETTE = pc.qualitative.Alphabet
country_colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)}

# =================================================
# Layout — tabs
# =================================================
tab_scenario, tab_costs = st.tabs(
    ["⚙️ Scenario outcomes", "💰 Cost structure"]
)

# =================================================
# TAB — Scenario outcomes
# =================================================
with tab_scenario:
    st.subheader("Scenario outcomes")

    # -------------------------------------------------
    # Plot 1: Electricity price vs electricity CO2 footprint
    # -------------------------------------------------
    fig1 = px.scatter(
        df,
        x="Electricity CO₂ intensity (kg/kWh)",
        y="Electricity price (€/kWh)",
        color="Country",
        text="Country",
        color_discrete_map=country_colors,
        title="Electricity price vs electricity CO₂ intensity",
    )
    fig1.update_traces(textposition="top center")
    fig1.update_layout(
        xaxis_title="Electricity CO₂ intensity (kg CO₂ / kWh)",
        yaxis_title="Electricity price (€/kWh)",    
    )
    st.plotly_chart(fig1, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------
    # Plot 2: Total cost vs electricity price
    # -------------------------------------------------
    fig2 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Total cost (€/t)",
        color="Country",
        text="Country",
        color_discrete_map=country_colors,
        title="Total production cost vs electricity price",
    )
    fig2.update_traces(textposition="top center")
    fig2.update_layout(
        xaxis_title="Electricity price (€/kWh)",
        yaxis_title="Total cost (€/t aluminium)",
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------
    # Plot 3: Total cost vs CO2 footprint
    # -------------------------------------------------
    fig3 = px.scatter(
        df,
        x="CO₂ footprint (kg/t)",
        y="Total cost (€/t)",
        color="Country",
        text="Country",
        color_discrete_map=country_colors,
        title="Total production cost vs CO₂ footprint",
    )
    fig3.update_traces(textposition="top center")
    fig3.update_layout(
        xaxis_title="CO₂ footprint (kg CO₂ / t aluminium)",
        yaxis_title="Total cost (€/t aluminium)",
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")

    # -------------------------------------------------
    # Plot 4: Electricity cost vs electricity price
    # -------------------------------------------------
    fig4 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Electricity cost (€/t)",
        color="Country",
        text="Country",
        color_discrete_map=country_colors,
        title="Electricity cost vs electricity price",
    )
    fig4.update_traces(textposition="top center")
    fig4.update_layout(
        xaxis_title="Electricity price (€/kWh)",
        yaxis_title="Electricity cost (€/t aluminium)",
    )
    st.plotly_chart(fig4, use_container_width=True)

# =================================================
# TAB — Cost structure
# =================================================
with tab_costs:
    st.subheader("Cost composition by country")

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

    fig.update_layout(
        barmode="stack",
        yaxis_title="€/t aluminium",
        xaxis_title="Country",
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.round(2), use_container_width=True)




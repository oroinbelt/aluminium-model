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
# Sidebar (global parameters only)
# =================================================
with st.sidebar:
    st.header("Global parameters")

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
# Countries — AUTOMATIC (ALL)
# =================================================
countries_selected = sorted(country_df["country"].unique())

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
country_colors = {
    c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)
}

# =================================================
# Layout — tabs
# =================================================
tab_map, tab_scenario, tab_costs = st.tabs(
    ["🌍 Global map", "⚙️ Scenario outcomes", "💰 Cost structure"]
)

# =================================================
# TAB — Global map
# =================================================
with tab_map:
    st.subheader("Global overview of aluminium production metrics")

    fig_map = px.choropleth(
        df,
        locations="Country",
        locationmode="country names",
        color="Total cost (€/t)",
        color_continuous_scale="Viridis",
        range_color=(df["Total cost (€/t)"].min(), df["Total cost (€/t)"].max()),
        hover_name="Country",
        hover_data={
            "Total cost (€/t)": ":.1f",
            "Electricity price (€/kWh)": ":.3f",
            "CO₂ footprint (kg/t)": ":.0f",
        },
        title="Total aluminium production cost by country",
    )

    fig_map.update_geos(
        showcountries=True,
        countrycolor="lightgray",
        showcoastlines=False,
        showframe=False,
        projection_type="natural earth",
    )

    fig_map.update_layout(
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="€/t aluminium"),
    )

    st.plotly_chart(fig_map, use_container_width=True)

# =================================================
# TAB — Scenario outcomes
# =================================================
with tab_scenario:
    st.subheader("Scenario outcomes")

    fig1 = px.scatter(
        df,
        x="Electricity CO₂ intensity (kg/kWh)",
        y="Electricity price (€/kWh)",
        color="Country",
        title="Electricity price vs electricity CO₂ intensity",
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Total cost (€/t)",
        color="Country",
        title="Total production cost vs electricity price",
    )
    st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.scatter(
        df,
        x="CO₂ footprint (kg/t)",
        y="Total cost (€/t)",
        color="Country",
        title="Total production cost vs CO₂ footprint",
    )
    st.plotly_chart(fig3, use_container_width=True)

    fig4 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Electricity cost (€/t)",
        color="Country",
        title="Electricity cost vs electricity price",
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

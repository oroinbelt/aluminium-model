


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
# DATA LOADING
# =================================================
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")
alumina_df = pd.read_csv("data/alumina_costs.csv")
petcoke_df = pd.read_csv("data/calc_petcoke_costs.csv")

# Flow + electricity CSV (used in notebook)
flows_df = pd.read_csv("data/total_co2_tot_Al.csv")

# Clean country names
for df in [country_df, electricity_df, alumina_df, petcoke_df, flows_df]:
    for col in df.columns:
        if "country" in col.lower():
            df[col] = df[col].astype(str).str.strip()

# =================================================
# SIDEBAR
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
# FULL ALUMINIUM + TOTAL CO₂ MODEL
# (Notebook logic embedded)
# =================================================
flows_df = flows_df.dropna(how="all").fillna(0)

for col in flows_df.columns:
    if flows_df[col].dtype == object:
        try:
            flows_df[col] = flows_df[col].str.replace(",", "").astype(float)
        except:
            pass

records = []

for country in flows_df["Bauxite_destination_m"].unique():

    imports = flows_df[flows_df["Bauxite_destination_m"] == country]["Bauxite_tonnes_m"].sum() / 1e6
    exports = flows_df[flows_df["Bauxite_destination_x"] == country]["Bauxite_tonnes_x"].sum() / 1e6
    domestic = flows_df[flows_df["Bauxite_local_country"] == country]["Bauxite_local_tonnes"].sum() / 1e6

    total_bauxite = imports + domestic - exports
    if total_bauxite <= 0:
        continue

    alumina_imports = flows_df[flows_df["Alumina_destination_m"] == country]["Alumina_tonnes_m"].sum() / 1e6
    alumina_exports = flows_df[flows_df["Alumina_destination_x"] == country]["Alumina_tonnes_x"].sum() / 1e6
    net_alumina = alumina_imports - alumina_exports

    bauxite_grade = 0.5
    total_alumina = total_bauxite * bauxite_grade + net_alumina

    stoich = 0.529
    efficiency = 0.95
    total_aluminium = total_alumina / stoich * efficiency  # Mt Al

    # CO₂ components
    anode_consumption = 400
    anode_co2 = 3.67
    bauxite_mining_co2 = 5
    bayer_co2 = 150

    scope1_anode = total_aluminium * anode_consumption * anode_co2 / 1e6
    scope1_bauxite = total_bauxite * bauxite_mining_co2
    scope1_bayer = total_alumina * bayer_co2

    energy = flows_df[flows_df["country2"] == country]["energy_kwh_per_t"].mean()
    grid_co2 = flows_df[flows_df["country1"] == country]["avg_co2_kg_per_kwh"].mean()

    if pd.isna(energy) or pd.isna(grid_co2):
        continue

    scope2 = total_aluminium * energy * grid_co2 / 1000
    total_co2 = scope1_anode + scope1_bauxite + scope1_bayer + scope2

    records.append({
        "Country": country,
        "Total aluminium (t)": total_aluminium * 1e6,
        "Total CO₂ (t)": total_co2 * 1e6,
    })

total_co2_df = pd.DataFrame(records)

# =================================================
# CORE STREAMLIT MODEL (COST + POLICY)
# =================================================
countries_selected = sorted(country_df["country"].unique())
results = []

for country in countries_selected:

    if (
        country not in electricity_df["country"].values
        or country not in alumina_df["country"].values
        or country not in petcoke_df["country"].values
        or country not in total_co2_df["Country"].values
    ):
        continue

    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]
    tdata = total_co2_df[total_co2_df["Country"] == country].iloc[0]

    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]
    electricity_price = edata["avg_electricity_price_eur_per_kwh"]
    grid_co2_intensity = edata["avg_co2_kg_per_kwh"]

    electricity_cost = E * electricity_price
    electricity_co2 = E * grid_co2_intensity

    alumina_row = alumina_df[alumina_df["country"] == country].iloc[0]
    petcoke_row = petcoke_df[petcoke_df["country"] == country].iloc[0]

    material_cost = (
        alumina_row["alumina_market_price_eur_per_t"]
        + alumina_row["alumina_transport_cost_eur_per_t"]
        + petcoke_row["petcoke_market_price_eur_per_t"]
        + petcoke_row["petcoke_transport_cost_eur_per_t"]
    )

    total_co2_kg_per_t = (tdata["Total CO₂ (t)"] / tdata["Total aluminium (t)"]) * 1000
    non_electricity_co2 = total_co2_kg_per_t - electricity_co2

    carbon_cost = (total_co2_kg_per_t / 1000) * carbon_tax

    operational_cost = electricity_cost + labour_cost + material_cost
    margin_cost = operational_cost * margin_rate
    total_cost = operational_cost + margin_cost + carbon_cost

    results.append({
        "Country": country,
        "Electricity cost (€/t)": electricity_cost,
        "Labour cost (€/t)": labour_cost,
        "Material cost (€/t)": material_cost,
        "Carbon cost (€/t)": carbon_cost,
        "Margin (€/t)": margin_cost,
        "Total cost (€/t)": total_cost,
        "Electricity price (€/kwh)": electricity_price,
        "Electricity CO₂ (kg/t)": electricity_co2,
        "Non-electricity CO₂ (kg/t)": non_electricity_co2,
        "Total CO₂ (kg/t)": total_co2_kg_per_t,
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
            "Electricity CO₂ (kg/t)": ":.3f",
            "Non-electricity CO₂ (kg/t)": ":.0f",
            "Total CO₂ (kg/t)": ":.0f",
        },
        title="Total aluminium production cost by country",
    )
    fig_map.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
    )
    fig_map.update_geos(
        bgcolor="#0e1117",
        showcountries=True,
        countrycolor="#2a2f3a",   # subtle country borders
        showcoastlines=True,
        coastlinecolor="#3a3f4b",  # soft coastlines
        coastlinewidth=0.6,
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
        x="Total CO₂ (kg/t)",
        y="Total cost (€/t)",
        size="Total cost (€/t)",
        color="Country",
        hover_name="Country",
        hover_data={
            "Electricity CO₂ (kg/t)": ":.0f",
            "Non-electricity CO₂ (kg/t)": ":.0f",
            "Total CO₂ (kg/t)": ":.0f",

        },
        title="Total aluminium cost vs total CO₂ footprint",
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












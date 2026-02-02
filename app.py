import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc

# =================================================
# Page configuration
# =================================================
st.set_page_config(
    page_title="Aluminium Production Cost Model",
    layout="wide"
)


st.markdown(
    """
    <style>
      /* Keep Streamlit header controls (Deploy + menu) but make header transparent */
      header[data-testid="stHeader"]{
        background: rgba(0,0,0,0);
      }
      header[data-testid="stHeader"]::after{
        box-shadow: none;
      }

      /* Fixed custom top bar */
      .custom-topbar{
        position: fixed;
        top: 0.25rem;
        right: 14rem;
        left: 28rem;
        height: 3.2rem;
        display: flex;
        align-items: center;
        padding: 0 1.25rem;

        background: #0e1117;
        border: 1px solid #2a2f3a;
        border-radius: 14px;

        z-index: 998;
      }

      /* When sidebar is collapsed, bar shifts left */
      section[data-testid="stSidebar"][aria-expanded="false"] ~ div .custom-topbar{
        left: 19rem;
      }

      .custom-topbar .title{
        color: white;
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1;
        margin: 0;
      }

      /* Sticky TAB TITLES ONLY (the "Global map / Scenario outcomes / Cost structure" row) */
      div[role="tablist"]{
        position: fixed;
        top: 3.5rem;
        left: 33.5rem;
        right: 17rem;
        z-index: 997;

        background: #0e1117;
        border-bottom: 1px solid #2a2f3a;
        padding: 0.25rem 0.75rem;
      }

      section[data-testid="stSidebar"][aria-expanded="false"] ~ div div[role="tablist"]{
        left: 20rem;
      }

      /* ---- FULL-WIDTH OPAQUE MASKS (prevents content showing at the sides/corners) ---- */
      .custom-topbar::before{
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 4.0rem;          /* covers the whole topbar region */
        background: #0e1117;
        z-index: -1;
      }

      div[role="tablist"]::before{
        content: "";
        position: fixed;
        top: 3.5rem;             /* starts right after the topbar mask */
        left: 0;
        right: 0;
        height: 3.4rem;          /* covers the whole tabs region */
        background: #0e1117;
        z-index: -1;
      }

      /* Push main content below fixed topbar + fixed tabs */
      .block-container{
        padding-top: 8.2rem;
      }
    </style>

    <div class="custom-topbar">
      <div class="title">⚡ Aluminium Production — Cost Model</div>
    </div>
    """,
    unsafe_allow_html=True
)




# =================================================
# Data loading
# =================================================
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")

# NEW material cost files
alumina_df = pd.read_csv("data/alumina_costs.csv")
petcoke_df = pd.read_csv("data/calc_petcoke_costs.csv")

# Sustainability / trade-based CO2 dataset (the one you just uploaded)
sustainability_df = pd.read_csv("data/total_co2_tot_Al.csv")

# Drop empty rows (same as notebook)
sustainability_df = sustainability_df.dropna(how="all")

# Clean numeric columns exactly like your notebook logic (remove commas, coerce, fill 0)
for col in [
    "Bauxite_tonnes_m", "Bauxite_tonnes_x", "Bauxite_local_tonnes",
    "Alumina_tonnes_m", "Alumina_tonnes_x"
]:
    if col in sustainability_df.columns:
        sustainability_df[col] = (
            sustainability_df[col]
            .astype(str)
            .str.replace(",", "", regex=True)
        )
        sustainability_df[col] = pd.to_numeric(sustainability_df[col], errors="coerce").fillna(0)

# Clean country-name fields in sustainability_df (prevents mismatch due to trailing spaces)
country_cols = [
    "Bauxite_destination_m",
    "Bauxite_destination_x",
    "Bauxite_local_country",
    "Alumina_destination_m",
    "Alumina_destination_x",
    "country1",
    "country2",
]
for col in country_cols:
    if col in sustainability_df.columns:
        sustainability_df[col] = sustainability_df[col].astype(str).str.strip()

# Clean country names
for df in [country_df, electricity_df, alumina_df, petcoke_df]:
    df["country"] = df["country"].str.strip()

# =================================================
# Sidebar (global parameters only)
# =================================================
with st.sidebar:
    st.header("Global parameters")

    carbon_tax = st.number_input(
        "Carbon Tax (€/t CO₂)",
        min_value=0.0,
        max_value=500.0,
        value=60.0,
        step=5.0,
    )

    margin_rate = st.number_input(
        "Producer Margin (% of operational cost)",
        min_value=0.0,
        max_value=50.0,
        value=15.0,
        step=1.0,
    ) / 100.0
    current_efficiency = st.number_input(
        "Current Efficiency",
        min_value=0.20,
        max_value=1.00,
        value=0.90,
        step=0.01,
    )

    bauxite_footprint = st.number_input(
        "Bauxite footprint (tCO₂ / t bauxite)",
        min_value=0.0,
        max_value=0.40,
        value=0.035,
        step=0.001,
        format="%.3f",
    )

    voltage_cell = st.number_input(
        "Cell Voltage (V)",
        min_value=0.0,
        max_value=10.0,
        value=4.64,
        step=0.01,
    )


# =================================================
# Countries — AUTOMATIC (ALL)
# =================================================
countries_selected = sorted(country_df["country"].unique())

##################################################################################################
def compute_total_co2_intensity_from_trade(
    df,
    country_name,
    current_efficiency=0.9,
    bauxite_footprint=0.035,
    voltage_cell=4.64,
):

    # ---- EXACT CONSTANTS FROM YOUR CODE ----
    bauxite_grade = 0.5  # fraction of alumina from local bauxite
    #current_efficiency = 0.9  # CE

    stochiometric_al = 1.889  # tAl2O3/t Al
    stochiometric_c = 0.333   # tC/ t Al
    stochiometric_co2 = 1.222 # tCO2 / tAl

    #bauxite_footprint = 0.035 # tCO2/t bauxite

    fuel_oil_alumina = 0.093      # kg fuel oil / kg alumina
    fuel_oil_co2 = 3.52           # kg CO2 / kg fuel oil
    natural_gas_alumina = 0.17    # kg natural gas / kg alumina
    natural_gas_co2 = 1.98        # kg CO2 / kg natural gas
    energy_alumina = 0.109        # kWh/ kg alumina

    #voltage_cell = 4.64  # V
    anode_footprint = 1.5 # t CO2 / t Al

    # ---- EXACT LOGIC FROM YOUR CODE (just organized) ----
    def total_bauxite_for_country(country_name):
        imports = df.loc[df['Bauxite_destination_m'] == country_name, 'Bauxite_tonnes_m'].sum() / 1000  # kg → t
        exports = df.loc[df['Bauxite_destination_x'] == country_name, 'Bauxite_tonnes_x'].sum() / 1000  # kg → t
        domestic = df.loc[df['Bauxite_local_country'] == country_name, 'Bauxite_local_tonnes'].sum() * 1000  # 1000 t → t
        total = imports + domestic - exports
        return total / 1e6  # tonnes (Mtonnes-style scaling as in code)

    def total_alumina_for_country(country_name):
        imports = df.loc[df['Alumina_destination_m'] == country_name, 'Alumina_tonnes_m'].sum() / 1000  # kg → t
        exports = df.loc[df['Alumina_destination_x'] == country_name, 'Alumina_tonnes_x'].sum() / 1000  # kg → t
        total = imports - exports
        return total / 1e6  # tonnes

    def electricity_footprint_per_country(country_name):
        electricity_footprint = df.loc[df['country1'] == country_name, 'avg_co2_kg_per_kwh'].sum()
        return electricity_footprint

    def energy_intensity_per_country(country_name):
        energy_intensity = df.loc[df['country2'] == country_name, 'energy_kwh_per_t'].sum() / 1000
        return energy_intensity

    total_bauxite = total_bauxite_for_country(country_name)
    total_alumina = total_bauxite * bauxite_grade + total_alumina_for_country(country_name)

    total_al = total_alumina / stochiometric_al * current_efficiency
    total_c = total_al * stochiometric_c / current_efficiency
    total_reaction_co2 = total_al * stochiometric_co2 / current_efficiency

    bauxite_co2 = bauxite_footprint * total_bauxite

    energy_co2 = electricity_footprint_per_country(country_name)  # kg CO2 / kWh

    alumina_co2 = (
        (fuel_oil_alumina * fuel_oil_co2 + natural_gas_alumina * natural_gas_co2 + energy_alumina * energy_co2)
        * total_alumina
    )

    energy_hh_mode_1 = 2.9806 * voltage_cell / current_efficiency # MWh / t Al
    energy_hh_mode_2 = energy_intensity_per_country(country_name) # MWh / t Al

    total_energy_co2_mode_1 = energy_co2 * energy_hh_mode_1 * total_al
    total_energy_co2_mode_2 = energy_co2 * energy_hh_mode_2 * total_al

    anode_co2 = anode_footprint * total_al

    total_co2_mode_1 = total_reaction_co2 + bauxite_co2 + alumina_co2 + total_energy_co2_mode_1 + anode_co2
    total_co2_mode_2 = total_reaction_co2 + bauxite_co2 + alumina_co2 + total_energy_co2_mode_2 + anode_co2

    functional_unit_mode_1 = total_co2_mode_1 / total_al
    functional_unit_mode_2 = total_co2_mode_2 / total_al

    functional_unit_avg = (functional_unit_mode_1 + functional_unit_mode_2) / 2
    # --- component intensities (tCO2/t Al) ---
    # Electricity is computed in two modes; keep both + average
    elec_intensity_mode_1 = total_energy_co2_mode_1 / total_al
    elec_intensity_mode_2 = total_energy_co2_mode_2 / total_al
    elec_intensity_avg = (elec_intensity_mode_1 + elec_intensity_mode_2) / 2

    reaction_intensity = total_reaction_co2 / total_al
    bauxite_intensity = bauxite_co2 / total_al
    anode_intensity = anode_co2 / total_al

    return {
        "Functional_unit": functional_unit_avg,  # as in code
        "functional_unit_mode_1": functional_unit_mode_1,
        "functional_unit_mode_2": functional_unit_mode_2,
        "total_al": total_al,
        "total_alumina": total_alumina,
        "total_bauxite": total_bauxite,

        # NEW: breakdown (tCO2/t Al)
        "elec_tco2_per_tal": elec_intensity_avg,
        "bauxite_tco2_per_tal": bauxite_intensity,
        "anode_tco2_per_tal": anode_intensity,
        "reaction_tco2_per_tal": reaction_intensity,
    }

# =================================================
# Core model calculations (AUTOMATED MODE ONLY)
# =================================================
results = []

for country in countries_selected:

    # Skip countries missing required datasets
    if (
        country not in electricity_df["country"].values
        or country not in alumina_df["country"].values
        or country not in petcoke_df["country"].values
    ):
        continue

    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]

    # Country-level parameters
    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    electricity_price = edata["avg_electricity_price_eur_per_kwh"]
    grid_co2_intensity = edata["avg_co2_kg_per_kwh"]

    # Electricity cost and emissions (electricity-only breakdown)
    electricity_cost = E * electricity_price
    electricity_co2 = (E * grid_co2_intensity)/1000 # t CO2 / t Al

    ############################################################################################################
    # Total CO2 intensity from the sustainability dataset (trade-based) -> already INCLUDES electricity
    co2_info = compute_total_co2_intensity_from_trade(
        sustainability_df,
        country,
        current_efficiency=current_efficiency,
        bauxite_footprint=bauxite_footprint,
        voltage_cell=voltage_cell,
    )

    if (
        co2_info is None
        or co2_info.get("Functional_unit") is None
        or pd.isna(co2_info.get("Functional_unit"))
        or co2_info.get("total_al", 0) == 0
    ):
        continue

    # TOTAL footprint from sustainability model (tCO2/tAl)
    total_co2 = co2_info["Functional_unit"] 
    ##############################################################################################################
    elec_co2_int = co2_info["elec_tco2_per_tal"]
    bauxite_co2_int = co2_info["bauxite_tco2_per_tal"]
    anode_co2_int = co2_info["anode_tco2_per_tal"]
    reaction_co2_int = co2_info["reaction_tco2_per_tal"]

    # =================================================
    # NEW MATERIAL COST LOGIC
    # =================================================
    alumina_row = alumina_df[alumina_df["country"] == country].iloc[0]
    petcoke_row = petcoke_df[petcoke_df["country"] == country].iloc[0]

    alumina_cost = (
        alumina_row["alumina_market_price_eur_per_t"]
        + alumina_row["alumina_transport_cost_eur_per_t"]
    )

    petcoke_cost = (
        petcoke_row["petcoke_market_price_eur_per_t"]
        + petcoke_row["petcoke_transport_cost_eur_per_t"]
    )

    material_cost = ((alumina_cost*1.889) + (petcoke_cost*0.333))/current_efficiency

    # Carbon cost (use TOTAL CO2 only; no double counting)
    carbon_cost = total_co2 * carbon_tax

    # Total cost
    operational_cost = electricity_cost + labour_cost + material_cost
    margin_cost = operational_cost * margin_rate
    total_cost = operational_cost + margin_cost + carbon_cost

    results.append({
        "Country": country,
        "Electricity price (€/kWh)": electricity_price,
        "Electricity CO₂ footprint (kgCO₂/kWh)": grid_co2_intensity,
        "Electricity cost (€/t)": electricity_cost,
        "Labour cost (€/t)": labour_cost,
        "Material cost (€/t)": material_cost,
        "Carbon cost (€/t)": carbon_cost,
        "Margin (€/t)": margin_cost,
        "Total cost (€/t)": total_cost,

        # Store TOTAL footprint (kg/t Al)
        "Total CO₂ footprint  (tCO₂/t Al)": total_co2,

        # Optional but useful breakdown column (electricity-only)
        "Electricity CO₂  (tCO₂/t Al)": electricity_co2,

        "CO₂ elec (tCO₂/t Al)": elec_co2_int,
        "CO₂ bauxite (tCO₂/t Al)": bauxite_co2_int,
        "CO₂ anode (tCO₂/t Al)": anode_co2_int,
        "CO₂ reaction (tCO₂/t Al)": reaction_co2_int,
        "Total Al (t)": co2_info["total_al"],   # total tonnes of aluminium (already in the function)

    })

df = pd.DataFrame(results)

df["Total CO₂ (t)"] = df["Total CO₂ footprint  (tCO₂/t Al)"] * df["Total Al (t)"]

# =================================================
# Visual styling
# =================================================
PALETTE = (
    pc.qualitative.Dark24
    + pc.qualitative.Light24
    + pc.qualitative.Alphabet
)

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
    st.markdown(
        "<h3 style='font-size:1.25rem; margin:0 0 0.2rem 0;'>"
        "Global overview of aluminium production metrics"
        "</h3>",
        unsafe_allow_html=True
    )

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
            "Total CO₂ footprint  (tCO₂/t Al)": ":.0f",
            "Electricity CO₂  (tCO₂/t Al)": ":.0f",
        },
        #title="Total aluminium production cost by country",
    )
    fig_map.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
    )
    fig_map.update_geos(
        bgcolor="#0e1117",
        showcountries=True,
        countrycolor="#2a2f3a",
        showcoastlines=True,
        coastlinecolor="#3a3f4b",
        coastlinewidth=0.6,
        showframe=False,
        projection_type="natural earth",
    )

    fig_map.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="€/t aluminium"),
    )

    st.plotly_chart(fig_map, use_container_width=True)

# =================================================
# TAB — Scenario outcomes
# =================================================
with tab_scenario:
    #st.subheader("Scenario outcomes")

    fig1 = px.scatter(
        df,
        x="Electricity CO₂ footprint (kgCO₂/kWh)",
        y="Electricity price (€/kWh)",
        color="Country",
        title="Electricity price vs Electricity CO₂ footprint (Grid)",
        color_discrete_sequence=PALETTE
    )
    fig1.update_traces(marker=dict(opacity=1.0))
    fig1.update_layout(
        height=500,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Total cost (€/t)",
        color="Country",
        title="Total production cost vs electricity price",
        color_discrete_sequence=PALETTE
    )
    fig2.update_traces(marker=dict(opacity=1.0))
    fig2.update_layout(
        height=620,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.scatter(
        df,
        x="Total CO₂ footprint  (tCO₂/t Al)",
        y="Total cost (€/t)",
        color="Country",
        title="Total production cost vs TOTAL CO₂ footprint",
        color_discrete_sequence=PALETTE
    )
    fig3.update_traces(marker=dict(opacity=1.0))
    fig3.update_layout(
        height=620,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig3, use_container_width=True)

    fig4 = px.scatter(
        df,
        x="Electricity price (€/kWh)",
        y="Electricity cost (€/t)",
        color="Country",
        title="Electricity cost vs electricity price",
        color_discrete_sequence=PALETTE
    )
    fig4.update_traces(marker=dict(opacity=1.0))
    fig4.update_layout(
        height=620,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig4, use_container_width=True)
    
    

    fig5 = px.scatter(
        df,
        x="Electricity CO₂  (tCO₂/t Al)",
        y="Total CO₂ footprint  (tCO₂/t Al)",
        color="Country",
        title="Total CO₂ footprint vs electricity CO₂ footprint",
        color_discrete_sequence=PALETTE
        
    )
    fig5.update_traces(marker=dict(opacity=1.0))
    fig5.update_layout(
        height=620,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig5, use_container_width=True)
    
    fig6 = px.scatter(
        df,
        x="Electricity CO₂ footprint (kgCO₂/kWh)",
        y="Total CO₂ footprint  (tCO₂/t Al)",
        color="Country",
        title="Total CO₂ footprint vs electricity CO₂ footprint (Grid)",
        color_discrete_sequence=PALETTE
        
    )
    fig6.update_traces(marker=dict(opacity=1.0))
    fig6.update_layout(
        height=620,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=9)
        )
    )
    st.plotly_chart(fig6, use_container_width=True)
    ###########################################################################33

    fig_total_emissions = px.scatter(
        df,
        x="Total Al (t)",
        y="Total CO₂ (t)",
        color="Country",
        title="Total CO₂ emissions vs total aluminium (by country)",
        color_discrete_sequence=PALETTE
    )
    fig_total_emissions.update_traces(marker=dict(opacity=1.0))
    st.plotly_chart(fig_total_emissions, use_container_width=True, key="total_co2_vs_total_al")


    ######################################################################################
    fig_intensity_vs_scale = px.scatter(
        df,
        x="Total Al (t)",
        y="Total CO₂ footprint  (tCO₂/t Al)",
        color="Country",
        title="CO₂ intensity vs total aluminium (by country)",
        color_discrete_sequence=PALETTE
    )
    fig_intensity_vs_scale.update_traces(marker=dict(opacity=1.0))
    st.plotly_chart(fig_intensity_vs_scale, use_container_width=True, key="intensity_vs_total_al")

    ############################################################################
    st.markdown("### CO₂ footprint breakdown (per tonne of Al)")
    
    country_for_pie = st.selectbox(
        "Select a country",
        options=sorted(df["Country"].unique()),
        key="pie_country_select"
    )




    row = df[df["Country"] == country_for_pie].iloc[0]

    pie_fig = px.pie(
        names=["Electricity", "Bauxite", "Anode", "Reaction"],
        values=[
            row["CO₂ elec (tCO₂/t Al)"],
            row["CO₂ bauxite (tCO₂/t Al)"],
            row["CO₂ anode (tCO₂/t Al)"],
            row["CO₂ reaction (tCO₂/t Al)"],
        ],
        title=f"CO₂ sources for {country_for_pie} (tCO₂/t Al)"
    )

    pie_fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(pie_fig, use_container_width=True, key="co2_pie")

# =================================================
# TAB — Cost structure
# =================================================
#with tab_costs:
    #st.subheader("Cost composition by country")

with tab_costs:
    st.markdown(
        "<h3 style='font-size:1.25rem; margin:0 0 0.2rem 0;'>"
        "Cost composition by country"
        "</h3>",
        unsafe_allow_html=True
    )

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
        margin={"r": 0, "t": 20, "l": 0, "b": 0},
        yaxis_title="€/t aluminium",
        xaxis_title="Country",
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.round(2), use_container_width=True)


































































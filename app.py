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
    "An academic decision-support model evaluating cost and carbon trade-offs "
    "in primary aluminium production under alternative electricity and policy scenarios."
)

# =================================================
# Data loading
# =================================================
country_df = pd.read_csv("data/country_electricity_mix.csv")
electricity_df = pd.read_csv("data/electricity_price_co2.csv")
materials_df = pd.read_csv("data/materials_trade.csv")

sources = [
    "coal", "gas", "other fossil", "nuclear", "bioenergy",
    "hydro", "solar", "wind", "other renewables"
]

co2_factors = {
    "coal": 0.82,
    "gas": 0.49,
    "other fossil": 0.74,
    "nuclear": 0.012,
    "bioenergy": 0.23,
    "hydro": 0.004,
    "solar": 0.041,
    "wind": 0.011,
    "other renewables": 0.038,
}

price_factors = {
    "coal": 0.074,
    "gas": 0.046,
    "other fossil": 0.064,
    "nuclear": 0.129,
    "bioenergy": 0.055,
    "hydro": 0.046,
    "solar": 0.040,
    "wind": 0.031,
    "other renewables": 0.037,
}

# =================================================
# Sidebar — global scenario definition
# =================================================
with st.sidebar:
    st.header("Select Country(s)")

    countries_selected = st.multiselect(
        "Countries included in comparison",
        sorted(country_df["country"].unique()),
        default=["China", "Canada"],
    )

    st.markdown("---")
    st.header("Scenario")

    carbon_tax = st.number_input(
        "Carbon price (€/t CO₂)",
        min_value=0.0,
        max_value=300.0,
        value=60.0,
        step=5.0,
    )

    margin_rate = (
        st.number_input(
            "Producer margin (% of operational cost)",
            min_value=0.0,
            max_value=50.0,
            value=15.0,
            step=1.0,
        )
        / 100.0
    )

    st.markdown("---")
    st.subheader("Interpretation note")
    st.markdown(
        "The model represents average production conditions. "
        "Electricity prices and carbon intensities respond endogenously "
        "to the assumed electricity mix."
    )

# =================================================
# Grid mix adjustment (scenario layer)
# =================================================
country_mixes = {}

for country in countries_selected:
    cdata = country_df[country_df["country"] == country].iloc[0]
    mix = {source: float(cdata[source]) for source in sources}
    country_mixes[country] = mix

# =================================================
# Core model calculations (unchanged math)
# =================================================
results = []

for country in countries_selected:
    cdata = country_df[country_df["country"] == country].iloc[0]
    edata = electricity_df[electricity_df["country"] == country].iloc[0]

    E = cdata["energy_kwh_per_t"]
    labour_cost = cdata["labour_cost_eur_per_t"]

    mix = country_mixes[country]
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

    results.append(
        {
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
        }
    )

df = pd.DataFrame(results)

# =================================================
# Visual styling
# =================================================
PALETTE = pc.qualitative.Alphabet
country_colors = {
    c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)
}

# =================================================
# Main layout — tabs
# =================================================
tab_scenario, tab_grid, tab_costs = st.tabs(
    ["⚙️ Scenario Builder", "⚡ Electricity & Grid", "💰 Cost Structure"]
)

# -------------------------------------------------
# TAB 1 — Overview (decision-focused)
# -------------------------------------------------
# Scenario builder
# -------------------------------------------------
with tab_scenario:
    st.subheader("Scenario outcomes and sensitivities")
    st.markdown(
        "This tab combines scenario definition with key outcome indicators and sensitivity analyses."
    )

    st.markdown("### Cost–emissions trade-off")

    fig_tradeoff = px.scatter(
        df,
        x="CO₂ footprint (kg/t)",
        y="Total cost (€/t)",
        text="Country",
        color="Country",
        color_discrete_map=country_colors,
    )

    fig_tradeoff.update_traces(textposition="top center")
    fig_tradeoff.update_layout(
        xaxis_title="Carbon footprint (kg CO₂ / t aluminium)",
        yaxis_title="Total production cost (€/t)",
    )

    st.plotly_chart(fig_tradeoff, use_container_width=True)

    st.markdown("---")
    st.markdown("### Electricity cost sensitivity to electricity price")

    price_range = np.linspace(0.03, 0.20, 200)
    fig_el_cost = go.Figure()

    for _, r in df.iterrows():
        E = country_df[country_df["country"] == r["Country"]]["energy_kwh_per_t"].iloc[0]
        electricity_cost_curve = E * price_range

        fig_el_cost.add_trace(
            go.Scatter(
                x=price_range,
                y=electricity_cost_curve,
                mode="lines",
                name=r["Country"],
                line=dict(color=country_colors[r["Country"]], width=2),
            )
        )

    fig_el_cost.update_layout(
        xaxis_title="Electricity price (€/kWh)",
        yaxis_title="Electricity cost (€/t)",
        hovermode="x unified",
    )

    st.plotly_chart(fig_el_cost, use_container_width=True)

    st.markdown("---")
    st.markdown("### Electricity + carbon cost sensitivity to electricity price")

    fig_el_carbon = go.Figure()

    for _, r in df.iterrows():
        E = country_df[country_df["country"] == r["Country"]]["energy_kwh_per_t"].iloc[0]
        electricity_co2 = r["CO₂ footprint (kg/t)"]

        combined_cost_curve = E * price_range + (electricity_co2 / 1000) * carbon_tax

        fig_el_carbon.add_trace(
            go.Scatter(
                x=price_range,
                y=combined_cost_curve,
                mode="lines",
                name=r["Country"],
                line=dict(color=country_colors[r["Country"]], width=2),
            )
        )

    fig_el_carbon.update_layout(
        xaxis_title="Electricity price (€/kWh)",
        yaxis_title="Electricity + carbon cost (€/t)",
        hovermode="x unified",
    )

    st.plotly_chart(fig_el_carbon, use_container_width=True)

# -------------------------------------------------
# TAB 3 — Electricity & grid mix — Electricity & grid mix
# -------------------------------------------------
with tab_grid:
    st.subheader("Electricity system representation")

    selected_country = st.selectbox("Select country", countries_selected)
    mix = country_mixes[selected_country]

    mix_df = pd.DataFrame(
        {"Source": list(mix.keys()), "Share": list(mix.values())}
    )

    fig_mix = px.bar(
        mix_df,
        x="Source",
        y="Share",
        title=f"Electricity mix — {selected_country}",
    )

    st.plotly_chart(fig_mix, use_container_width=True)

    with st.expander("Adjust grid mix manually"):
        new_mix = {}
        for s in sources:
            new_mix[s] = st.slider(
                s.capitalize(),
                min_value=0.0,
                max_value=1.0,
                value=mix[s],
                step=0.01,
                key=f"grid_{selected_country}_{s}",
            )

        total = sum(new_mix.values())
        if total > 0:
            for s in sources:
                mix[s] = new_mix[s] / total

        st.info(
            f"Resulting electricity price: "
            f"{sum(mix[s]*price_factors[s] for s in sources):.3f} €/kWh  \
"
            f"Resulting CO₂ intensity: "
            f"{sum(mix[s]*co2_factors[s] for s in sources):.3f} kg/kWh"
        )

# -------------------------------------------------
# TAB 4 — Cost structure
# -------------------------------------------------
with tab_costs:
    st.subheader("Cost composition by country")

    cost_cols = [
        "Electricity cost (€/t)",
        "Labour cost (€/t)",
        "Material cost (€/t)",
        "Margin (€/t)",
        "Carbon cost (€/t)",
    ]

    fig_stack = go.Figure()
    for col in cost_cols:
        fig_stack.add_trace(
            go.Bar(x=df["Country"], y=df[col], name=col)
        )

    fig_stack.update_layout(
        barmode="stack",
        yaxis_title="€/t aluminium",
        xaxis_title="Country",
    )

    st.plotly_chart(fig_stack, use_container_width=True)

    st.markdown("---")
    st.caption("Detailed numerical outputs")
    st.dataframe(df.round(2), use_container_width=True)



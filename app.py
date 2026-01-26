import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc

# -------------------------------------------------
# Custom CSS for enhanced styling
# -------------------------------------------------
st.markdown("""
<style>
    .stApp { 
        background-color: #f0f4f8; 
        font-family: 'Arial', sans-serif;
    }
    .stButton > button { 
        background-color: #4CAF50; 
        color: white; 
        border-radius: 4px;
    }
    .stExpander { 
        border: 1px solid #ddd; 
        border-radius: 4px; 
    }
    h1, h2, h3 { 
        color: #333; 
    }
    .metric-container {
        background-color: white;
        padding: 10px;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Aluminium Production Decision Model",
    page_icon="⚡",
    layout="wide"
)
st.title("⚡ Aluminium Production — Integrated Decision Model")

# -------------------------------------------------
# Load CSV data
# -------------------------------------------------
@st.cache_data
def load_data():
    country_df = pd.read_csv("data/country_electricity_mix.csv")
    electricity_df = pd.read_csv("data/electricity_price_co2.csv")
    materials_df = pd.read_csv("data/materials_trade.csv")
    return country_df, electricity_df, materials_df

country_df, electricity_df, materials_df = load_data()

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
    st.header("Scenario Controls")
    st.info("Adjust settings below to explore scenarios. Changes update in real-time.")

    countries_selected = st.multiselect(
        "Select Countries",
        sorted(country_df["country"].unique()),
        default=["China", "Canada"],
        help="Choose one or more countries for comparison."
    )

    carbon_tax = st.number_input(
        "Carbon Tax (€/t CO₂)",
        min_value=0.0,
        max_value=300.0,
        value=60.0,
        step=1.0,
        help="Set the carbon tax rate to see its impact on costs."
    )

    margin_rate = st.number_input(
        "Margin (% of operational cost)",
        min_value=0.0,
        max_value=50.0,
        value=15.0,
        step=0.5,
        help="Adjust the profit margin percentage."
    ) / 100.0

    # Checkbox to enable custom grid mixes
    enable_custom_mix = st.checkbox("Enable Custom Grid Mix Scenarios", value=False, help="Toggle to adjust energy mixes for each country.")

# -------------------------------------------------
# Core calculations
# -------------------------------------------------
@st.cache_data(ttl=3600)  # Cache for 1 hour
def compute_results(countries_selected, carbon_tax, margin_rate, country_mixes):
    results = []
    for country in countries_selected:
        cdata = country_df[country_df["country"] == country].iloc[0]
        edata = electricity_df[electricity_df["country"] == country].iloc[0]

        E = cdata["energy_kwh_per_t"]
        labour_cost = cdata["labour_cost_eur_per_t"]

        mix = country_mixes.get(country, {s: float(cdata[s]) for s in sources})
        electricity_price = sum(mix[source] * price_factors[source] for source in sources)
        grid_co2_intensity = sum(mix[source] * co2_factors[source] for source in sources)

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
    return pd.DataFrame(results)

# Grid Mix Scenarios (conditional)
country_mixes = {}
if enable_custom_mix:
    for country in countries_selected:
        cdata = country_df[country_df["country"] == country].iloc[0]
        with st.sidebar.expander(f"{country} Grid Mix"):
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
                for source in sources:
                    mix[source] = float(cdata[source])
            country_mixes[country] = mix
            # Pie chart for visual feedback
            fig_pie = px.pie(names=sources, values=[mix[s] for s in sources], title=f"{country} Energy Mix")
            st.plotly_chart(fig_pie, use_container_width=True)

# Compute results
df = compute_results(countries_selected, carbon_tax, margin_rate, country_mixes)

# -------------------------------------------------
# Visual styling
# -------------------------------------------------
PALETTE = pc.qualitative.Alphabet
country_colors = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(countries_selected)}

# -------------------------------------------------
# Tabs for organized navigation
# -------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📊 Overview", "📈 Charts", "🔧 Scenarios"])

with tab1:
    st.subheader("Key Insights")
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Total Cost (€/t)", f"€{df['Total cost (€/t)'].mean():.2f}")
        with col2:
            st.metric("Avg CO₂ Footprint (kg/t)", f"{df['CO₂ footprint (kg/t)'].mean():.2f}")
        with col3:
            min_cost_country = df.loc[df['Total cost (€/t)'].idxmin(), 'Country']
            st.metric("Lowest Cost Country", min_cost_country)
        with col4:
            min_co2_country = df.loc[df['CO₂ footprint (kg/t)'].idxmin(), 'Country']
            st.metric("Lowest CO₂ Country", min_co2_country)
    
    st.subheader("Cost Summary Table")
    st.dataframe(df.style.format("{:.2f}").background_gradient(cmap="viridis"), use_container_width=True)
    
    # Download button
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Results as CSV",
        data=csv,
        file_name='aluminium_costs.csv',
        mime='text/csv',
        help="Export the summary table for further analysis."
    )

with tab2:
    st.subheader("Electricity Cost + Carbon Cost vs Price")
    price_range = np.linspace(0.03, 0.20, 200)
    fig_el = go.Figure()
    for _, r in df.iterrows():
        E = country_df[country_df["country"] == r["Country"]]["energy_kwh_per_t"].iloc[0]
        curve = E * price_range + r["Carbon cost (€/t)"]
        fig_el.add_trace(go.Scatter(x=price_range, y=curve, mode="lines", name=r["Country"], line=dict(color=country_colors[r["Country"]], width=2)))
    fig_el.update_layout(xaxis_title="Electricity Price (€/kWh)", yaxis_title="Electricity + Carbon Cost (€/t)", hovermode="x unified")
    st.plotly_chart(fig_el, use_container_width=True)
    
    st.subheader("Electricity Price vs CO₂ Footprint")
    fig_co2 = px.scatter(df, x="CO₂ footprint (kg/t)", y="Electricity price (€/kWh)", text="Country", color="Country", color_discrete_map=country_colors)
    fig_co2.update_traces(textposition="top center")
    st.plotly_chart(fig_co2, use_container_width=True)
    
    st.subheader("Cost Structure by Country")
    cost_cols = ["Electricity cost (€/t)", "Labour cost (€/t)", "Material cost (€/t)", "Margin (€/t)", "Carbon cost (€/t)"]
    fig_stack = go.Figure()
    for col in cost_cols:
        fig_stack.add_trace(go.Bar(x=df["Country"], y=df[col], name=col))
    fig_stack.update_layout(barmode="stack", yaxis_title="€/t Aluminium", xaxis_title="Country")
    st.plotly_chart(fig_stack, use_container_width=True)

with tab3:
    st.subheader("Advanced Scenario Analysis")
    st.write("Explore custom grid mixes and their impacts. Enable in sidebar to adjust.")
    if enable_custom_mix:
        for country in countries_selected:
            st.write(f"**{country} Mix Details**")
            mix_df = pd.DataFrame({"Source": sources, "Percentage": [country_mixes[country][s] * 100 for s in sources]})
            st.table(mix_df)
    else:
        st.info("Enable custom mixes in the sidebar to customize energy sources.")

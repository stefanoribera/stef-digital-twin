import httpx
import polars as pl
import pyarrow as pa
import streamlit as st
import plotly.express as px

# Internal Docker DNS routing (Tier-4 to Tier-0)
API_URL = "http://stef-api:8000"

st.set_page_config(page_title="CMS Z-Boson Resonance", layout="wide")
st.title("EOSC Digital Twin: Z-Boson Kinematics")

@st.cache_data(ttl=2)
def fetch_zero_copy_stream():
    """Fetches and parses the Arrow IPC stream with zero memory copies."""
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/physics/z-bosons", timeout=10.0)
            response.raise_for_status()

        # Parse binary bytes directly into an Arrow Table
        reader = pa.ipc.open_stream(response.content)
        arrow_table = reader.read_all()
        
        # Zero-Copy transition to Polars DataFrame
        return pl.from_arrow(arrow_table)
    except Exception as e:
        st.error(f"Streamlink Failure: {e}")
        return pl.DataFrame({"invariant_mass": []})

df = fetch_zero_copy_stream()

if df.is_empty():
    st.warning("No Z-Boson events detected. Awaiting Tier-2 ingestion...")
else:
    st.success(f"Successfully streaming {df.height} resonant events via ADBC/Arrow IPC.")
    
    # Extract native arrays for Plotly to avoid Pandas bloat
    fig = px.histogram(
        x=df["invariant_mass"].to_numpy(),
        nbins=50,
        title="Z-Boson Invariant Mass Distribution",
        labels={"x": "Mass (GeV)", "y": "Event Count"},
        color_discrete_sequence=["#00b4d8"]
    )
    st.plotly_chart(fig, use_container_width=True)

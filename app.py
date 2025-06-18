import streamlit as st
import pandas as pd
import plotly.express as px
import re
from io import StringIO

st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")

st.markdown("---")

# --- Upload Multiple Files ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV (| delimiter)", 
    type=["csv"], 
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("⬆️ Silakan upload minimal satu file.")
    st.stop()

# --- Load and Combine All Uploaded Data ---
all_data = []

for file in uploaded_files:
    # Extract date from filename
    filename = file.name
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    upload_date = match.group(1) if match else "Unknown"

    try:
        df = pd.read_csv(file, delimiter="|")
        df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
        df = (
            df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"]
            .sum()
        )
        df["upload_date"] = upload_date
        all_data.append(df)
    except Exception as e:
        st.error(f"Gagal membaca file `{filename}`: {e}")

if not all_data:
    st.warning("Tidak ada data yang berhasil diproses.")
    st.stop()

df_all = pd.concat(all_data, ignore_index=True)

# --- Date Selection ---
available_dates = sorted(df_all["upload_date"].unique(), reverse=True)
selected_date = st.selectbox("📅 Pilih Tanggal Data", available_dates)

df = df_all[df_all["upload_date"] == selected_date]

st.markdown("---")

# --- Summary Stats ---
st.header("📊 Ringkasan Data")

total_piutang = df["currentbal"].sum()
jml_nasabah = df["custcode"].nunique()

col1, col2 = st.columns(2)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)

st.markdown("---")

# --- Sales Summary Chart ---
st.subheader("📌 Distribusi Kategori Sales")
sales_summary = df.groupby("salesid")["currentbal"].sum().reset_index()
fig_sales = px.bar(
    sales_summary,
    x="salesid",
    y="currentbal",
    title="Total Piutang per Kategori Sales",
    labels={"salesid": "Kategori", "currentbal": "Nilai Piutang"},
)
fig_sales.update_traces(hovertemplate="Rp %{y:,.0f}")
st.plotly_chart(fig_sales, use_container_width=True)

# --- Top Clients Chart ---
st.subheader("🏆 Top 10 Nasabah dengan Piutang Tertinggi")
top_clients = df.nlargest(10, "currentbal")
fig_top = px.bar(
    top_clients,
    x="custname",
    y="currentbal",
    title="Top 10 Nasabah",
    text="currentbal",
    labels={"custname": "Nasabah", "currentbal": "Piutang"},
)
fig_top.update_traces(texttemplate="Rp %{text:,.0f}", hovertemplate="Rp %{y:,.0f}")
st.plotly_chart(fig_top, use_container_width=True)

st.markdown("---")

# --- Raw Data Table ---
st.subheader(f"📋 Tabel Data — Tanggal: {selected_date}")
st.dataframe(
    df.sort_values("currentbal", ascending=False).reset_index(drop=True),
    use_container_width=True
)

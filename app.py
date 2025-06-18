import streamlit as st
import pandas as pd
import plotly.express as px
import re

st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")

# --- Upload Section ---
st.header("1️⃣ Upload CSV Harian")

uploaded_file = st.file_uploader("Upload file CSV (| delimiter)", type=["csv"])
if uploaded_file is None:
    st.warning("Silakan upload file terlebih dahulu.")
    st.stop()

# --- Extract date from filename ---
filename = uploaded_file.name
match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
upload_date = match.group(1) if match else "Unknown"

# --- Load and Prepare Data ---
try:
    df = pd.read_csv(uploaded_file, delimiter="|")
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

# Convert and clean
df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)

# Group by custcode to sum duplicates
df = (
    df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"]
    .sum()
)

# Add upload date column
df["upload_date"] = upload_date

# --- Summary Stats ---
total_piutang = df["currentbal"].sum()
jml_nasabah = df["custcode"].nunique()

col1, col2 = st.columns(2)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)

# --- Sales Summary Chart ---
st.subheader("📌 Distribusi Kategori Sales")
sales_summary = df.groupby("salesid")["currentbal"].sum().reset_index()
fig_sales = px.bar(
    sales_summary,
    x="salesid",
    y="currentbal",
    title="Piutang per Kategori Sales",
    labels={"currentbal": "Rp"},
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
    labels={"currentbal": "Rp"},
)
fig_top.update_traces(texttemplate="Rp %{text:,.0f}", hovertemplate="Rp %{y:,.0f}")
st.plotly_chart(fig_top, use_container_width=True)

# --- Raw Data Preview ---
st.subheader(f"📋 Tabel Data (Dari File Tanggal: {upload_date})")
df_display = df.copy()
df_display["currentbal"] = df_display["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
st.dataframe(df_display.sort_values("currentbal", ascending=False), use_container_width=True)

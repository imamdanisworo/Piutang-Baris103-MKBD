import streamlit as st
import pandas as pd
import plotly.express as px
import re

# --- Page Setup ---
st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")
st.markdown("---")

# --- File Upload Section ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV dengan pemisah `|`", 
    type=["csv"], 
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("⬆️ Silakan upload minimal satu file CSV.")
    st.stop()

# --- Read and Combine Uploaded Data ---
all_data = []

for file in uploaded_files:
    filename = file.name
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    upload_date = match.group(1) if match else "Unknown"

    try:
        df = pd.read_csv(file, delimiter="|")
        df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
        df_grouped = (
            df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"]
            .sum()
        )
        df_grouped["upload_date"] = upload_date
        all_data.append(df_grouped)
    except Exception as e:
        st.error(f"❌ Gagal membaca file `{filename}`: {e}")

if not all_data:
    st.warning("⚠️ Tidak ada data yang berhasil diproses.")
    st.stop()

df_all = pd.concat(all_data, ignore_index=True)

# --- Sidebar Filter ---
st.sidebar.header("🔎 Filter Data")
salesid_options = ["Semua"] + sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("Pilih SalesID", salesid_options)

df_filtered = df_all if selected_salesid == "Semua" else df_all[df_all["salesid"] == selected_salesid]

# --- Trend Chart ---
st.header("📈 Tren Total Piutang per Hari")
df_trend = (
    df_filtered.groupby("upload_date")["currentbal"]
    .sum()
    .reset_index()
    .sort_values("upload_date")
)

fig_trend = px.line(
    df_trend,
    x="upload_date",
    y="currentbal",
    title=f"Total Piutang per Hari{' — SalesID: ' + selected_salesid if selected_salesid != 'Semua' else ''}",
    markers=True,
    labels={"upload_date": "Tanggal", "currentbal": "Total Piutang"},
)
fig_trend.update_traces(mode="lines+markers", hovertemplate="Tanggal: %{x}<br>Total: Rp %{y:,.0f}")
st.plotly_chart(fig_trend, use_container_width=True)

# --- Date Selector ---
st.subheader("📅 Pilih Tanggal untuk Analisis Detail")
available_dates = sorted(df_all["upload_date"].unique(), reverse=True)
selected_date = st.selectbox("Tanggal Data", available_dates)

df_date = df_all[df_all["upload_date"] == selected_date]

st.markdown("---")

# --- Summary Cards ---
st.header("📊 Ringkasan Piutang")
total_piutang = df_date["currentbal"].sum()
jumlah_nasabah = df_date["custcode"].nunique()

col1, col2 = st.columns(2)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jumlah_nasabah)

st.markdown("---")

# --- Tabel Rincian ---
st.subheader(f"📋 Tabel Piutang — Tanggal: {selected_date}")
df_sorted = df_date.sort_values("currentbal", ascending=False).reset_index(drop=True)
df_sorted["currentbal"] = df_sorted["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
st.dataframe(df_sorted, use_container_width=True)

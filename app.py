import streamlit as st
import pandas as pd
import plotly.express as px
import re

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

# --- Sidebar Filter: salesid selection ---
salesid_list = sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("📂 Filter berdasarkan SalesID", ["Semua"] + salesid_list)

if selected_salesid != "Semua":
    df_all_filtered = df_all[df_all["salesid"] == selected_salesid]
else:
    df_all_filtered = df_all

# --- Line Chart: Total Piutang per Date ---
st.header("📈 Tren Total Piutang per Hari")

df_trend = (
    df_all_filtered.groupby("upload_date")["currentbal"]
    .sum()
    .reset_index()
    .sort_values("upload_date")
)

fig_line = px.line(
    df_trend,
    x="upload_date",
    y="currentbal",
    title=f"Total Piutang per Hari{' — SalesID: ' + selected_salesid if selected_salesid != 'Semua' else ''}",
    markers=True,
    labels={"upload_date": "Tanggal", "currentbal": "Total Piutang"},
)
fig_line.update_traces(mode="lines+markers", hovertemplate="Tanggal %{x}<br>Rp %{y:,.0f}")
st.plotly_chart(fig_line, use_container_width=True)

# --- Select Specific Date ---
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

# --- Raw Data Table ---
st.subheader(f"📋 Tabel Data — Tanggal: {selected_date}")

# Sort numerically, then format
df_sorted = df.sort_values("currentbal", ascending=False).reset_index(drop=True)
df_display = df_sorted.copy()
df_display["currentbal"] = df_display["currentbal"].apply(lambda x: f"Rp {x:,.0f}")

st.dataframe(df_display, use_container_width=True)

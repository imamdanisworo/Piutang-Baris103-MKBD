import streamlit as st
import pandas as pd
import os
from huggingface_hub import HfApi, HfFileSystem
from io import StringIO
import plotly.express as px

# Config
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
HF_TOKEN = os.getenv("HF_TOKEN")  # Set this securely in your environment
fs = HfFileSystem(token=HF_TOKEN)
api = HfApi(token=HF_TOKEN)

st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")

# --- Upload Section ---
st.header("1️⃣ Upload CSV Harian")

uploaded_file = st.file_uploader("Upload file CSV (| delimiter)", type=["csv"])
if uploaded_file is not None:
    filename = uploaded_file.name
    file_content = uploaded_file.read()

    # Save to Hugging Face dataset
    remote_path = f"{REPO_ID}/data/{filename}"
    with fs.open(remote_path, "wb") as f:
        f.write(file_content)

    st.success(f"✅ File `{filename}` berhasil diupload ke Hugging Face.")
    st.button("🔄 Selesai Upload — Klik untuk refresh")

# --- Load & Combine Data ---
st.header("2️⃣ Ringkasan Data")

@st.cache_data
def load_all_data():
    try:
        file_list = fs.ls(f"{REPO_ID}/data", detail=False)
    except FileNotFoundError:
        return pd.DataFrame()  # No folder or data yet

    dataframes = []
    for file_path in file_list:
        if not file_path.endswith(".csv"):
            continue
        with fs.open(file_path, "r") as f:
            df = pd.read_csv(f, delimiter="|")
            df["source_file"] = os.path.basename(file_path)
            dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True) if dataframes else pd.DataFrame()

df_all = load_all_data()

if df_all.empty:
    st.warning("Belum ada data tersedia.")
    st.stop()

# --- Summary Stats ---
df_all["currentbal"] = pd.to_numeric(df_all["currentbal"], errors="coerce").fillna(0)

total_piutang = df_all["currentbal"].sum()
jml_nasabah = df_all["custcode"].nunique()
jml_hari = df_all["source_file"].nunique()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)
col3.metric("📆 Jumlah Hari Data", jml_hari)

# --- Visuals ---
st.subheader("📌 Distribusi Kategori Sales")
sales_summary = df_all.groupby("salesid")["currentbal"].sum().reset_index()
fig_sales = px.bar(sales_summary, x="salesid", y="currentbal", title="Piutang per Kategori Sales")
st.plotly_chart(fig_sales, use_container_width=True)

st.subheader("🏆 Top 10 Nasabah dengan Piutang Tertinggi")
top_clients = df_all.groupby(["custcode", "custname"])["currentbal"].sum().nlargest(10).reset_index()
fig_top = px.bar(top_clients, x="custname", y="currentbal", title="Top 10 Nasabah", text="currentbal")
st.plotly_chart(fig_top, use_container_width=True)

# --- Data Preview ---
st.subheader("📋 Tabel Data")
st.dataframe(df_all.sort_values("currentbal", ascending=False), use_container_width=True)

import streamlit as st
import pandas as pd
import os
from huggingface_hub import HfApi, HfFileSystem
from io import BytesIO
import plotly.express as px

# Configuration
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
HF_TOKEN = os.getenv("HF_TOKEN")  # Set in HF Spaces → Secrets
api = HfApi(token=HF_TOKEN)
fs = HfFileSystem(token=HF_TOKEN)

st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")

# --- Ensure dataset exists ---
try:
    api.repo_info(repo_id=REPO_ID, repo_type="dataset")
except Exception:
    api.create_repo(
        repo_id=REPO_ID,
        repo_type="dataset",
        private=True,
        exist_ok=True
    )
    st.info("📁 Dataset baru berhasil dibuat di Hugging Face.")

# --- Upload Section ---
st.header("1️⃣ Upload CSV Harian")

uploaded_file = st.file_uploader("Upload file CSV (| delimiter)", type=["csv"])
if uploaded_file is not None:
    filename = uploaded_file.name
    file_bytes = uploaded_file.read()
    remote_path = f"{REPO_ID}/data/{filename}"

    # Ensure the /data folder exists
    try:
        fs.ls(f"{REPO_ID}/data")
    except FileNotFoundError:
        api.upload_file(
            path_or_fileobj=BytesIO(b"init"),
            path_in_repo="data/.keep",
            repo_id=REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN
        )

    # Upload the actual file
    try:
        with fs.open(remote_path, "wb") as f:
            f.write(file_bytes)
        st.success(f"✅ File `{filename}` berhasil diupload ke Hugging Face.")
        st.button("🔄 Selesai Upload — Klik untuk refresh")
    except Exception as e:
        st.error(f"❌ Gagal upload file: {e}")
        st.stop()

# --- Load All Data ---
st.header("2️⃣ Ringkasan Data")

@st.cache_data
def load_all_data():
    try:
        file_list = fs.ls(f"{REPO_ID}/data", detail=False)
    except FileNotFoundError:
        return pd.DataFrame()

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

# --- Clean + Group Data ---
df_all["currentbal"] = pd.to_numeric(df_all["currentbal"], errors="coerce").fillna(0)

# 🔁 Group by custcode to remove duplicates and sum balances
df_all = (
    df_all.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"]
    .sum()
)

# --- Summary Stats ---
total_piutang = df_all["currentbal"].sum()
jml_nasabah = df_all["custcode"].nunique()
jml_file = load_all_data()["source_file"].nunique()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)
col3.metric("📂 Jumlah File Diupload", jml_file)

# --- Sales Summary Chart ---
st.subheader("📌 Distribusi Kategori Sales")
sales_summary = df_all.groupby("salesid")["currentbal"].sum().reset_index()
fig_sales = px.bar(sales_summary, x="salesid", y="currentbal", title="Piutang per Kategori Sales")
st.plotly_chart(fig_sales, use_container_width=True)

# --- Top Clients Chart ---
st.subheader("🏆 Top 10 Nasabah dengan Piutang Tertinggi")
top_clients = df_all.nlargest(10, "currentbal")
fig_top = px.bar(top_clients, x="custname", y="currentbal", title="Top 10 Nasabah", text="currentbal")
st.plotly_chart(fig_top, use_container_width=True)

# --- Raw Data Preview ---
st.subheader("📋 Tabel Data")
st.dataframe(df_all.sort_values("currentbal", ascending=False), use_container_width=True)

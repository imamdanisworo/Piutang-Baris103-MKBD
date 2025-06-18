import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
from huggingface_hub import HfApi, upload_file
from io import StringIO

# --- CONFIG ---
HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
ALLOWED_PATTERN = r"(bal_detail_103_\d{4}-\d{2}-\d{2})"

# --- PAGE SETUP ---
st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")
st.title("📤 Upload & Analisa Piutang Nasabah")
st.markdown("---")

# --- FILE UPLOADER ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV (`|` delimiter, format: bal_detail_103_yyyy-mm-dd.csv)", 
    type=["csv"], 
    accept_multiple_files=True
)

if not uploaded_files:
    st.info("⬆️ Silakan upload minimal satu file.")
    st.stop()

# --- Hugging Face API ---
hf_api = HfApi(token=HF_TOKEN)

# --- LOAD & CLEAN FILES ---
all_data = []
for file in uploaded_files:
    original_name = file.name
    match = re.search(ALLOWED_PATTERN, original_name)
    if not match:
        st.warning(f"⚠️ Nama file `{original_name}` tidak valid. Akan dibersihkan otomatis.")
        match = re.search(r"\d{4}-\d{2}-\d{2}", original_name)
        if not match:
            st.error(f"❌ Gagal memproses `{original_name}`: tidak ditemukan tanggal valid.")
            continue
        cleaned_name = f"bal_detail_103_{match.group(0)}.csv"
    else:
        cleaned_name = match.group(0) + ".csv"

    upload_date = re.search(r"\d{4}-\d{2}-\d{2}", cleaned_name).group(0)

    try:
        df = pd.read_csv(file, delimiter="|")
        df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
        df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()
        df["upload_date"] = upload_date
        all_data.append(df)

        # Prepare content for upload
        content = file.getvalue()
        content_str = content.decode("utf-8")

        # --- Delete existing file if present
        existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
        if cleaned_name in existing_files:
            hf_api.delete_file(path_in_repo=cleaned_name, repo_id=REPO_ID, repo_type="dataset")

        # --- Upload cleaned file
        upload_file(
            path_or_fileobj=StringIO(content_str),
            path_in_repo=cleaned_name,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=HF_TOKEN
        )

        st.success(f"✅ `{cleaned_name}` berhasil diupload & disimpan.")
    except Exception as e:
        st.error(f"❌ Gagal membaca `{original_name}`: {e}")

if not all_data:
    st.warning("⚠️ Tidak ada data yang berhasil diproses.")
    st.stop()

# --- GABUNGKAN SEMUA DATA ---
df_all = pd.concat(all_data, ignore_index=True)

# --- SIDEBAR FILTER ---
st.sidebar.header("🔎 Filter Data")
salesid_list = ["Semua"] + sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("Pilih SalesID", salesid_list)
df_filtered = df_all if selected_salesid == "Semua" else df_all[df_all["salesid"] == selected_salesid]

# --- TREN PIUTANG ---
st.header("📈 Tren Total Piutang per Hari")
df_trend = (
    df_filtered.groupby("upload_date")["currentbal"]
    .sum()
    .reset_index()
    .sort_values("upload_date")
)

fig = px.line(
    df_trend,
    x="upload_date",
    y="currentbal",
    title=f"Total Piutang per Hari{' — SalesID: ' + selected_salesid if selected_salesid != 'Semua' else ''}",
    markers=True,
    labels={"upload_date": "Tanggal", "currentbal": "Total Piutang"}
)
fig.update_layout(xaxis_tickformat="%Y-%m-%d")  # ⛔ Remove time format
fig.update_traces(hovertemplate="Tanggal: %{x}<br>Total: Rp %{y:,.0f}")
st.plotly_chart(fig, use_container_width=True)

# --- SELECT TANGGAL ---
st.subheader("📅 Pilih Tanggal untuk Rincian Data")
available_dates = sorted(df_all["upload_date"].unique(), reverse=True)
selected_date = st.selectbox("Tanggal Data", available_dates)

df_selected = df_all[df_all["upload_date"] == selected_date]
st.markdown("---")

# --- RINGKASAN STATISTIK ---
st.header("📊 Ringkasan Data")
total_piutang = df_selected["currentbal"].sum()
jml_nasabah = df_selected["custcode"].nunique()

col1, col2 = st.columns(2)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)

# --- TABEL DETAIL ---
st.markdown("---")
st.subheader(f"📋 Tabel Rincian — Tanggal: {selected_date}")
df_view = df_selected.sort_values("currentbal", ascending=False).reset_index(drop=True)
df_view["currentbal"] = df_view["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
st.dataframe(df_view, use_container_width=True)

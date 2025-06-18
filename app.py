import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os
from huggingface_hub import HfApi, upload_file, hf_hub_download, delete_file
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="📊 Ringkasan Piutang", layout="wide")

# --- FULLY REMOVE COLLAPSE BUTTON & LOCK SIDEBAR OPEN ---
st.markdown("""
    <style>
    div[data-testid="collapsedControl"] {
        display: none !important;
        visibility: hidden !important;
        position: absolute !important;
        top: -9999px;
    }
    section[data-testid="stSidebar"] {
        transform: none !important;
        visibility: visible !important;
        width: 270px !important;
        min-width: 270px !important;
        max-width: 270px !important;
        position: relative !important;
        left: 0px !important;
    }
    .block-container {
        padding-left: 3rem !important;
        padding-right: 2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONFIG ---
HF_TOKEN = "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"
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
VALID_PATTERN = r"bal_detail_103_\d{4}-\d{2}-\d{2}\.csv"

hf_api = HfApi(token=HF_TOKEN)

st.title("📤 Upload & Analisa Piutang Nasabah")
st.markdown("---")

# --- FILE UPLOADER ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV (`|` delimiter, format: bal_detail_103_yyyy-mm-dd.csv)", 
    type=["csv"], 
    accept_multiple_files=True
)

# --- HANDLE MULTIPLE FILE UPLOADS ---
if uploaded_files:
    uploaded_success = False
    status_area = st.container()
    progress_area = st.container()

    with progress_area:
        st.info("⏳ Sedang memproses file yang diupload...")
        overall_progress = st.progress(0, text="Menyiapkan upload...")

    for idx, file in enumerate(uploaded_files):
        with status_area.status(f"📤 Mengunggah `{file.name}`...", expanded=True) as file_status:
            match = re.search(r"bal_detail_103_(\d{4}-\d{2}-\d{2})", file.name)
            if not match:
                file_status.error(f"⚠️ Nama file `{file.name}` tidak valid. Lewati.")
                continue

            cleaned_name = f"bal_detail_103_{match.group(1)}.csv"

            try:
                df = pd.read_csv(file, delimiter="|")
                df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
                df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()

                existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
                if cleaned_name in existing_files:
                    delete_file(cleaned_name, REPO_ID, "dataset", HF_TOKEN)

                upload_file(BytesIO(file.getvalue()), cleaned_name, REPO_ID, "dataset", HF_TOKEN)
                uploaded_success = True
                file_status.success(f"✅ `{cleaned_name}` berhasil diupload & disimpan.")
            except Exception as e:
                file_status.error(f"❌ Gagal memproses `{file.name}`: {e}")

            overall_progress.progress((idx + 1) / len(uploaded_files), text=f"📁 {idx + 1}/{len(uploaded_files)} file selesai")

    progress_area.empty()

    if uploaded_success:
        st.success("✅ Semua file berhasil diupload.")
        with st.spinner("🔄 Memuat ulang data terbaru..."):
            st.cache_data.clear()
            existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
            valid_files = [f for f in existing_files if re.match(VALID_PATTERN, f)]
            df_all = None
else:
    existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
    valid_files = [f for f in existing_files if re.match(VALID_PATTERN, f)]

# --- LOAD FILES (CACHED) ---
@st.cache_data(show_spinner="📥 Memuat data dari Hugging Face...")
def read_all_data_from_hf(file_list, repo_id, token):
    all_data = []
    for file_name in file_list:
        try:
            match = re.search(r"\d{4}-\d{2}-\d{2}", file_name)
            upload_date = pd.to_datetime(match.group(0)) if match else None
            if not upload_date:
                continue

            file_path = hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=file_name,
                token=token,
                local_dir="/tmp",
                local_dir_use_symlinks=False
            )

            df = pd.read_csv(file_path, delimiter="|")
            df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
            df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()
            df["upload_date"] = upload_date
            all_data.append(df)
        except Exception:
            pass

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame(
        columns=["custcode", "custname", "salesid", "currentbal", "upload_date"]
    )

df_all = read_all_data_from_hf(valid_files, REPO_ID, HF_TOKEN)
if df_all.empty:
    st.warning("⚠️ Tidak ada data yang berhasil dimuat.")
    st.stop()

# --- DELETE SECTION ---
st.sidebar.header("🗑️ Hapus Data")
delete_file_choice = st.sidebar.selectbox("Pilih file untuk dihapus", [""] + valid_files)
if st.sidebar.button("🗑️ Hapus File Ini") and delete_file_choice:
    delete_file(delete_file_choice, REPO_ID, "dataset", HF_TOKEN)
    st.cache_data.clear()
    st.sidebar.success(f"File `{delete_file_choice}` berhasil dihapus. Silakan refresh.")

if st.sidebar.button("🔥 Hapus Semua File"):
    for file in valid_files:
        delete_file(file, REPO_ID, "dataset", HF_TOKEN)
    st.cache_data.clear()
    st.sidebar.success("🚨 Semua file berhasil dihapus dari dataset.")

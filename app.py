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
HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
VALID_PATTERN = r"bal_detail_103_\d{4}-\d{2}-\d{2}\.csv"

st.title("📤 Upload & Analisa Piutang Nasabah")
st.markdown("---")

# --- HF API ---
hf_api = HfApi(token=HF_TOKEN)
existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
valid_files = [f for f in existing_files if re.match(VALID_PATTERN, f)]

# --- FILE UPLOADER ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV (`|` delimiter, format: bal_detail_103_yyyy-mm-dd.csv)", 
    type=["csv"], 
    accept_multiple_files=True
)

# --- HANDLE MULTIPLE FILE UPLOADS WITH CLEAN UI ---
if uploaded_files:
    uploaded_success = False
    status_area = st.container()
    progress_area = st.container()

    with progress_area:
        st.info("⏳ Sedang memproses file yang diupload...")
        overall_progress = st.progress(0, text="Menyiapkan upload...")

    for idx, file in enumerate(uploaded_files):
        with status_area.status(f"📤 Mengunggah `{file.name}`...", expanded=True) as file_status:
            original_name = file.name
            match = re.search(r"bal_detail_103_(\d{4}-\d{2}-\d{2})", original_name)
            if not match:
                file_status.error(f"⚠️ Nama file `{original_name}` tidak valid. Lewati.")
                continue
            upload_date = match.group(1)
            cleaned_name = f"bal_detail_103_{upload_date}.csv"

            try:
                df = pd.read_csv(file, delimiter="|")
                df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
                df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()

                if cleaned_name in existing_files:
                    delete_file(
                        path_in_repo=cleaned_name,
                        repo_id=REPO_ID,
                        repo_type="dataset",
                        token=HF_TOKEN
                    )

                upload_file(
                    path_or_fileobj=BytesIO(file.getvalue()),
                    path_in_repo=cleaned_name,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )

                uploaded_success = True
                file_status.success(f"✅ `{cleaned_name}` berhasil diupload & disimpan.")

            except Exception as e:
                file_status.error(f"❌ Gagal memproses `{original_name}`: {e}")

            overall_progress.progress((idx + 1) / len(uploaded_files), text=f"📁 {idx + 1}/{len(uploaded_files)} file selesai")

    progress_area.empty()

    if uploaded_success:
        st.cache_data.clear()
        st.success("✅ Semua upload selesai. Memperbarui data...")

        # 🔄 Reload file list and data
        existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
        valid_files = [f for f in existing_files if re.match(VALID_PATTERN, f)]

# --- LOAD FILES WITH PROGRESS ---
def read_all_data_from_hf_with_progress(file_list, repo_id, token):
    all_data = []
    progress = st.progress(0, text="📥 Memuat data dari Hugging Face...")
    total = len(file_list)

    for i, file_name in enumerate(file_list):
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

        except Exception as e:
            st.warning(f"Gagal memproses `{file_name}`: {e}")

        progress.progress((i + 1) / total, text=f"📥 Memuat file {i + 1} dari {total}...")

    progress.empty()
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame(
        columns=["custcode", "custname", "salesid", "currentbal", "upload_date"]
    )

# --- LOAD DATA ---
df_all = read_all_data_from_hf_with_progress(valid_files, REPO_ID, HF_TOKEN)
if df_all.empty:
    st.warning("⚠️ Tidak ada data yang berhasil dimuat.")
    st.stop()

# --- DELETE SECTION ---
st.sidebar.header("🗑️ Hapus Data")
delete_file_choice = st.sidebar.selectbox("Pilih file untuk dihapus", [""] + valid_files)
if st.sidebar.button("🗑️ Hapus File Ini") and delete_file_choice:
    delete_file(path_in_repo=delete_file_choice, repo_id=REPO_ID, repo_type="dataset", token=HF_TOKEN)
    st.cache_data.clear()
    st.sidebar.success(f"File `{delete_file_choice}` berhasil dihapus. Silakan refresh.")

if st.sidebar.button("🔥 Hapus Semua File"):
    for file in valid_files:
        delete_file(path_in_repo=file, repo_id=REPO_ID, repo_type="dataset", token=HF_TOKEN)
    st.cache_data.clear()
    st.sidebar.success("🚨 Semua file berhasil dihapus dari dataset.")

# --- SIDEBAR FILTER ---
st.sidebar.header("🔎 Filter Data")
salesid_list = ["Semua"] + sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("Pilih SalesID", salesid_list)
df_filtered = df_all if selected_salesid == "Semua" else df_all[df_all["salesid"] == selected_salesid]

# --- DATE RANGE FILTER ---
st.subheader("📅 Pilih Periode Tanggal")
available_dates = sorted(df_filtered["upload_date"].dt.date.unique())
default_start = max(pd.to_datetime(f"{pd.Timestamp.today().year}-01-01").date(), available_dates[0])
default_end = available_dates[-1]

selected_range = st.date_input(
    "Pilih rentang tanggal upload:",
    value=(default_start, default_end),
    min_value=available_dates[0],
    max_value=available_dates[-1]
)

start_date, end_date = selected_range
df_filtered_range = df_filtered[
    (df_filtered["upload_date"].dt.date >= start_date) &
    (df_filtered["upload_date"].dt.date <= end_date)
]

# --- CHART ---
if df_filtered_range.empty:
    st.warning("❌ Tidak ada data dalam rentang tanggal yang dipilih.")
else:
    st.header("📈 Tren Total Piutang per Hari")
    df_trend = (
        df_filtered_range.groupby("upload_date", as_index=False)["currentbal"]
        .sum()
        .sort_values("upload_date")
    )

    fig = px.line(
        df_trend,
        x="upload_date",
        y="currentbal",
        title=f"Total Piutang — Periode {start_date} s.d. {end_date} {'(SalesID: ' + selected_salesid + ')' if selected_salesid != 'Semua' else ''}",
        markers=True,
        labels={"upload_date": "Tanggal", "currentbal": "Total Piutang"}
    )
    fig.update_layout(xaxis_tickformat="%Y-%m-%d")
    fig.update_traces(hovertemplate="Tanggal: %{x|%Y-%m-%d}<br>Total: Rp %{y:,.0f}")
    st.plotly_chart(fig, use_container_width=True)

    # --- DETAIL TANGGAL ---
    st.subheader("📅 Pilih Tanggal untuk Rincian Data")
    tanggal_opsi = sorted(df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d").unique(), reverse=True)
    selected_date = st.selectbox("Tanggal Data", tanggal_opsi)
    df_selected = df_filtered_range[df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d") == selected_date]
    st.markdown("---")

    # --- SUMMARY ---
    st.header("📊 Ringkasan Data")
    total_piutang = df_selected["currentbal"].sum()
    jml_nasabah = df_selected["custcode"].nunique()

    col1, col2 = st.columns(2)
    col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
    col2.metric("👥 Jumlah Nasabah", jml_nasabah)

    # --- TABLE ---
    st.markdown("---")
    st.subheader(f"📋 Tabel Rincian — Tanggal: {selected_date}")
    df_view = df_selected.sort_values("currentbal", ascending=False).reset_index(drop=True)
    df_view["currentbal"] = df_view["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
    st.dataframe(df_view, use_container_width=True)

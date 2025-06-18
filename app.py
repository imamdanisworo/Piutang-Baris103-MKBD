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

if HF_TOKEN is None:
    st.error("❌ HF_TOKEN environment variable is not set.")
    st.stop()

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
            df_all = None  # force refresh after upload
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

# --- SIDEBAR FILTER ---
st.sidebar.header("🔎 Filter Data")
salesid_list = ["Semua"] + sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("Pilih SalesID", salesid_list)
df_filtered = df_all if selected_salesid == "Semua" else df_all[df_all["salesid"] == selected_salesid]

# --- DATE FILTER ---
st.subheader("📅 Pilih Periode Tanggal")
available_dates = sorted(df_filtered["upload_date"].dt.date.unique())
if not available_dates:
    st.warning("Tidak ada tanggal tersedia untuk SalesID ini.")
    st.stop()

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
    st.stop()

st.header("📈 Tren Total Piutang per Hari")
df_trend = df_filtered_range.groupby("upload_date", as_index=False)["currentbal"].sum()
fig = px.line(df_trend, x="upload_date", y="currentbal", markers=True)
fig.update_traces(hovertemplate="Tanggal: %{x|%Y-%m-%d}<br>Total: Rp %{y:,.0f}")
fig.update_layout(title="Total Piutang per Hari", xaxis_title="Tanggal", yaxis_title="Total Piutang")
st.plotly_chart(fig, use_container_width=True)

# --- RINGKASAN PER TANGGAL ---
st.subheader("📅 Pilih Tanggal untuk Rincian Data")
tanggal_opsi = sorted(df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d").unique(), reverse=True)
selected_date = st.selectbox("Tanggal Data", tanggal_opsi)
df_selected = df_filtered_range[df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d") == selected_date]

st.header("📊 Ringkasan Data")
total_piutang = df_selected["currentbal"].sum()
jml_nasabah = df_selected["custcode"].nunique()
col1, col2 = st.columns(2)
col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
col2.metric("👥 Jumlah Nasabah", jml_nasabah)

# --- PIE CHART SALESID ---
df_selected_grouped = df_selected.copy()
df_selected_grouped["salesid_group"] = df_selected_grouped["salesid"].apply(lambda x: "WM" if str(x).startswith("WM-") else x)
salesid_summary = df_selected_grouped.groupby("salesid_group", as_index=False)["currentbal"].sum()

fig2 = px.pie(salesid_summary, names="salesid_group", values="currentbal", hole=0.4)
fig2.update_traces(textinfo="label+percent", hovertemplate="SalesID: %{label}<br>Total: Rp %{value:,.0f}")
fig2.update_layout(title="📊 Distribusi Piutang per SalesID")
st.plotly_chart(fig2, use_container_width=True)

# --- TABEL RINCIAN ---
st.subheader(f"📋 Tabel Rincian — Tanggal: {selected_date}")
df_view = df_selected.sort_values("currentbal", ascending=False).reset_index(drop=True)
df_view["currentbal"] = df_view["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
st.dataframe(df_view.drop(columns=["salesid_group"]), use_container_width=True)

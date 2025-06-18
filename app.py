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

st.title("📤 Upload & Analisa Piutang Nasabah")
st.markdown("---")

# --- HF API ---
hf_api = HfApi(token=HF_TOKEN)

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
            df.columns = df.columns.str.strip().str.lower()

            required_cols = ["custcode", "custname", "salesid", "currentbal"]
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"Kolom wajib tidak lengkap di {file_name}. Ditemukan kolom: {df.columns.tolist()}")

            df = df[required_cols]
            df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
            df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()
            df = df[df["currentbal"] != 0]
            df["upload_date"] = upload_date
            all_data.append(df)

        except Exception as e:
            st.warning(f"Gagal memproses `{file_name}`: {e}")
            continue

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame(
        columns=["custcode", "custname", "salesid", "currentbal", "upload_date"]
    )

# --- INITIALIZE SESSION STATE ---
if "df_all" not in st.session_state:
    existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")
    valid_files = [f for f in existing_files if re.match(VALID_PATTERN, f)]
    st.session_state.df_all = read_all_data_from_hf(valid_files, REPO_ID, HF_TOKEN)

# --- FILE UPLOADER ---
st.header("📁 Upload File CSV Harian")
uploaded_files = st.file_uploader(
    "Upload satu atau beberapa file CSV (`|` delimiter, format: bal_detail_103_yyyy-mm-dd.csv)", 
    type=["csv"], 
    accept_multiple_files=True
)

# --- HANDLE UPLOADS ---
if uploaded_files:
    uploaded_success = False
    status_area = st.container()
    progress_area = st.container()

    with progress_area:
        st.info("⏳ Sedang memproses file yang diupload...")
        overall_progress = st.progress(0, text="Menyiapkan upload...")

    existing_files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")

    for idx, file in enumerate(uploaded_files):
        with status_area.status(f"📤 Mengunggah `{file.name}`...", expanded=True) as file_status:
            match = re.search(r"bal_detail_103_(\d{4}-\d{2}-\d{2})", file.name)
            if not match:
                file_status.error(f"⚠️ Nama file `{file.name}` tidak valid. Lewati.")
                continue

            cleaned_name = f"bal_detail_103_{match.group(1)}.csv"

            try:
                df = pd.read_csv(file, delimiter="|")
                df.columns = df.columns.str.strip().str.lower()

                required_cols = ["custcode", "custname", "salesid", "currentbal"]
                if not all(col in df.columns for col in required_cols):
                    raise ValueError(f"Kolom wajib tidak lengkap di {file.name}. Ditemukan kolom: {df.columns.tolist()}")

                df = df[required_cols]
                df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
                df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()
                df = df[df["currentbal"] != 0]

                buffer = BytesIO()
                df.to_csv(buffer, index=False)
                buffer.seek(0)

                if cleaned_name in existing_files:
                    delete_file(
                        path_in_repo=cleaned_name,
                        repo_id=REPO_ID,
                        repo_type="dataset",
                        token=HF_TOKEN
                    )

                upload_file(
                    path_or_fileobj=buffer,
                    path_in_repo=cleaned_name,
                    repo_id=REPO_ID,
                    repo_type="dataset",
                    token=HF_TOKEN
                )
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
            st.session_state.df_all = read_all_data_from_hf(valid_files, REPO_ID, HF_TOKEN)

# --- USE LOADED DATA ---
df_all = st.session_state.df_all
if df_all.empty:
    st.warning("⚠️ Tidak ada data yang berhasil dimuat.")
    st.stop()

# --- FILTER BY SALESID ---
st.sidebar.header("🔎 Filter Data")
salesid_list = ["Semua"] + sorted(df_all["salesid"].unique())
selected_salesid = st.sidebar.selectbox("Pilih SalesID", salesid_list)
df_filtered = df_all if selected_salesid == "Semua" else df_all[df_all["salesid"] == selected_salesid]

# --- FILTER BY DATE ---
st.subheader("📅 Pilih Periode Tanggal")
available_dates = sorted(df_filtered["upload_date"].dt.date.unique())
default_start = max(pd.to_datetime(f"{pd.Timestamp.today().year}-01-01").date(), available_dates[0])
default_end = available_dates[-1]
selected_range = st.date_input("Pilih rentang tanggal:", (default_start, default_end), min_value=available_dates[0], max_value=available_dates[-1])
start_date, end_date = selected_range
df_filtered_range = df_filtered[(df_filtered["upload_date"].dt.date >= start_date) & (df_filtered["upload_date"].dt.date <= end_date)]

# --- TREND CHART ---
if df_filtered_range.empty:
    st.warning("❌ Tidak ada data dalam rentang tanggal yang dipilih.")
else:
    st.header("📈 Tren Total Piutang per Hari")
    df_trend = df_filtered_range.groupby("upload_date", as_index=False)["currentbal"].sum()
    fig = px.line(df_trend, x="upload_date", y="currentbal", markers=True,
                  title=f"Total Piutang: {start_date} s.d. {end_date}",
                  labels={"upload_date": "Tanggal", "currentbal": "Total Piutang"})
    fig.update_layout(xaxis_tickformat="%Y-%m-%d")
    fig.update_traces(hovertemplate="Tanggal: %{x|%Y-%m-%d}<br>Total: Rp %{y:,.0f}")
    st.plotly_chart(fig, use_container_width=True)

    # --- DETAIL TANGGAL ---
    st.subheader("📅 Pilih Tanggal untuk Rincian")
    tanggal_opsi = sorted(df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d").unique(), reverse=True)
    selected_date = st.selectbox("Tanggal Data", tanggal_opsi)
    df_selected = df_filtered_range[df_filtered_range["upload_date"].dt.strftime("%Y-%m-%d") == selected_date]

    # --- RINGKASAN ---
    st.header("📊 Ringkasan Data")
    total_piutang = df_selected["currentbal"].sum()
    jml_nasabah = df_selected["custcode"].nunique()
    col1, col2 = st.columns(2)
    col1.metric("💰 Total Piutang", f"Rp {total_piutang:,.0f}")
    col2.metric("👥 Jumlah Nasabah", jml_nasabah)

    # --- PIE CHART BY SALESID GROUP (WM) ---
    df_selected["salesid_group"] = df_selected["salesid"].apply(lambda x: "WM" if str(x).startswith("WM-") else x)
    pie_data = df_selected.groupby("salesid_group", as_index=False)["currentbal"].sum().sort_values("currentbal", ascending=False)
    fig_pie = px.pie(pie_data, names="salesid_group", values="currentbal", title="Distribusi Piutang per SalesID", hole=0.4)
    fig_pie.update_traces(textinfo="label+percent", hovertemplate="SalesID: %{label}<br>Total: Rp %{value:,.0f}")
    st.plotly_chart(fig_pie, use_container_width=True)

    # --- TABLE RINCIAN ---
    st.markdown("---")
    st.subheader(f"📋 Tabel Rincian — Tanggal: {selected_date}")
    df_view = df_selected.sort_values("currentbal", ascending=False).reset_index(drop=True)
    df_view["currentbal"] = df_view["currentbal"].apply(lambda x: f"Rp {x:,.0f}")
    st.dataframe(df_view, use_container_width=True)

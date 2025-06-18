from nicegui import ui
import pandas as pd
import re
from huggingface_hub import HfApi, upload_file, delete_file, hf_hub_download
from io import BytesIO
import os
from datetime import datetime

# --- CONFIG ---
HF_TOKEN = os.getenv("HF_TOKEN")
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"
VALID_PATTERN = r"bal_detail_103_\d{4}-\d{2}-\d{2}\.csv"
hf_api = HfApi(token=HF_TOKEN)

# --- STATE ---
all_data = pd.DataFrame()

# --- FUNCTIONS ---
def refresh_file_list():
    return [f for f in hf_api.list_repo_files(REPO_ID, repo_type="dataset") if re.match(VALID_PATTERN, f)]

def process_file(file_bytes, filename):
    df = pd.read_csv(BytesIO(file_bytes), delimiter="|")
    df["currentbal"] = pd.to_numeric(df["currentbal"], errors="coerce").fillna(0)
    df = df.groupby(["custcode", "custname", "salesid"], as_index=False)["currentbal"].sum()
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if date_match:
        df["upload_date"] = pd.to_datetime(date_match.group(1))
    return df

def load_all_data():
    dfs = []
    for fname in refresh_file_list():
        try:
            path = hf_hub_download(REPO_ID, fname, repo_type="dataset", token=HF_TOKEN, local_dir="/tmp")
            with open(path, "rb") as f:
                df = process_file(f.read(), fname)
                dfs.append(df)
        except Exception as e:
            print(f"Error loading {fname}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def upload_and_replace(file):
    filename = file.name
    match = re.search(r"bal_detail_103_(\d{4}-\d{2}-\d{2})", filename)
    if not match:
        ui.notify(f"Nama file {filename} tidak valid")
        return
    cleaned_name = f"bal_detail_103_{match.group(1)}.csv"
    existing_files = refresh_file_list()
    if cleaned_name in existing_files:
        delete_file(cleaned_name, REPO_ID, repo_type="dataset", token=HF_TOKEN)
    upload_file(path_or_fileobj=BytesIO(file.content.read()),
                path_in_repo=cleaned_name,
                repo_id=REPO_ID,
                repo_type="dataset",
                token=HF_TOKEN)
    ui.notify(f"✅ File {cleaned_name} berhasil diupload dan disimpan.")

# --- UI ---
ui.label("📊 Ringkasan Piutang Nasabah").classes("text-2xl font-bold")

with ui.row():
    with ui.column():
        ui.label("📁 Upload File CSV (Format: bal_detail_103_yyyy-mm-dd.csv)")
        upload = ui.upload(on_upload=upload_and_replace, auto_upload=True, label="Pilih File")
        upload.tooltip("Format file wajib sesuai dan delimiter '|'")

        def delete_all():
            for f in refresh_file_list():
                delete_file(f, REPO_ID, repo_type="dataset", token=HF_TOKEN)
            ui.notify("🗑️ Semua file berhasil dihapus")

        ui.button("🔥 Hapus Semua File", on_click=delete_all, color="red")

    with ui.column():
        def reload():
            global all_data
            ui.notify("🔄 Memuat ulang data...")
            all_data = load_all_data()
            ui.notify(f"📈 {len(all_data)} baris data dimuat.")
        ui.button("🔄 Muat Ulang Data", on_click=reload)

@ui.page("/")
def main_page():
    reload()
    if all_data.empty:
        ui.label("⚠️ Tidak ada data yang tersedia.")
    else:
        latest_date = all_data["upload_date"].max().date()
        start_date = datetime(latest_date.year, 1, 1).date()
        with ui.row():
            date_range = ui.date_range("Pilih Periode", start_date=start_date, end_date=latest_date)

        def update_chart():
            if not date_range.value:
                return
            start, end = date_range.value
            df_filtered = all_data[(all_data["upload_date"].dt.date >= start) & (all_data["upload_date"].dt.date <= end)]
            if df_filtered.empty:
                ui.notify("⚠️ Tidak ada data dalam rentang tanggal yang dipilih.")
                return
            df_trend = df_filtered.groupby("upload_date", as_index=False)["currentbal"].sum()
            ui.line_plot(df_trend, x="upload_date", y="currentbal", title="Tren Piutang", markers=True)

        ui.button("📊 Tampilkan Grafik", on_click=update_chart)

# --- FINAL RUN ---
if __name__ == "__main__":
    ui.run(title="Ringkasan Piutang", dark=False, reload=False)

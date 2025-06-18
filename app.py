from huggingface_hub import HfApi

HF_TOKEN = "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"
REPO_ID = "imamdanisworo/Piutang-Baris103-MKBD"

hf_api = HfApi(token=HF_TOKEN)

# List all files in the repo
files = hf_api.list_repo_files(REPO_ID, repo_type="dataset")

# Delete each file
for file in files:
    try:
        hf_api.delete_file(path_in_repo=file, repo_id=REPO_ID, repo_type="dataset")
        print(f"✅ Deleted: {file}")
    except Exception as e:
        print(f"❌ Failed to delete {file}: {e}")

import os
import time
from pathlib import Path
from cryptography.fernet import Fernet
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

FERNET_KEY = b"PVLAZViSXqvafbm3ugQpJtrmDMjSC339eh6fOs7VgYM="
fernet = Fernet(FERNET_KEY)

CLIENT_FILE = Path.cwd() / "client_secrets.json"
CRED_ENC = Path.cwd() / "credentials.enc"


def get_drive():
    gauth = GoogleAuth()
    gauth.LoadClientConfigFile(str(CLIENT_FILE))
    
    if CRED_ENC.exists():
        decrypted = fernet.decrypt(CRED_ENC.read_bytes())
        temp_path = CRED_ENC.with_suffix(".json")
        temp_path.write_bytes(decrypted)
        gauth.LoadCredentialsFile(str(temp_path))
        temp_path.unlink()  # remove immediately
    else:
        gauth.credentials = None

    if gauth.credentials is None:
        print("First time authentication...")
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        print("Refreshing token...")
        gauth.Refresh()
    else:
        gauth.Authorize()
    
    temp_path = CRED_ENC.with_suffix(".json")
    gauth.SaveCredentialsFile(str(temp_path))
    encrypted = fernet.encrypt(temp_path.read_bytes())
    CRED_ENC.write_bytes(encrypted)
    temp_path.unlink()

    return GoogleDrive(gauth)

def get_or_create_drive_folder(drive, parent_id, folder_name):
    """Find or create a subfolder under the given parent folder."""
    try:
        existing_folders = drive.ListFile({
            "q": f"'{parent_id}' in parents and title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        }).GetList()
    except Exception:
        existing_folders = []

    if existing_folders:
        return existing_folders[0]["id"]

    # Create new folder
    folder_metadata = {
        "title": folder_name,
        "parents": [{"id": parent_id}],
        "mimeType": "application/vnd.google-apps.folder"
    }
    new_folder = drive.CreateFile(folder_metadata)
    new_folder.Upload()
    print(f"Created folder on Drive: {folder_name}")
    return new_folder["id"]


def run_upload(folder, drive_folder_id):
    """
    Upload all files in a folder (and its subfolders) to Google Drive.
    Folder structure on Drive mirrors the local one.
    Retries uploads for up to 5 minutes per file.
    """
    drive = get_drive()

    print(f"Starting recursive upload from: {folder}")

    for root, dirs, files in os.walk(folder):
        rel_path = os.path.relpath(root, folder)
        rel_path = "" if rel_path == "." else rel_path

        # Ensure subfolder structure exists on Drive
        current_folder_id = drive_folder_id
        if rel_path:
            for part in rel_path.split(os.sep):
                current_folder_id = get_or_create_drive_folder(drive, current_folder_id, part)

        # Upload all files in this folder
        for filename in files:
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue

            # Skip if file already exists on Drive
            try:
                existing_files = drive.ListFile({
                    'q': f"'{current_folder_id}' in parents and title='{filename}' and trashed=false"
                }).GetList()
            except Exception:
                existing_files = []

            if existing_files:
                print(f"Melewati file '{filename}' — sudah ada di '{rel_path or '(root)'}'")
                continue

            # Retry upload for up to 5 minutes
            start_time = time.time()
            while True:
                try:
                    gfile = drive.CreateFile({
                        'title': filename,
                        'parents': [{'id': current_folder_id}]
                    })
                    gfile.SetContentFile(file_path)
                    gfile.Upload()
                    print(f"Uploaded: {filename} -> {rel_path or '(root)'}")
                    break

                except Exception as e:
                    elapsed = time.time() - start_time
                    if elapsed >= 300:  # 5 minutes
                        print(f"Upload failed {filename} after 5 minutes. Error: {e}")
                        raise ConnectionError("Upload stopped, bad connection.")
                    else:
                        print(f"Failed to upload '{filename}', trying again in 10 seconds... ({int(elapsed)}s)")
                        time.sleep(10)

    print("All Upload Complete")
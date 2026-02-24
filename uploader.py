import os, sys
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import socket
from cryptography.fernet import Fernet
import tempfile
import time
from pathlib import Path

APP_NAME = "TerraLog"

import os
import tempfile
from cryptography.fernet import Fernet
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

def get_drive():
    gauth = GoogleAuth()
    client_file = Path.cwd() / "client_secrets.json"
    gauth.LoadClientConfigFile(client_file)
    CRED_ENC = Path.cwd() / "credentials.enc"
    FERNET_KEY = b"jptpGskWrHdUq3Vvi8DOw3pQQDBCtOfCrpNC80DwI7Q="
    #New fernet = jptpGskWrHdUq3Vvi8DOw3pQQDBCtOfCrpNC80DwI7Q=
    #Default fernet = DZR2E60GV-cn0XWTuX61QX9JyTy8ZNp5qXHlHWtg614=
    fernet = Fernet(FERNET_KEY)

    # --- Step 1: Decrypt credentials.enc into memory ---
    if not os.path.exists(CRED_ENC):
        raise FileNotFoundError("Encrypted credentials.enc not found")

    with open(CRED_ENC, "rb") as f:
        encrypted_data = f.read()
    decrypted_data = fernet.decrypt(encrypted_data)

    # --- Step 2: Write decrypted credentials to a temporary file ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(decrypted_data)
        tmp.flush()
        temp_path = tmp.name

    try:
        # --- Step 3: Load credentials safely ---
        gauth.LoadCredentialsFile(temp_path)

        if gauth.credentials is None:
            # First-time setup (requires internet)
            print("Authenticating Google Drive")
            gauth.LocalWebserverAuth()
        else:
            try:
                if gauth.access_token_expired:
                    # Try refreshing token (may fail offline)
                    gauth.Refresh()
                else:
                    gauth.Authorize()
            except Exception as e:
                print(f"Error: {e}")
                # Still use existing credentials (will fail on upload if offline)
                try:
                    gauth.Authorize()
                except Exception:
                    print("Authorize failed!")

        # --- Step 4: Save (and re-encrypt) credentials back to .enc ---
        with tempfile.NamedTemporaryFile(delete=False) as tmp_out:
            gauth.SaveCredentialsFile(tmp_out.name)
            tmp_out.flush()
            with open(tmp_out.name, "rb") as f:
                new_data = f.read()
            enc_new = fernet.encrypt(new_data)
            with open(CRED_ENC, "wb") as f:
                f.write(enc_new)

    finally:
        # Always remove decrypted temp file
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass

    # --- Step 5: Return Drive instance ---
    return GoogleDrive(gauth)


def check_internet(host="208.67.222.222", port=53, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
    
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
                print(f"File skipped'{filename}' — Already exist in '{rel_path or '(root)'}'")
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
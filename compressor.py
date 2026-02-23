import os
import csv
import struct

# Assign IDs for each message type
TYPE_MAP = {
    "GPS": 1,
    "POS": 2,
    "RCOU": 3,
    "BAT1": 4,
    "BAT2": 5,
    "MSG": 6,
    "CMD": 7,
    "MODE": 8,
    "CTUN": 9,
}
ID_MAP = {v: k for k, v in TYPE_MAP.items()}

def csv_to_bin(csv_file, bin_file, schemas):
    with open(csv_file, newline='') as f_in, open(bin_file, "wb") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            mtype = row["mavpackettype"]
            if mtype not in schemas:
                continue
            schema = schemas[mtype]

            # Write 1 byte type ID first
            f_out.write(struct.pack("B", TYPE_MAP[mtype]))

            # Pack fields
            fmt = "<" + "".join(t for _,t in schema)
            values = []
            for name, t in schema:
                val = row.get(name, "")
                if val == "" or val is None:
                    val = 0
                if "s" in t:  # handle fixed-length string (e.g. "12s")
                    # Encode string to bytes and pad/truncate to exact length
                    strlen = int(t[:-1])  # e.g. "12s" → 12
                    val_bytes = str(val).encode("utf-8")[:strlen]
                    val_bytes = val_bytes.ljust(strlen, b'\x00')
                    values.append(val_bytes)
                elif t in ("i","q"):
                    values.append(int(float(val)))
                elif t in ("f","d"):
                    values.append(float(val))
                else:
                    raise ValueError(f"Unsupported type {t} in schema")
            f_out.write(struct.pack(fmt, *values))


def bin_to_csv(bin_file, csv_file, schemas):
    with open(bin_file,"rb") as f_in, open(csv_file,"w",newline="") as f_out:
        writer = csv.writer(f_out)
        # Collect all headers
        all_headers = ["mavpackettype"]
        for s in schemas.values():
            for name,_ in s:
                if name not in all_headers:
                    all_headers.append(name)
        writer.writerow(all_headers)

        while True:
            type_b = f_in.read(1)
            if not type_b:
                break
            mtype = ID_MAP[struct.unpack("B", type_b)[0]]
            schema = schemas[mtype]

            fmt = "<" + "".join(t for _,t in schema)
            size = struct.calcsize(fmt)
            chunk = f_in.read(size)
            values = struct.unpack(fmt, chunk)

            row_dict = {"mavpackettype": mtype}
            for (name,t), val in zip(schema, values):
                if "s" in t:  # decode fixed-length string
                    val = val.decode("utf-8").rstrip("\x00")
                row_dict[name] = val
            row = [row_dict.get(h,"") for h in all_headers]
            writer.writerow(row)


# === Folder processors ===

def process_csv_folder(input_folder, output_folder, schemas):
    """
    Recursively convert all CSV files under `input_folder` to BIN files,
    preserving the same subfolder structure in `output_folder`.
    """
    input_folder = os.path.abspath(input_folder)
    output_folder = os.path.abspath(output_folder)

    for root, dirs, files in os.walk(input_folder):
        # Compute relative subpath from the root of input_folder
        rel_path = os.path.relpath(root, input_folder)
        current_out = os.path.join(output_folder, rel_path)

        # Make sure subfolder exists
        os.makedirs(current_out, exist_ok=True)

        for fname in files:
            if not fname.lower().endswith(".csv"):
                continue

            csv_path = os.path.join(root, fname)
            bin_name = os.path.splitext(fname)[0] + ".bin"
            bin_path = os.path.join(current_out, bin_name)

            print(f"[Sukses mengkonversi CSV->BIN] {csv_path} -> {bin_path}")
            csv_to_bin(csv_path, bin_path, schemas)
            
def new_process_csv_folder(input_folder, output_folder, schemas):
    csv_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".csv")]
    for filename in csv_files:
        bin_path = os.path.join(input_folder, filename)
        print(bin_path)




def process_bin_folder(input_folder, output_folder, schemas, log=None):
    """Convert all BIN files in a folder to CSV, same base name."""
    os.makedirs(output_folder, exist_ok=True)
    for fname in os.listdir(input_folder):
        if fname.lower().endswith(".bin"):
            bin_path = os.path.join(input_folder, fname)
            csv_name = os.path.splitext(fname)[0] + ".csv"
            csv_path = os.path.join(output_folder, csv_name)
            bin_to_csv(bin_path, csv_path, schemas)

            print(f"[Sukses mengkonversi BIN->CSV] {fname} -> {csv_name}")
            
def delete_csv_files(folder):
    for fname in os.listdir(folder):
        if fname.lower().endswith(".csv"):
            fpath = os.path.join(folder, fname)
            try:
                os.remove(fpath)
                print(f" Terdelete {fname}")
            except Exception as e:
                print(f"Gagal mendelete {fname}: {e}")
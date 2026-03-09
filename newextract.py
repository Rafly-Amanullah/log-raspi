import os
import pandas as pd
from pymavlink import mavutil
import re
from datetime import datetime, timedelta, timezone
import time


def downsample_df(df: pd.DataFrame, per_sec: int) -> pd.DataFrame:
    if df.empty or "TimeUS" not in df.columns:
        return df

    df = df.copy()
    df["sec"] = (df["TimeUS"] // 1_000_000).astype(int)

    df = (
        df.groupby("sec", group_keys=False)
        .apply(lambda g: g.iloc[:per_sec])
        .reset_index(drop=True)
    )

    return df.drop(columns="sec", errors="ignore")


def extract(folder_path: str, tz: int, downsample_val: int):

    bin_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".bin")]
    if not bin_files:
        raise FileNotFoundError("No .bin file found")

    results = []

    for filename in bin_files:
        bin_path = os.path.join(folder_path, filename)

        mav = mavutil.mavlink_connection(bin_path, robust_parsing=True)

        buffers = {
            "GPS": [],
            "POS": [],
            "RCOU": [],
            "BAT": [],
            "CMD": [],
            "MSG": [],
            "MODE": [],
            "CTUN": [],
        }

        sysid_thismav = None
        gps_datetime = None

        try:
            while True:
                msg = mav.recv_match(blocking=False)
                if msg is None:
                    break

                mtype = msg.get_type()
                dct = msg.to_dict()

                # ---------- SYSID ----------
                if mtype == "PARM" and sysid_thismav is None:
                    if dct.get("Name") == "SYSID_THISMAV":
                        sysid_thismav = int(dct.get("Value"))

                # ---------- GPS datetime ----------
                if mtype == "GPS" and gps_datetime is None:
                    if "GWk" in dct and "GMS" in dct:
                        gps_epoch = datetime(1980, 1, 6, tzinfo=timezone.utc)
                        utc_time = gps_epoch + timedelta(
                            weeks=dct["GWk"],
                            milliseconds=dct["GMS"],
                        )
                        gps_datetime = utc_time.astimezone(
                            timezone(timedelta(hours=tz))
                        )
                        date_str = gps_datetime.strftime("%Y-%m-%d")
                        date_file = gps_datetime.strftime("%d%m%Y")

                # ---------- MSG filter ----------
                if mtype == "MSG":
                    text = dct.get("Message", "")

                    m = re.search(r"Mission:\s*(\d+)\s+(RepeatServo)", text)
                    if m:
                        dct["Mission"] = int(m.group(1))
                        dct["Action"] = m.group(2)
                    else:
                        continue

                if mtype in buffers:
                    buffers[mtype].append(dct)

        finally:
            mav.close()

        # ---------- DataFrames ----------
        dfs = {k: pd.DataFrame(v) for k, v in buffers.items()}

        if not dfs["CMD"].empty and "Prm3" in dfs["CMD"].columns:
            dfs["CMD"] = dfs["CMD"][dfs["CMD"]["Prm3"] == 1]

        # ---------- Keep columns (from old script) ----------
        keep_cols = {
            "GPS": ["mavpackettype", "TimeUS", "Status", "GMS", "GWk", "Spd"],
            "POS": ["mavpackettype", "TimeUS", "Lat", "Lng", "RelHomeAlt"],
            "RCOU": ["mavpackettype", "TimeUS", "C11"],
            "BAT": ["mavpackettype", "Inst", "TimeUS", "Curr"],
            "MSG": ["mavpackettype", "TimeUS", "Mission", "Action"],
            "CMD": ["mavpackettype", "TimeUS", "Prm3"],
            "CTUN": ["mavpackettype", "TimeUS", "ThO"],
        }

        # apply filtering
        for key, df in dfs.items():
            if df.empty:
                continue
            cols = keep_cols.get(key)
            if cols:
                dfs[key] = df[[c for c in cols if c in df.columns]]

        # ---------- BAT split ----------
        bat_outputs = []
        if not dfs["BAT"].empty and "Inst" in dfs["BAT"]:
            for inst in (0, 1):
                sub = dfs["BAT"][dfs["BAT"]["Inst"] == inst].copy()
                if not sub.empty:
                    sub["mavpackettype"] = f"BAT{inst+1}"
                    sub = sub.drop(columns=["Inst"])
                    sub = downsample_df(sub, downsample_val)
                    bat_outputs.append(sub)

        # ---------- POS dynamic downsample ----------
        pos_df = dfs["POS"]
        rcou_df = dfs["RCOU"]

        if not pos_df.empty and not rcou_df.empty and "C11" in rcou_df:
            pos_df = pd.merge_asof(
                pos_df.sort_values("TimeUS"),
                rcou_df[["TimeUS", "C11"]].sort_values("TimeUS"),
                on="TimeUS",
                direction="nearest",
            )

            pos_high = pos_df[pos_df["C11"] > 1800]
            pos_low = pos_df[pos_df["C11"] <= 1800]

            pos_low = downsample_df(pos_low, downsample_val)

            pos_df = pd.concat([pos_high, pos_low]).sort_values("TimeUS")
            pos_df = pos_df.drop(columns="C11", errors="ignore")

        else:
            pos_df = downsample_df(pos_df, downsample_val)

        # RCOU conditional downsample
        if not rcou_df.empty and "C11" in rcou_df:
            rcou_high = rcou_df[rcou_df["C11"] > 1800]
            rcou_low = rcou_df[rcou_df["C11"] <= 1800]
            rcou_low = downsample_df(rcou_low, downsample_val)
            rcou_df = pd.concat([rcou_high, rcou_low]).sort_values("TimeUS")

        # Downsample others
        other_types = ["GPS", "MSG", "MODE", "CTUN"]
        others = [
            downsample_df(dfs[t], downsample_val)
            for t in other_types
            if not dfs[t].empty
        ]
        #Keep whole CMD
        if not dfs["CMD"].empty:
            others.append(dfs["CMD"])

        merged_parts = others + bat_outputs
        if not rcou_df.empty:
            merged_parts.append(rcou_df)
        if not pos_df.empty:
            merged_parts.append(pos_df)

        merged = pd.concat(merged_parts, ignore_index=True) if merged_parts else pd.DataFrame()
        # ---------- Enforce column order (match old CSV format) ----------
        final_cols = [
            "mavpackettype",
            "TimeUS",
            "Status",
            "GMS",
            "GWk",
            "Spd",
            "Curr",
            "Prm3",
            "Mission",
            "Action",
            "Mode",
            "ModeNum",
            "Rsn",
            "ThO",
            "C11",
            "Lat",
            "Lng",
            "RelHomeAlt",
        ]

        if not merged.empty:
            merged = merged.reindex(columns=final_cols)

        results.append(
            {
                "file": filename,
                "sysid": sysid_thismav,
                "gps_time": date_str,
                "file_time": date_file,
                "data": merged,
            }
        )
    return results
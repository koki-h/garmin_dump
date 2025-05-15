#!/usr/bin/env python3
"""
Usage
------
python3 download_bp.py 2025-05-01 2025-05-10 bp.csv

引数
  1: 開始日 (YYYY-MM-DD)
  2: 終了日 (YYYY-MM-DD)   ※含む
  3: 出力CSVファイル名     ※省略時は blood_pressure.csv
"""

import sys, csv, json, datetime, os, time
from garminconnect import Garmin
from garth.exc import GarthHTTPError
from dateutil import parser as dtparse   # pip install python-dateutil

# ==== 設定 ====
CREDENTIAL_FILE = "credentials.json"
TOKENSTORE      = os.getenv("GARMINTOKENS", os.getcwd())   # 既存と同じ場所
# ===============

def init_client():
    with open(CREDENTIAL_FILE) as f:
        creds = json.load(f)
    email, password = creds["email"], creds["password"]

    cli = Garmin()
    try:
        cli.login(TOKENSTORE)
    except (FileNotFoundError, GarthHTTPError):
        cli = Garmin(email, password)
        cli.login()
        cli.garth.dump(TOKENSTORE)
    return cli

def daterange(d1, d2):
    cur = d1
    one = datetime.timedelta(days=1)
    while cur <= d2:
        yield cur
        cur += one

# ——————— main ———————
if len(sys.argv) < 3:
    print("Usage: download_bp.py YYYY-MM-DD YYYY-MM-DD [out.csv]")
    sys.exit(1)

d_start = datetime.date.fromisoformat(sys.argv[1])
d_end   = datetime.date.fromisoformat(sys.argv[2])
outfile = sys.argv[3] if len(sys.argv) > 3 else "blood_pressure_first.csv"

g = init_client()
rows = []

for day in daterange(d_start, d_end):
    resp = g.get_blood_pressure(day.isoformat())
    # すべての measurements を 1 リストに集約
    measures = []
    for summ in resp.get("measurementSummaries", []):
        measures.extend(summ.get("measurements", []))

    if not measures:          # その日データなし
        continue

    # measurementTimestampLocal を datetime にして最古を選択
    first = min(
        measures,
        key=lambda m: dtparse.isoparse(m["measurementTimestampLocal"])
    )

    rows.append([
        day.isoformat(),
        dtparse.isoparse(first["measurementTimestampLocal"]),
        first.get("systolic"),
        first.get("diastolic"),
        first.get("pulse")
    ])

    time.sleep(0.3)

# CSV 出力
with open(outfile, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["date", "timestamp_local", "systolic", "diastolic", "pulse"])
    writer.writerows(rows)

print(f"{len(rows)} days exported to {outfile}")

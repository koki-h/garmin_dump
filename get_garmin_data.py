#!/usr/bin/env python3
import datetime
import json
import os
import time
from garminconnect import Garmin
from garth.exc import GarthHTTPError

# --- 認証設定 ---
CREDENTIAL_FILE = "credentials.json"
# トークン保存ディレクトリ（環境変数 GARMINTOKENS 指定可）
TOKENSTORE = os.getenv("GARMINTOKENS", os.getcwd())

def init_client():
    # credentials.json から読み込み
    try:
        with open(CREDENTIAL_FILE, "r") as f:
            creds = json.load(f)
        email = creds["email"]
        password = creds["password"]
    except Exception:
        raise Exception("credentials.json の読み込みに失敗しました。")

    client = Garmin()
    # まずトークンでログインを試行
    try:
        client.login(TOKENSTORE)
#        print("トークンログインに成功しました。")
    except (FileNotFoundError, GarthHTTPError):
        # トークンログイン失败時はパスワードログイン
#        print("トークンログイン失敗 → パスワード認証を実施します。")
        client = Garmin(email, password)
        client.login()
        # 新しいトークンを保存
        client.garth.dump(TOKENSTORE)
#        print(f"新しいトークンを '{TOKENSTORE}' に保存しました。")
    return client

client = init_client()

# --- 日付設定 ---
# 引数で日付を指定する場合
if len(os.sys.argv) > 1:
    try:
        date_str = os.sys.argv[1]
        today = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print("日付の形式が不正です。YYYY-MM-DD 形式で指定してください。")
        exit(1)
# 引数がない場合は今日の日付を使用
else:
    today = datetime.date.today()

yesterday = today - datetime.timedelta(days=1)

# --- 生データ取得 ---
sleep_raw = client.get_sleep_data(today)
bb_y = client.get_body_battery(yesterday)
stress_y = client.get_stress_data(yesterday)
hr_y     = client.get_heart_rates(yesterday)
hrv_raw    = client.get_hrv_data(today)

# --- 配列データを辞書リストに変換 ---
def convert_array(array, fields):
    out = []
    for row in array:
        if isinstance(row, dict):
            out.append(row)
        elif isinstance(row, list):
            d = {}
            for i, key in enumerate(fields):
                if i < len(row):
                    d[key] = row[i]
            out.append(d)
    return out

# Body Battery の値配列
bb_raw = []
if bb_y and isinstance(bb_y, list):
    bb_raw = convert_array(
        bb_y[0].get("bodyBatteryValuesArray", []),
        ["timestamp", "value"]
    )

# Stress の値配列
stress_raw_list = convert_array(
    stress_y.get("stressValuesArray", []),
    ["timestamp", "stressLevel"]
)

# Heart Rate の値配列
hr_raw_list = convert_array(
    hr_y.get("heartRateValues", []),
    ["timestamp", "heartRate"]
)

# HRV の値配列
hrv_raw_list = convert_array(
    hrv_raw.get("hrvReadings", []),
    ["readingTimeGMT", "hrvValue"]
)

# タイムスタンプを統一フォーマット（UTC ISO8601）に変換するヘルパー
def parse_ts(value):
    # ミリ秒エポックとして渡された場合
    if isinstance(value, (int, float)):
        return datetime.datetime.utcfromtimestamp(value / 1000).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ISO文字列として渡された場合
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                # datetime.datetime.strptime を呼び出す
                dt = datetime.datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
    # それ以外はそのまま返す
    return value

# 再帰的にデータを走査して時刻フィールドを正規化
def normalize(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            key_lower = k.lower()
            # キーに時間を含む可能性が高い場合に変換
            if any(term in key_lower for term in ['timestamp', 'time', 'startgmt', 'endgmt', 'readingtime']):
                new_obj[k] = parse_ts(v)
            else:
                new_obj[k] = normalize(v)
        return new_obj
    elif isinstance(obj, list):
        return [normalize(item) for item in obj]
    else:
        return obj

# --- 結果を JSON 出力 ---
raw_data = {
    "date": today.isoformat(),
    "sleep_raw": sleep_raw,                 # dailySleepDTO や sleepLevels 等を含む
    "bb_raw": bb_raw,                       # Body Battery の時系列
    "stress_raw": stress_raw_list,         # Stress の時系列
    "hr_raw": hr_raw_list,                  # Heart Rate の時系列
    "hrv_raw": hrv_raw_list,                # HRV の時系列
}

output = normalize(raw_data)
print(json.dumps(output, indent=2, ensure_ascii=False))

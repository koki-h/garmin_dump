#!/usr/bin/env python3
import sys, json, datetime, gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any
from typing import Optional, Union

from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

KEY_FILE    = './gsheet_key.json'
SHEET_URL   = 'https://docs.google.com/spreadsheets/d/1im_fLOL462h4z9R2XVYbjWS4dq6dL6wePD9N--eAB3Q'

def to_jst(timestr: Optional[Union[str, int, float, datetime]]) -> Optional[datetime]:
    if timestr is None or timestr == '':
        return None

    # 既に datetime オブジェクトならそのまま使う
    if isinstance(timestr, datetime):
        dt = timestr

    # 数値なら UNIX エポックとして解釈
    elif isinstance(timestr, (int, float)):
        dt = datetime.fromtimestamp(float(timestr), tz=timezone.utc)

    # 文字列（ISO-8601）をパース
    elif isinstance(timestr, str):
        # 末尾 'Z' → '+00:00' に置換（Python 3.10 以下対策）
        if timestr.endswith('Z'):
            timestr = timestr[:-1] + '+00:00'
        dt = datetime.fromisoformat(timestr)

    else:
        raise TypeError(f"Unsupported type for timestr: {type(timestr)}")

    # タイムゾーンが無ければ UTC とみなす
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # JST へ変換して返却
    return dt.astimezone(JST)

def parse_entries(
    raw: List[Dict[str, Any]],
    time_key: str,
    val_key: str
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []

    for e in raw:
        # ts は time_key があればそちらを、なければ 'timestamp' を採用
        ts = e.get(time_key) or e.get('timestamp')
        val = e.get(val_key)

        # 値が負の場合は 0 に補正
        if val is not None and val < 0:
            val = 0

        # タイムスタンプまたは値が欠けているならスキップ
        if ts is None or val is None:
            continue

        # JST へ変換
        t = to_jst(ts)

        entries.append({'time': t, 'value': val})

    return entries

def recalc_min_max(entries: List[Dict[str, any]]) -> Dict[str, Optional[Dict[str, any]]]:
    """
    entries から前日以前のデータを抽出し、最小値と最大値を持つエントリを返す

    Parameters
    ----------
    entries : List[Dict]
        各要素が {'time': datetime, 'value': 数値} を含むリスト

    Returns
    -------
    Dict[str, Optional[Dict]]
        {'min': {...}, 'max': {...}} 形式の辞書。該当データがなければ None を返す。
    """
    if not entries:
        return {'min': None, 'max': None}

    # @today に相当する変数を参照（ここでは global 変数 today）
    filtered = [e for e in entries]

    if not filtered:
        return {'min': None, 'max': None}

    min_e = min(filtered, key=lambda e: e['value'])
    max_e = max(filtered, key=lambda e: e['value'])

    return {
        'min': {'time': min_e['time'], 'value': min_e['value']},
        'max': {'time': max_e['time'], 'value': max_e['value']},
    }

def main(json_path):
    # ➊ 読み込む
    with open(json_path) as f:

        # data['date'] が "2025-05-06" のような日付文字列（ISO 形式）であると仮定
        data = json.load(f)
        today = datetime.fromisoformat(data['date'])
        sleep_raw = data['sleep_raw']
        dto = sleep_raw['dailySleepDTO']
        sleep_start = to_jst(dto['sleepStartTimestampGMT'])
        sleep_end   = to_jst(dto['sleepEndTimestampGMT'])
        deep_minutes = dto['deepSleepSeconds'] / 60 if 'deepSleepSeconds' in dto else 0
        light_minutes = dto['lightSleepSeconds'] / 60 if 'lightSleepSeconds' in dto else 0
        rem_minutes = dto['remSleepSeconds'] / 60 if 'remSleepSeconds' in dto else 0
        score = dto['sleepScores']['overall']['value']

        sleep_bb = parse_entries(sleep_raw['sleepBodyBattery'], 'startGMT', 'value')
        sleep_st = parse_entries(sleep_raw['sleepStress'], 'startGMT', 'value')
        sleep_hr = parse_entries(sleep_raw['sleepHeartRate'], 'startGMT', 'value')

        # Body Battery のデータを再計算
        bb_entries = parse_entries(data['bb_raw'], 'timestamp', 'value')
        bb_stats = recalc_min_max(bb_entries)
        bed_bb = min(sleep_bb, key=lambda e: e['time'])
        wake_bb = max(sleep_bb, key=lambda e: e['time'])
        bb_min = bb_stats['min']
        bb_max = bb_stats['max']
        
        # ストレスのデータを再計算
        st_entries = parse_entries(data['stress_raw'], 'timestamp', 'stressLevel')
        st_stats = recalc_min_max(st_entries)
        bed_st = min(sleep_st, key=lambda e: e['time'])
        wake_st = max(sleep_st, key=lambda e: e['time'])
        st_min = st_stats['min']
        st_max = st_stats['max']

        # 心拍数のデータを再計算
        hr_entries = parse_entries(data['hr_raw'], 'timestamp', 'heartRate')
        hr_stats = recalc_min_max(hr_entries)
        bed_hr = min(sleep_hr, key=lambda e: e['time'])
        wake_hr = max(sleep_hr, key=lambda e: e['time'])
        hr_min = hr_stats['min']
        hr_max = hr_stats['max']

        #HRV のデータを再計算
        hrv = data['hrv_raw']
        if len(hrv) > 0:
            hrv_values = [e['hrvValue'] for e in hrv]
            hrv_min = min(hrv_values)
            hrv_max = max(hrv_values)
            hrv_avg = sum(hrv_values) / len(hrv_values)
        else:
            hrv_min = None
            hrv_max = None
            hrv_avg = None


    # ➋ 行に展開（例：お好みで）
    row = [
        today.strftime('%Y-%m-%d'),
        sleep_start.isoformat(),
        sleep_end.isoformat(),
        deep_minutes,
        light_minutes,
        rem_minutes,
        score,
        bed_bb['value'],
        bed_bb['time'].isoformat(),
        wake_bb['value'],
        wake_bb['time'].isoformat(),
        bb_min['value'],
        bb_min['time'].isoformat(),
        bb_max['value'],
        bb_max['time'].isoformat(),
        bed_st['value'],
        bed_st['time'].isoformat(),
        wake_st['value'],
        wake_st['time'].isoformat(),
        st_min['value'],
        st_min['time'].isoformat(),
        st_max['value'],
        st_max['time'].isoformat(),
        bed_hr['value'],
        bed_hr['time'].isoformat(),
        wake_hr['value'],
        wake_hr['time'].isoformat(),
        hr_min['value'],
        hr_min['time'].isoformat(),
        hr_max['value'],
        hr_max['time'].isoformat(),
        hrv_avg,
        hrv_max,
        hrv_min
    ]

    # ➌ Sheets API
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(KEY_FILE, scopes=scope)
    gc    = gspread.authorize(creds)
    sh    = gc.open_by_url(SHEET_URL)
    sh.sheet1.append_row(row, value_input_option="USER_ENTERED")

if __name__ == '__main__':
    main(sys.argv[1])

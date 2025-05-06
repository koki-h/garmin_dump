# garmin_dump
GarminConnectからデータを取得して直近の睡眠時データと前日データの要約を表示する

## 使用しているライブラリ
https://github.com/cyberjunky/python-garminconnect

## macOS で「Garmin データを自動でメモ（Notes）に保存する」ワークフローの作り方

---

1. **準備スクリプトをそろえる**

   * `get_garmin_data.py` … Garmin から生データを取得して JSON を出力。
   * `display_result.rb` … その JSON を読み取り、見やすいテキストを標準出力に出す。
   * 上の 2 本を呼び出すラッパー `~/scripts/run_garmin.sh` を作成し、実行権限を付ける。

     ```bash
     #!/usr/bin/env bash
     python3 ~/…/get_garmin_data.py  > /tmp/raw.json
     ruby    ~/…/display_result.rb   /tmp/raw.json
     ```

2. **Automator を開いてアプリケーションを新規作成**

   * 「新規書類」→「アプリケーション」を選択。
   * ライブラリ一覧から **ユーティリティ › シェルスクリプトを実行** を 1 つだけドラッグ。
   * 右側の設定は *Shell: /bin/bash*、*Pass input: to stdin* のまま。

3. **シェルスクリプト欄に下記を貼り付ける**

   ```bash
   #!/usr/bin/env bash
   # 1) Garmin→Ruby の出力を一時ファイルに保存
   ~/scripts/run_garmin.sh > /tmp/garmin_output.txt

   # 2) 改行を <br> に変換し HTML エスケープ
   html_text=$(sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/$/<br>/g' /tmp/garmin_output.txt)

   # 3) ノート名（JST 日付）
   today=$(TZ=Asia/Tokyo date +"%Y-%m-%d")

   # 4) AppleScript で Notes へ追記
   osascript <<EOF
   set noteTitle to "${today} Garmin"
   set fileText  to "${html_text}"

   tell application "Notes"
     -- Garmin Logs フォルダを用意
     if not (exists folder "Garmin Logs" of default account) then
       make new folder at default account with properties {name:"Garmin Logs"}
     end if
     set targetFolder to folder "Garmin Logs" of default account

     -- 同日タイトルのノートがあれば追記、なければ新規
     if exists note noteTitle of targetFolder then
       set theNote to note noteTitle of targetFolder
       set body of theNote to (body of theNote & "<br><br>" & fileText)
     else
       make new note at targetFolder with properties {name:noteTitle, body:fileText}
     end if
   end tell
   EOF
   ```

4. **アプリケーションとして保存**

   * 例：`Run Garmin to Notes.app` を `~/Applications` などに保存。

5. **ログイン項目に登録**

   * システム設定 › ユーザとグループ › ログイン項目を開き、
     ［＋］ボタンで 4 のアプリを追加。
   * これで Mac へログインすると自動実行される。

6. **動作確認**

   * 作ったアプリをダブルクリックしてテスト。
   * メモ（Notes）アプリに *Garmin Logs* フォルダが作成され、
     その日の「YYYY-MM-DD Garmin」ノートに整形テキストが追記されていれば成功。

---

**ポイントのおさらい**

* 出力を一時ファイルに保存し、`sed` で `<br>` を付与して改行を保持。
* HTML 特殊文字をエスケープしてメモ内の表示崩れを防止。
* 日付ごとに個別タイトルでノートを管理し、同じ日付なら追記。
* すべて 1 つの「シェルスクリプトを実行」アクションで完結させるとトラブルが少ない。



## Google スプレッドシートへ自動追記するためのセットアップ

### 1. Google Cloud でサービスアカウント&キーを作成

1. **Google Cloud Console** → 新しいプロジェクトを作成

2. 「API とサービス › ライブラリ」で **Google Sheets API** を **有効化**

3. 「IAM と管理 › サービスアカウント」 → **＋サービスアカウントを作成**

   * 役割は **編集者**（または「Sheets > Sheets Editor」）で十分

4. 「キー」タブ → **＋キーを追加 › JSON**

   * ダウンロードされた `XXXXX.json` を、リポジトリ外の安全な場所に保存
     例：`~/garmin-automation/keys/gsheet_key.json`

5. 追記：データを書き込みたい **Google スプレッドシート** を開き、
   右上〔共有〕→ **サービスアカウントのメールアドレス** を “編集者” として追加

---

### 2. 必要パッケージをインストール

```bash
cd ~/garmin-automation
source venv/bin/activate        # すでに venv を作っていない場合は python3 -m venv venv
pip install gspread google-auth
```

---

### 3. `append_gsheet.py` を編集（または config YAML を用意）

```python
# append_gsheet.py 主要部
KEY_FILE  = '/Users/<you>/garmin-automation/keys/gsheet_key.json'   # 1 で保存したキー
SHEET_URL = 'https://docs.google.com/spreadsheets/d/xxxxxxxxxxxxxxxxxxxx'  # 対象シートURL
```

> **行内容を変えたい場合**
> `row = […]` に入れる要素を自由に編集してください。
> 例：`['日付', sleep_score, bb_min, bb_max, stress_max, hr_min]`

---

### 4. コマンドテスト

```bash
# raw_data.json は get_garmin_data.py の出力（生データ）
python3 append_gsheet.py /tmp/raw.json
```

* スプレッドシート最終行に値が追加されれば OK
* エラーが出る場合は：

  * サービスアカウントをシートに共有していない
  * `KEY_FILE` パス誤り
  * API を有効化していない
    を確認

---

### 5. 定期実行に組み込む

* 既存のシェルラッパー `run_garmin.sh` 末尾に **1 行追加**するだけ

```bash
python3 /Users/<you>/garmin_dump/append_gsheet.py /tmp/raw.json
```

* Automator でも cron でも launchd でも、
  **`run_garmin.sh` が呼ばれれば Sheets にも追記**されます。

---

これでスプレッドシート連携は完了です。
毎回の処理フロー：

1. `get_garmin_data.py` → 生 JSON 出力
2. `append_gsheet.py` が JSON を読み取り → Sheets API で最終行に `append_row`


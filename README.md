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

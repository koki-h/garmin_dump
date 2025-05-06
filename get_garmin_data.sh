#!/bin/bash
# Garmin Connect APIからデータを取得するスクリプト
python3 -W "ignore:::urllib3" get_garmin_data.py > result.json
# Ruby スクリプトで整形表示
ruby display_result.rb result.json


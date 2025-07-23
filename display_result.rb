#!/usr/bin/env ruby
require 'json'
require 'time'
require 'date'
require 'pp'

# コマンドライン引数 or デフォルトの JSON ファイル
file = ARGV[0] || 'result.json'
data = JSON.parse(File.read(file))

# UTC→JST 変換メソッド
def to_jst(timestr)
  return nil unless timestr
  # ISO 8601 文字列（UTCとみなす）をパース
  t = Time.parse(timestr + ' UTC')
  # JST(+09:00) に変換
  t.getlocal('+09:00')
end

# 配列データをパースして [{time: Time, value: 数値}, ...] の形式に
def parse_entries(raw, time_key, val_key)
  raw.map do |e|
    ts = e[time_key] || e['timestamp']
    val = e[val_key]
    val = 0 if val && val < 0
    next unless ts && val
    t = to_jst(ts)
    { time: t, value: val }
  end.compact
end


# 時刻を基準にデータを取得
def closest_point(data, target_time)
  data.min_by { |h| (h[:time] - target_time).abs }
end

# 前日全体の min/max を計算
def recalc_min_max(entries)
  return { min: nil, max: nil } if entries.empty?
  # 前日のデータのみを抽出
  entries = entries.select { |e| e[:time].to_time < @today }
  entries = entries.reject { |h| h[:value] == 0 }

  min_e = entries.min_by { |e| e[:value] }
  max_e = entries.max_by { |e| e[:value] }
  # 前日の日付を取得
  yesterday = @today - 24 * 60 * 60
  # 前日の15時の時刻を取得
  time = Time.new(yesterday.year, yesterday.month, yesterday.day, 15, 0, 0, '+09:00')
  # 15時の時刻を基準にデータを取得
  y15_e = closest_point(entries, time)
  # 19時の時刻を基準にデータを取得
  y19_e = closest_point(entries, time + 4 * 60 * 60) # 15時 + 4時間
  {
    min: { time: min_e[:time], value: min_e[:value] },
    max: { time: max_e[:time], value: max_e[:value] },
    y15: { time: y15_e[:time], value: y15_e[:value] },
    y19: { time: y19_e[:time], value: y19_e[:value] }
  }
end

# sleep summary
@today = Time.parse(data['date'])
dto = data.dig('sleep_raw', 'dailySleepDTO') || {}
sleep_start = to_jst(dto['sleepStartTimestampGMT'])
sleep_end   = to_jst(dto['sleepEndTimestampGMT'])
deep_minutes  = (dto['deepSleepSeconds']  || 0) / 60
light_minutes = (dto['lightSleepSeconds'] || 0) / 60
rem_minutes   = (dto['remSleepSeconds']   || 0) / 60
score = dto.dig('sleepScores','overall','value')
sleep_bb = parse_entries(data.dig('sleep_raw', 'sleepBodyBattery'), 'startGMT', 'value') || [] 
sleep_st = parse_entries(data.dig('sleep_raw', 'sleepStress'), 'startGMT', 'value') || []
sleep_hr = parse_entries(data.dig('sleep_raw', 'sleepHeartRate'), 'startGMT', 'value') || []
sleep_hrv = data['sleep_raw']['avgOvernightHrv'] || nil
puts "【#{data['date']} の Garmin 睡眠データ】"
puts "■ 睡眠概要"
puts "- スコア: #{score || 'N/A'}"
puts "- 時間: #{sleep_start.strftime('%Y-%m-%d %H:%M')} ～ #{sleep_end.strftime('%Y-%m-%d %H:%M')}"
puts "- 深: #{deep_minutes}分 / 浅: #{light_minutes}分 / REM: #{rem_minutes}分"
puts

# Body Battery
bb_entries = parse_entries(data['bb_raw'], 'timestamp', 'value')
bb_stats   = recalc_min_max(bb_entries)
bed_bb     = sleep_bb.min_by { |e| e[:time] }
wake_bb    = sleep_bb.max_by { |e| e[:time] }

puts "■ Body Battery"
puts "- 就寝時: 値=#{bed_bb[:value]}  時刻=#{bed_bb[:time].strftime('%H:%M')}"
puts "- 起床時: 値=#{wake_bb[:value]}  時刻=#{wake_bb[:time].strftime('%H:%M')}"
puts "- 前日最大: 値=#{bb_stats[:max][:value]}  時刻=#{bb_stats[:max][:time].strftime('%H:%M')}"
puts "- 前日最小: 値=#{bb_stats[:min][:value]}  時刻=#{bb_stats[:min][:time].strftime('%H:%M')}"
puts "- 前日15時: 値=#{bb_stats[:y15][:value]}  時刻=#{bb_stats[:y15][:time].strftime('%H:%M')}"
puts "- 前日19時: 値=#{bb_stats[:y19][:value]}  時刻=#{bb_stats[:y19][:time].strftime('%H:%M')}"
puts

# ストレス
st_entries = parse_entries(data['stress_raw'], 'timestamp', 'stressLevel')
st_stats   = recalc_min_max(st_entries)
bed_st     = sleep_st.min_by { |e| e[:time] }
wake_st    = sleep_st.max_by { |e| e[:time] }

puts "■ ストレス"
puts "- 就寝時: 値=#{bed_st[:value]}  時刻=#{bed_st[:time].strftime('%H:%M')}"
puts "- 起床時: 値=#{wake_st[:value]}  時刻=#{wake_st[:time].strftime('%H:%M')}"
puts "- 前日最大: 値=#{st_stats[:max][:value]}  時刻=#{st_stats[:max][:time].strftime('%H:%M')}"
puts "- 前日最小: 値=#{st_stats[:min][:value]}  時刻=#{st_stats[:min][:time].strftime('%H:%M')}"
puts "- 前日15時: 値=#{st_stats[:y15][:value]}  時刻=#{st_stats[:y15][:time].strftime('%H:%M')}"
puts "- 前日19時: 値=#{st_stats[:y19][:value]}  時刻=#{st_stats[:y19][:time].strftime('%H:%M')}"
puts

# 心拍数
hr_entries = parse_entries(data['hr_raw'], 'timestamp', 'heartRate')
hr_stats   = recalc_min_max(hr_entries)
bed_hr     = sleep_hr.min_by { |e| e[:time] }
wake_hr    = sleep_hr.max_by { |e| e[:time] }

puts "■ 心拍数"
puts "- 就寝時: 値=#{bed_hr[:value]}  時刻=#{bed_hr[:time].strftime('%H:%M')}"
puts "- 起床時: 値=#{wake_hr[:value]}  時刻=#{wake_hr[:time].strftime('%H:%M')}"
puts "- 前日最大: 値=#{hr_stats[:max][:value]}  時刻=#{hr_stats[:max][:time].strftime('%H:%M')}"
puts "- 前日最小: 値=#{hr_stats[:min][:value]}  時刻=#{hr_stats[:min][:time].strftime('%H:%M')}"
puts "- 前日15時: 値=#{hr_stats[:y15][:value]}  時刻=#{hr_stats[:y15][:time].strftime('%H:%M')}"
puts "- 前日19時: 値=#{hr_stats[:y19][:value]}  時刻=#{hr_stats[:y19][:time].strftime('%H:%M')}"
puts

# HRV は sleep_summary の値をそのまま表示
hrv = data['hrv_raw'] || []
if hrv.any?
  hrv_vals = hrv.map { |e| e['hrvValue'] }
  puts "■ HRV (睡眠中)"
  puts "- 平均: #{sleep_hrv || (hrv_vals.sum.to_f / hrv_vals.size).round(1)}"
  puts "- 最大: #{hrv_vals.max}"
  puts "- 最小: #{hrv_vals.min}"
  puts
end

# 就寝前の血圧を表示
bp_y = data['bp_y_raw'] || []
bp_y = bp_y[0]['measurements']
bp_t = data['bp_raw'] || []
bp_t = bp_t[0]['measurements']

puts "■ 血圧"
if bp_y
  bp_y = bp_y.max_by { |e| e['measurementTimestampGMT'] }
  bp_y['time'] = to_jst(bp_y['measurementTimestampGMT'])
  puts "- 就寝前: #{bp_y['systolic']}/#{bp_y['diastolic']} #{bp_y['pulse']}bpm 時刻=#{bp_y['time'].strftime('%H:%M')}"
else
  puts "- 就寝前: データなし"
end
if bp_t
  bp_t = bp_t.min_by { |e| e['measurementTimestampGMT'] }
  bp_t['time'] = to_jst(bp_t['measurementTimestampGMT'])
  puts "- 起床時: #{bp_t['systolic']}/#{bp_t['diastolic']} #{bp_t['pulse']}bpm 時刻=#{bp_t['time'].strftime('%H:%M')}"
else
  puts "- 起床時: データなし"
end
puts
bp_y = data['bp_y_raw'] || []
bp_y = bp_y[0]['measurements'].sort_by{|e| e['measurementTimestampGMT']}.slice(1..-2)
puts "■ 前日日中血圧" unless bp_y.empty?
bp_y.each do |e|
  next unless e['systolic'] && e['diastolic']
  time = to_jst(e['measurementTimestampGMT'])
  puts "- #{time.strftime('%H:%M')}: #{e['systolic']}/#{e['diastolic']} #{e['pulse']}bpm"
end

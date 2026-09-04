import os
import hmac
import hashlib
import base64
import requests
import threading
import time
import re
from datetime import datetime
from flask import Flask, request, abort
app = Flask(__name__)
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
NOTIFY_GROUP_ID = os.environ.get("NOTIFY_GROUP_ID")
# リマインダー保存場所
reminders = []
def verify_signature(body, signature):
    hash_value = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)
def reply_message(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    response = requests.post(
        url,
        headers=headers,
        json=data
    )
    print("LINE返信ステータス:", response.status_code)
    print("LINE返信結果:", response.text)
def push_to_group(text):
    """Aグループへ通知"""
    if not NOTIFY_GROUP_ID:
        print("NOTIFY_GROUP_IDが設定されていません")
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    data = {
        "to": NOTIFY_GROUP_ID,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    response = requests.post(
        url,
        headers=headers,
        json=data
    )
    print("Aグループ通知ステータス:", response.status_code)
    print("Aグループ通知結果:", response.text)
def reminder_worker():
    """リマインダーを監視する"""
    while True:
        now = datetime.now()
        for reminder in reminders[:]:
            if now >= reminder["time"]:
                message = (
                    "🔔 リマインド\n\n"
                    + reminder["text"]
                )
                print("リマインダー実行:", message)
                push_to_group(message)
                reminders.remove(reminder)
        time.sleep(10)
def parse_reminder(text):
    # 例：
    # 9月4日15時30分にテスト
    # 9月4日15時にゴミ出し
    pattern = (
        r"(\d{1,2})月"
        r"(\d{1,2})日"
        r"(\d{1,2})時"
        r"(?:([0-5]?\d)分)?"
        r"に(.+)"
    )
    match = re.search(pattern, text)
    if not match:
        return None
    month = int(match.group(1))
    day = int(match.group(2))
    hour = int(match.group(3))
    minute = match.group(4)
    if minute:
        minute = int(minute)
    else:
        minute = 0
    reminder_text = match.group(5).strip()
    year = datetime.now().year
    try:
        reminder_time = datetime(
            year,
            month,
            day,
            hour,
            minute
        )
    except ValueError:
        return None
    return {
        "time": reminder_time,
        "text": reminder_text
    }
@app.route("/")
def home():
    return "LINE Reminder Bot is running!"
@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, signature):
        print("署名チェック失敗")
        abort(400)
    data = request.get_json()
    print("LINEから受信:", data)
    for event in data.get("events", []):
        if event.get("type") != "message":
            continue
        source = event.get("source", {})
        reply_token = event.get("replyToken")
        # 個人トーク
        if source.get("type") == "user":
            message = event.get("message", {})
            if message.get("type") != "text":
                continue
            text = message.get("text", "").strip()
            print("個人トーク:", text)
            reminder = parse_reminder(text)
            if reminder:
                reminders.append(reminder)
                time_text = reminder["time"].strftime(
                    "%Y年%m月%d日 %H:%M"
                )
                reply_message(
                    reply_token,
                    "✅ リマインダーを登録しました。\n\n"
                    + time_text
                    + "\n"
                    + reminder["text"]
                )
            else:
                reply_message(
                    reply_token,
                    "リマインダーを登録する場合は、\n\n"
                    "「9月4日15時30分に○○」\n\n"
                    "のように送ってください。"
                )
        # グループ
        elif source.get("type") == "group":
            group_id = source.get("groupId")
            print("グループID:", group_id)
            reply_message(
                reply_token,
                "このグループのIDです。\n\n" + group_id
            )
    return "OK"
if __name__ == "__main__":
    # リマインダー監視開始
    thread = threading.Thread(
        target=reminder_worker,
        daemon=True
    )
    thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port
    )

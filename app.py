import os
import hmac
import hashlib
import base64
import requests
import sqlite3
import re

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, abort


app = Flask(__name__)


# =========================
# 環境変数
# =========================

CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
NOTIFY_GROUP_ID = os.environ.get("NOTIFY_GROUP_ID")


# =========================
# 設定
# =========================

DB_FILE = "reminders.db"

# 日本時間
JST = ZoneInfo("Asia/Tokyo")


# =========================
# データベース初期化
# =========================

def init_db():

    conn = sqlite3.connect(DB_FILE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reminder_time TEXT NOT NULL,
            reminder_text TEXT NOT NULL,
            notified INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

    print("データベース初期化完了")


# =========================
# リマインダー登録
# =========================

def add_reminder(reminder_time, reminder_text):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        INSERT INTO reminders
        (reminder_time, reminder_text, notified)
        VALUES (?, ?, 0)
        """,
        (
            reminder_time.strftime("%Y-%m-%d %H:%M:%S"),
            reminder_text
        )
    )

    conn.commit()
    conn.close()

    print(
        "リマインダー登録:",
        reminder_time.strftime("%Y-%m-%d %H:%M:%S"),
        reminder_text
    )


# =========================
# 時間になったリマインダー取得
# =========================

def get_due_reminders():

    # 日本時間で現在時刻を取得
    now = datetime.now(JST)

    now_text = now.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        "現在の日本時間:",
        now_text
    )

    conn = sqlite3.connect(DB_FILE)

    rows = conn.execute(
        """
        SELECT id, reminder_time, reminder_text
        FROM reminders
        WHERE notified = 0
        AND reminder_time <= ?
        ORDER BY reminder_time
        """,
        (
            now_text,
        )
    ).fetchall()

    conn.close()

    return rows


# =========================
# 通知済みにする
# =========================

def mark_notified(reminder_id):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        UPDATE reminders
        SET notified = 1
        WHERE id = ?
        """,
        (
            reminder_id,
        )
    )

    conn.commit()
    conn.close()

    print(
        "通知済みにしました:",
        reminder_id
    )


# =========================
# LINE署名確認
# =========================

def verify_signature(body, signature):

    if not CHANNEL_SECRET:

        print(
            "CHANNEL_SECRETがありません"
        )

        return False

    hash_value = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(
        hash_value
    ).decode("utf-8")

    return hmac.compare_digest(
        expected,
        signature
    )


# =========================
# LINE返信
# =========================

def reply_message(
    reply_token,
    text
):

    url = (
        "https://api.line.me/"
        "v2/bot/message/reply"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization":
            f"Bearer {ACCESS_TOKEN}"
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

    print(
        "LINE返信:",
        response.status_code,
        response.text
    )


# =========================
# Aグループへ通知
# =========================

def push_to_group(text):

    if not NOTIFY_GROUP_ID:

        print(
            "NOTIFY_GROUP_IDがありません"
        )

        return False

    url = (
        "https://api.line.me/"
        "v2/bot/message/push"
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization":
            f"Bearer {ACCESS_TOKEN}"
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

    print(
        "Aグループ通知:",
        response.status_code,
        response.text
    )

    return response.status_code == 200


# =========================
# リマインダー解析
# =========================

def parse_reminder(text):

    pattern = (
        r"(\d{1,2})月"
        r"(\d{1,2})日"
        r"(\d{1,2})時"
        r"(?:([0-5]?\d)分)?"
        r"に(.+)"
    )

    match = re.search(
        pattern,
        text
    )

    if not match:

        return None

    month = int(
        match.group(1)
    )

    day = int(
        match.group(2)
    )

    hour = int(
        match.group(3)
    )

    minute_text = match.group(4)

    if minute_text:

        minute = int(
            minute_text
        )

    else:

        minute = 0

    reminder_text = match.group(5).strip()


    # 日本時間の現在日時
    now = datetime.now(JST)

    year = now.year


    try:

        reminder_time = datetime(
            year,
            month,
            day,
            hour,
            minute,
            tzinfo=JST
        )

    except ValueError:

        return None


    return (
        reminder_time,
        reminder_text
    )


# =========================
# リマインダー確認
# =========================

@app.route("/check")
def check_reminders():

    print(
        "======================"
    )

    print(
        "リマインダー確認開始"
    )

    print(
        "現在時刻:",
        datetime.now(JST).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    reminders = get_due_reminders()

    print(
        "期限到来リマインダー:",
        len(reminders)
    )

    count = 0


    for (
        reminder_id,
        reminder_time,
        reminder_text
    ) in reminders:

        print(
            "通知対象:",
            reminder_time,
            reminder_text
        )


        message = (
            "🔔 颯太の予定\n\n"
            + reminder_text
        )


        success = push_to_group(
            message
        )


        if success:

            mark_notified(
                reminder_id
            )

            count += 1


    print(
        "今回の通知数:",
        count
    )

    print(
        "======================"
    )


    return (
        "OK\n"
        f"通知数: {count}"
    )


# =========================
# 登録済みリマインダー確認
# =========================

@app.route("/reminders")
def show_reminders():

    conn = sqlite3.connect(
        DB_FILE
    )

    rows = conn.execute(
        """
        SELECT
            id,
            reminder_time,
            reminder_text,
            notified
        FROM reminders
        ORDER BY reminder_time
        """
    ).fetchall()

    conn.close()


    if not rows:

        return "登録されているリマインダーはありません。"


    result = []

    for row in rows:

        reminder_id = row[0]
        reminder_time = row[1]
        reminder_text = row[2]
        notified = row[3]


        if notified == 1:

            status = "通知済み"

        else:

            status = "未通知"


        result.append(
            f"{reminder_id}: "
            f"{reminder_time} "
            f"{reminder_text} "
            f"[{status}]"
        )


    return "<br>".join(
        result
    )


# =========================
# トップページ
# =========================

@app.route("/")
def home():

    return (
        "LINE Reminder Bot is running!"
    )


# =========================
# LINE Webhook
# =========================

@app.route(
    "/callback",
    methods=["POST"]
)
def callback():

    body = request.get_data()

    signature = request.headers.get(
        "X-Line-Signature",
        ""
    )


    # 署名確認

    if not verify_signature(
        body,
        signature
    ):

        print(
            "署名チェック失敗"
        )

        abort(400)


    data = request.get_json()

    print(
        "LINEから受信:",
        data
    )


    for event in data.get(
        "events",
        []
    ):


        # メッセージ以外は無視

        if event.get("type") != "message":

            continue


        source = event.get(
            "source",
            {}
        )

        reply_token = event.get(
            "replyToken"
        )


        # =========================
        # 個人トーク
        # =========================

        if source.get("type") == "user":

            message = event.get(
                "message",
                {}
            )


            if message.get("type") != "text":

                continue


            text = message.get(
                "text",
                ""
            ).strip()


            print(
                "個人トーク:",
                text
            )


            # リマインダー解析

            result = parse_reminder(
                text
            )


            if result:

                (
                    reminder_time,
                    reminder_text
                ) = result


                # データベースに保存

                add_reminder(
                    reminder_time,
                    reminder_text
                )


                # 登録確認

                time_text = (
                    reminder_time.strftime(
                        "%Y年%m月%d日 %H:%M"
                    )
                )


                reply_message(
                    reply_token,

                    "✅ リマインダーを登録しました。\n\n"
                    + time_text
                    + "\n"
                    + reminder_text
                )


            else:

                reply_message(
                    reply_token,

                    "リマインダーを登録する場合は、\n\n"
                    "「9月4日15時30分に○○」\n\n"
                    "のように送ってください。"
                )


        # =========================
        # グループ
        # =========================

        elif source.get("type") == "group":

            group_id = source.get(
                "groupId"
            )


            print(
                "グループID:",
                group_id
            )


            reply_message(
                reply_token,

                "このグループのIDです。\n\n"
                + group_id
            )


    return "OK"


# =========================
# 起動
# =========================

init_db()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port
    )

import os
import hmac
import hashlib
import base64
import requests
from flask import Flask, request, abort

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")


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

    requests.post(url, headers=headers, json=data)


@app.route("/")
def home():
    return "LINE Reminder Bot is running!"


@app.route("/callback", methods=["POST"])
def callback():

    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, signature):
        abort(400)

    data = request.get_json()

    for event in data.get("events", []):

        if event.get("type") != "message":
            continue

        source = event.get("source", {})
        reply_token = event.get("replyToken")

        if source.get("type") == "group":

            group_id = source.get("groupId")

            reply_message(
                reply_token,
                "AグループのIDです。\n\n" + group_id
            )

    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

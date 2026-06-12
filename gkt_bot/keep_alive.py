from __future__ import annotations

from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home() -> str:
    return "🤖 Bot Discord en ligne !"


def run() -> None:
    app.run(host="0.0.0.0", port=10000)


def keep_alive() -> None:
    thread = Thread(target=run, daemon=True)
    thread.start()

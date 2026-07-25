from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from store_customer_service.production import create_customer_service  # noqa: E402


app = Flask(__name__)
workflow = create_customer_service()


@app.get("/")
def index():
    return render_template("customer_chat.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "customer-chat"})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    result = workflow.run(
        str(payload.get("message", "")),
        str(payload.get("session_id") or uuid4()),
        str(payload.get("user_id") or "U1001"),
    )
    return jsonify(result.to_dict()), 200 if result.success else 400


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("WEB_PORT", "5058")),
        debug=False,
    )

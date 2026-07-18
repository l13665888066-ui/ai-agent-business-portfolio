from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from ecommerce_agent.factory import create_workflow  # noqa: E402


app = Flask(__name__)
workflow = create_workflow()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    response = workflow.run(
        question=payload.get("message", ""),
        session_id=payload.get("session_id", "demo-session"),
        user_id=payload.get("user_id", "U1001"),
    )
    return jsonify(response.to_dict())


if __name__ == "__main__":
    app.run(
        host=os.getenv("WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_PORT", "5000")),
        debug=False,
    )

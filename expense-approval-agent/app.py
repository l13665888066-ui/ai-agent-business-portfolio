from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from expense_agent.database import Database  # noqa: E402
from expense_agent.extractor import StructuredExtractor  # noqa: E402
from expense_agent.knowledge import PolicyKnowledgeService  # noqa: E402
from expense_agent.policy import ApprovalPolicyEngine  # noqa: E402
from expense_agent.workflow import ExpenseApprovalWorkflow  # noqa: E402


database = Database(ROOT / ".runtime" / "expense_agent.db")
workflow = ExpenseApprovalWorkflow(
    StructuredExtractor(),
    ApprovalPolicyEngine(),
    PolicyKnowledgeService(ROOT / "data" / "expense_policy.md"),
    database,
)
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/precheck")
def precheck():
    decision = workflow.run(request.get_json(silent=True) or {})
    return jsonify(decision.to_dict())


@app.get("/api/applications/<int:application_id>")
def application_detail(application_id: int):
    value = database.get_application(application_id)
    if value is None:
        return jsonify({"success": False, "error_code": "NOT_FOUND"}), 404
    return jsonify(
        {
            "success": True,
            "application": value,
            "audit_logs": database.list_audit(application_id),
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100, debug=False)

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from expense_agent.config import Settings  # noqa: E402
from expense_agent.database import BudgetUnavailableError  # noqa: E402
from expense_agent.factory import create_workflow  # noqa: E402


settings = Settings.from_env()
workflow, database = create_workflow(settings)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_ATTACHMENTS = {".pdf", ".png", ".jpg", ".jpeg"}
DEMO_IDENTITIES = ("E1001", "M2001", "F3001")


def current_actor_id() -> str:
    return (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or ""
    ).strip().upper()


def error_response(
    error_code: str,
    message: str,
    status_code: int,
):
    return (
        jsonify(
            {
                "success": False,
                "error_code": error_code,
                "message": message,
            }
        ),
        status_code,
    )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "database": "sqlite",
            "workflow": "expense-approval-v2",
        }
    )


@app.get("/api/demo-identities")
def demo_identities():
    identities = []
    for user_id in DEMO_IDENTITIES:
        identity = database.get_identity(user_id)
        if identity is not None:
            identities.append(identity.to_dict())
    return jsonify({"success": True, "identities": identities})


@app.get("/api/session")
def session_profile():
    identity = database.get_identity(current_actor_id())
    if identity is None:
        return error_response(
            "IDENTITY_NOT_FOUND",
            "未找到当前演示身份",
            404,
        )
    return jsonify(
        {
            "success": True,
            "identity": identity.to_dict(),
            "permissions": {
                "can_submit": identity.role == "employee",
                "can_approve": identity.role
                in {"manager", "finance"},
            },
        }
    )


@app.post("/api/attachments")
def upload_attachment():
    actor = database.get_identity(current_actor_id())
    if actor is None or actor.role != "employee":
        return error_response(
            "UPLOAD_FORBIDDEN",
            "只有员工身份可以上传报销附件",
            403,
        )
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return error_response(
            "FILE_REQUIRED",
            "请选择需要上传的票据文件",
            400,
        )
    original_name = secure_filename(uploaded.filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENTS:
        return error_response(
            "FILE_TYPE_NOT_ALLOWED",
            "仅支持PDF、PNG、JPG或JPEG文件",
            400,
        )
    attachment_id = uuid4().hex
    stored_name = f"{attachment_id}{suffix}"
    settings.upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    destination = settings.upload_directory / stored_name
    uploaded.save(destination)
    size_bytes = destination.stat().st_size
    if size_bytes <= 0:
        destination.unlink(missing_ok=True)
        return error_response(
            "EMPTY_FILE",
            "附件内容为空",
            400,
        )
    database.add_attachment(
        attachment_id,
        original_name,
        stored_name,
        uploaded.content_type
        or "application/octet-stream",
        size_bytes,
        actor.user_id,
    )
    return (
        jsonify(
            {
                "success": True,
                "attachment": {
                    "attachment_id": attachment_id,
                    "name": original_name,
                    "size_bytes": size_bytes,
                },
            }
        ),
        201,
    )


@app.post("/api/applications")
def submit_application():
    actor_id = current_actor_id()
    decision = workflow.submit(
        request.get_json(silent=True) or {},
        actor_id,
    )
    status_code = 201 if decision.success else 400
    if decision.error_code in {
        "DUPLICATE_INVOICE",
        "DUPLICATE_INVOICE_RACE",
    }:
        status_code = 409
    if decision.error_code in {
        "IDENTITY_NOT_FOUND",
        "IDENTITY_INACTIVE",
        "APPLICANT_ROLE_INVALID",
        "ATTACHMENT_FORBIDDEN",
    }:
        status_code = 403
    return jsonify(decision.to_dict()), status_code


@app.post("/api/precheck")
def dify_precheck():
    """保留Dify HTTP节点兼容入口，正式页面使用受控身份接口。"""
    decision = workflow.run(
        request.get_json(silent=True) or {}
    )
    return jsonify(decision.to_dict())


@app.get("/api/applications")
def application_list():
    actor = database.get_identity(current_actor_id())
    if actor is None:
        return error_response(
            "IDENTITY_NOT_FOUND",
            "未找到当前演示身份",
            404,
        )
    scope = request.args.get("scope", "all")
    if scope not in {"all", "pending"}:
        return error_response(
            "INVALID_SCOPE",
            "scope仅支持all或pending",
            400,
        )
    applications = database.list_applications(actor, scope)
    return jsonify(
        {
            "success": True,
            "applications": applications,
        }
    )


@app.get("/api/applications/<int:application_id>")
def application_detail(application_id: int):
    actor = database.get_identity(current_actor_id())
    if actor is None:
        return error_response(
            "IDENTITY_NOT_FOUND",
            "未找到当前演示身份",
            404,
        )
    value = database.get_application(application_id)
    if value is None:
        return error_response(
            "APPLICATION_NOT_FOUND",
            "未找到报销申请",
            404,
        )
    if not database.can_view(value, actor):
        return error_response(
            "VIEW_FORBIDDEN",
            "无权查看该报销申请",
            403,
        )
    budget = database.get_budget(value["department"])
    return jsonify(
        {
            "success": True,
            "application": value,
            "actions": database.list_actions(application_id),
            "audit_logs": database.list_audit(application_id),
            "budget": budget,
            "permissions": {
                "can_resubmit": actor.role == "employee"
                and value["employee_id"] == actor.user_id
                and value["status"] == "returned",
                "can_act": (
                    value["status"] == "pending_manager"
                    and actor.role == "manager"
                    and value["manager_id"] == actor.user_id
                )
                or (
                    value["status"] == "pending_finance"
                    and actor.role == "finance"
                ),
            },
        }
    )


@app.post("/api/applications/<int:application_id>/actions")
def application_action(application_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        value = workflow.act(
            application_id,
            current_actor_id(),
            str(payload.get("action", "")).strip(),
            str(payload.get("comment", "")).strip(),
        )
    except LookupError:
        return error_response(
            "APPLICATION_NOT_FOUND",
            "未找到报销申请",
            404,
        )
    except PermissionError:
        return error_response(
            "APPROVER_FORBIDDEN",
            "当前身份无权处理该申请",
            403,
        )
    except BudgetUnavailableError as error:
        return error_response(
            "BUDGET_UPDATE_FAILED",
            str(error),
            409,
        )
    except ValueError as error:
        code = str(error)
        messages = {
            "UNSUPPORTED_ACTION": "不支持的审批动作",
            "COMMENT_REQUIRED": "退回或驳回必须填写审批意见",
            "APPLICATION_NOT_ACTIONABLE": "当前申请状态不可审批",
        }
        return error_response(
            code,
            messages.get(code, "审批请求无效"),
            409,
        )
    return jsonify({"success": True, "application": value})


@app.post("/api/applications/<int:application_id>/resubmit")
def resubmit_application(application_id: int):
    decision = workflow.resubmit(
        application_id,
        request.get_json(silent=True) or {},
        current_actor_id(),
    )
    status_code = 200 if decision.success else 400
    if decision.error_code in {
        "OWNER_FORBIDDEN",
        "ATTACHMENT_FORBIDDEN",
    }:
        status_code = 403
    if decision.error_code == "APPLICATION_NOT_FOUND":
        status_code = 404
    if decision.error_code == "APPLICATION_NOT_RETURNED":
        status_code = 409
    return jsonify(decision.to_dict()), status_code


if __name__ == "__main__":
    app.run(
        host=settings.web_host,
        port=settings.web_port,
        debug=False,
    )

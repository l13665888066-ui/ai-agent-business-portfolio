from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any

from .models import ApprovalDecision, ExpenseApplication, UserIdentity


class BudgetUnavailableError(RuntimeError):
    pass


class Database:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,
        )
        self.connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._seed()

    def _init_schema(self) -> None:
        with self._lock:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    manager_id TEXT,
                    active INTEGER NOT NULL,
                    role TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS budgets (
                    department TEXT PRIMARY KEY,
                    monthly_budget REAL NOT NULL,
                    used_amount REAL NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS attachments (
                    attachment_id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    uploaded_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT NOT NULL,
                    applicant_name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    manager_id TEXT,
                    expense_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    invoice_no TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    attachment_id TEXT,
                    attachment_name TEXT,
                    decision TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_approver_role TEXT,
                    policy_sources TEXT NOT NULL,
                    semantic_review TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_invoice
                ON applications(invoice_no)
                WHERE invoice_no IS NOT NULL AND invoice_no != '';

                CREATE TABLE IF NOT EXISTS approval_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(application_id) REFERENCES applications(id)
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER,
                    actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    event TEXT NOT NULL,
                    details TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(application_id) REFERENCES applications(id)
                );
                """
            )

    def _seed(self) -> None:
        with self._lock:
            self.connection.executemany(
                """
                INSERT OR IGNORE INTO employees(
                    employee_id, name, department, manager_id, active, role
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("E1001", "张三", "销售部", "M2001", 1, "employee"),
                    ("E1002", "李四", "市场部", "M2002", 1, "employee"),
                    ("E1003", "王五", "销售部", "M2001", 0, "employee"),
                    ("M2001", "陈经理", "销售部", "F3001", 1, "manager"),
                    ("M2002", "赵经理", "市场部", "F3001", 1, "manager"),
                    ("F3001", "周会计", "财务部", "", 1, "finance"),
                ],
            )
            self.connection.executemany(
                """
                INSERT OR IGNORE INTO budgets(
                    department, monthly_budget, used_amount
                ) VALUES (?, ?, ?)
                """,
                [
                    ("销售部", 30000, 12000),
                    ("市场部", 20000, 18500),
                ],
            )

    def get_identity(self, user_id: str) -> UserIdentity | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM employees WHERE employee_id = ?",
                (user_id.upper(),),
            ).fetchone()
        if row is None:
            return None
        return UserIdentity(
            user_id=row["employee_id"],
            name=row["name"],
            role=row["role"],
            department=row["department"],
            manager_id=row["manager_id"] or "",
            active=bool(row["active"]),
        )

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        identity = self.get_identity(employee_id)
        if identity is None:
            return None
        return {
            "employee_id": identity.user_id,
            "name": identity.name,
            "department": identity.department,
            "manager_id": identity.manager_id,
            "active": identity.active,
            "role": identity.role,
        }

    def get_budget(self, department: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM budgets WHERE department = ?",
                (department,),
            ).fetchone()
        return dict(row) if row else None

    def invoice_exists(
        self,
        invoice_no: str,
        exclude_application_id: int | None = None,
    ) -> bool:
        if not invoice_no:
            return False
        sql = "SELECT 1 FROM applications WHERE invoice_no = ?"
        params: list[Any] = [invoice_no]
        if exclude_application_id is not None:
            sql += " AND id != ?"
            params.append(exclude_application_id)
        with self._lock:
            row = self.connection.execute(sql, params).fetchone()
        return row is not None

    def add_attachment(
        self,
        attachment_id: str,
        original_name: str,
        stored_name: str,
        content_type: str,
        size_bytes: int,
        uploaded_by: str,
    ) -> None:
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO attachments(
                    attachment_id, original_name, stored_name, content_type,
                    size_bytes, uploaded_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    original_name,
                    stored_name,
                    content_type,
                    size_bytes,
                    uploaded_by,
                ),
            )

    def attachment_belongs_to(
        self,
        attachment_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        if not attachment_id:
            return None
        with self._lock:
            row = self.connection.execute(
                """
                SELECT * FROM attachments
                WHERE attachment_id = ? AND uploaded_by = ?
                """,
                (attachment_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback

    def _reserve_budget(
        self,
        department: str,
        amount: float,
        *,
        allow_over_budget: bool = False,
    ) -> bool:
        if allow_over_budget:
            cursor = self.connection.execute(
                """
                UPDATE budgets
                SET used_amount = used_amount + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE department = ?
                """,
                (amount, department),
            )
            return cursor.rowcount == 1
        cursor = self.connection.execute(
            """
            UPDATE budgets
            SET used_amount = used_amount + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE department = ?
              AND monthly_budget - used_amount >= ?
            """,
            (amount, department, amount),
        )
        return cursor.rowcount == 1

    def create_application(
        self,
        application: ExpenseApplication,
        decision: ApprovalDecision,
        actor: UserIdentity,
    ) -> int:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                if decision.status == "approved" and not self._reserve_budget(
                    application.department,
                    float(application.amount or 0),
                ):
                    raise BudgetUnavailableError(
                        "审批写入时预算发生变化，需要财务复核"
                    )
                cursor = self.connection.execute(
                    """
                    INSERT INTO applications(
                        employee_id, applicant_name, department, manager_id,
                        expense_type, amount, invoice_no, expense_date, purpose,
                        attachment_id, attachment_name, decision, risk_level,
                        status, current_approver_role, policy_sources,
                        semantic_review
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        application.employee_id,
                        application.applicant_name,
                        application.department,
                        application.manager_id,
                        application.expense_type,
                        application.amount,
                        application.invoice_no,
                        application.expense_date,
                        application.purpose,
                        application.attachment_id,
                        application.attachment_name,
                        decision.decision,
                        decision.risk_level,
                        decision.status,
                        self._approver_role(decision.status),
                        self._encode(decision.policy_sources),
                        self._encode(decision.semantic_review),
                    ),
                )
                application_id = int(cursor.lastrowid)
                self._insert_action(
                    application_id,
                    actor,
                    "submit",
                    "提交报销申请",
                    "draft",
                    decision.status,
                )
                self._insert_audit(
                    application_id,
                    actor,
                    "precheck_completed",
                    decision.to_dict(),
                )
                self.connection.execute("COMMIT")
                return application_id
            except Exception:
                self.connection.execute("ROLLBACK")
                raise

    @staticmethod
    def _approver_role(status: str) -> str:
        if status == "pending_manager":
            return "manager"
        if status == "pending_finance":
            return "finance"
        if status == "returned":
            return "employee"
        return ""

    def _insert_action(
        self,
        application_id: int,
        actor: UserIdentity,
        action: str,
        comment: str,
        from_status: str,
        to_status: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO approval_actions(
                application_id, actor_id, actor_role, action, comment,
                from_status, to_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                actor.user_id,
                actor.role,
                action,
                comment,
                from_status,
                to_status,
            ),
        )

    def _insert_audit(
        self,
        application_id: int | None,
        actor: UserIdentity,
        event: str,
        details: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO audit_logs(
                application_id, actor_id, actor_role, event, details
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                application_id,
                actor.user_id,
                actor.role,
                event,
                self._encode(details),
            ),
        )

    def add_audit(
        self,
        application_id: int | None,
        actor: UserIdentity,
        event: str,
        details: dict[str, Any],
    ) -> None:
        with self._lock:
            self._insert_audit(application_id, actor, event, details)

    def get_application(self, application_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["policy_sources"] = self._decode(
            value.get("policy_sources"),
            [],
        )
        value["semantic_review"] = self._decode(
            value.get("semantic_review"),
            {},
        )
        return value

    def can_view(
        self,
        application: dict[str, Any],
        actor: UserIdentity,
    ) -> bool:
        if actor.role == "finance":
            return True
        if actor.role == "manager":
            return application["manager_id"] == actor.user_id
        return application["employee_id"] == actor.user_id

    def list_applications(
        self,
        actor: UserIdentity,
        scope: str = "all",
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if actor.role == "employee":
            where.append("employee_id = ?")
            params.append(actor.user_id)
            if scope == "pending":
                where.append("status = 'returned'")
        elif actor.role == "manager":
            where.append("manager_id = ?")
            params.append(actor.user_id)
            if scope == "pending":
                where.append("status = 'pending_manager'")
        elif actor.role == "finance" and scope == "pending":
            where.append("status = 'pending_finance'")
        elif actor.role not in {"employee", "manager", "finance"}:
            return []

        sql = "SELECT * FROM applications"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        with self._lock:
            rows = self.connection.execute(sql, params).fetchall()
        values = []
        for row in rows:
            value = dict(row)
            value["policy_sources"] = self._decode(
                value.get("policy_sources"),
                [],
            )
            value["semantic_review"] = self._decode(
                value.get("semantic_review"),
                {},
            )
            values.append(value)
        return values

    def list_actions(self, application_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT * FROM approval_actions
                WHERE application_id = ?
                ORDER BY id
                """,
                (application_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_audit(self, application_id: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                """
                SELECT actor_id, actor_role, event, details, created_at
                FROM audit_logs
                WHERE application_id = ?
                ORDER BY id
                """,
                (application_id,),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["details"] = self._decode(value["details"], {})
            result.append(value)
        return result

    def act_on_application(
        self,
        application_id: int,
        actor: UserIdentity,
        action: str,
        comment: str,
    ) -> dict[str, Any]:
        if action not in {"approve", "return", "reject"}:
            raise ValueError("UNSUPPORTED_ACTION")
        if action in {"return", "reject"} and not comment.strip():
            raise ValueError("COMMENT_REQUIRED")

        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT * FROM applications WHERE id = ?",
                    (application_id,),
                ).fetchone()
                if row is None:
                    raise LookupError("APPLICATION_NOT_FOUND")
                application = dict(row)
                from_status = application["status"]
                if from_status == "pending_manager":
                    if (
                        actor.role != "manager"
                        or application["manager_id"] != actor.user_id
                    ):
                        raise PermissionError("APPROVER_FORBIDDEN")
                elif from_status == "pending_finance":
                    if actor.role != "finance":
                        raise PermissionError("APPROVER_FORBIDDEN")
                else:
                    raise ValueError("APPLICATION_NOT_ACTIONABLE")

                decision = application["decision"]
                risk_level = application["risk_level"]
                if action == "approve":
                    allow_over_budget = actor.role == "finance"
                    reserved = self._reserve_budget(
                        application["department"],
                        float(application["amount"]),
                        allow_over_budget=allow_over_budget,
                    )
                    if not reserved:
                        if actor.role == "manager":
                            to_status = "pending_finance"
                            decision = "财务复核"
                            risk_level = "高"
                            comment = (
                                comment.strip()
                                or "主管同意，但审批时预算不足，自动转财务复核"
                            )
                        else:
                            raise BudgetUnavailableError(
                                "未找到可更新的部门预算"
                            )
                    else:
                        to_status = "approved"
                        decision = "审批通过"
                elif action == "return":
                    to_status = "returned"
                    decision = "退回补充"
                else:
                    to_status = "rejected"
                    decision = "审批驳回"

                self.connection.execute(
                    """
                    UPDATE applications
                    SET status = ?, decision = ?, risk_level = ?,
                        current_approver_role = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        to_status,
                        decision,
                        risk_level,
                        self._approver_role(to_status),
                        application_id,
                    ),
                )
                self._insert_action(
                    application_id,
                    actor,
                    action,
                    comment.strip() or "同意",
                    from_status,
                    to_status,
                )
                self._insert_audit(
                    application_id,
                    actor,
                    "approval_action",
                    {
                        "action": action,
                        "comment": comment.strip() or "同意",
                        "from_status": from_status,
                        "to_status": to_status,
                    },
                )
                self.connection.execute("COMMIT")
            except Exception:
                self.connection.execute("ROLLBACK")
                raise
        return self.get_application(application_id) or {}

    def resubmit_application(
        self,
        application_id: int,
        application: ExpenseApplication,
        decision: ApprovalDecision,
        actor: UserIdentity,
    ) -> int:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT * FROM applications WHERE id = ?",
                    (application_id,),
                ).fetchone()
                if row is None:
                    raise LookupError("APPLICATION_NOT_FOUND")
                current = dict(row)
                if current["employee_id"] != actor.user_id:
                    raise PermissionError("OWNER_FORBIDDEN")
                if current["status"] != "returned":
                    raise ValueError("APPLICATION_NOT_RETURNED")
                if decision.status == "approved" and not self._reserve_budget(
                    application.department,
                    float(application.amount or 0),
                ):
                    raise BudgetUnavailableError(
                        "重新提交时预算发生变化，需要财务复核"
                    )

                self.connection.execute(
                    """
                    UPDATE applications
                    SET expense_type = ?, amount = ?, invoice_no = ?,
                        expense_date = ?, purpose = ?, attachment_id = ?,
                        attachment_name = ?, decision = ?, risk_level = ?,
                        status = ?, current_approver_role = ?,
                        policy_sources = ?, semantic_review = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        application.expense_type,
                        application.amount,
                        application.invoice_no,
                        application.expense_date,
                        application.purpose,
                        application.attachment_id,
                        application.attachment_name,
                        decision.decision,
                        decision.risk_level,
                        decision.status,
                        self._approver_role(decision.status),
                        self._encode(decision.policy_sources),
                        self._encode(decision.semantic_review),
                        application_id,
                    ),
                )
                self._insert_action(
                    application_id,
                    actor,
                    "resubmit",
                    "补充材料后重新提交",
                    "returned",
                    decision.status,
                )
                self._insert_audit(
                    application_id,
                    actor,
                    "application_resubmitted",
                    decision.to_dict(),
                )
                self.connection.execute("COMMIT")
            except Exception:
                self.connection.execute("ROLLBACK")
                raise
        return application_id

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._seed()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                manager_id TEXT,
                active INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS budgets (
                department TEXT PRIMARY KEY,
                monthly_budget REAL NOT NULL,
                used_amount REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                expense_type TEXT NOT NULL,
                amount REAL NOT NULL,
                invoice_no TEXT,
                expense_date TEXT,
                purpose TEXT,
                decision TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_invoice
            ON applications(invoice_no) WHERE invoice_no IS NOT NULL AND invoice_no != '';
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER,
                event TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def _seed(self) -> None:
        self.connection.executemany(
            "INSERT OR IGNORE INTO employees VALUES (?, ?, ?, ?, ?)",
            [
                ("E1001", "张三", "销售部", "M2001", 1),
                ("E1002", "李四", "市场部", "M2002", 1),
                ("E1003", "王五", "销售部", "M2001", 0),
            ],
        )
        self.connection.executemany(
            "INSERT OR IGNORE INTO budgets VALUES (?, ?, ?)",
            [("销售部", 30000, 12000), ("市场部", 20000, 18500)],
        )
        self.connection.commit()

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_budget(self, department: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM budgets WHERE department = ?", (department,)
        ).fetchone()
        return dict(row) if row else None

    def invoice_exists(self, invoice_no: str) -> bool:
        if not invoice_no:
            return False
        row = self.connection.execute(
            "SELECT 1 FROM applications WHERE invoice_no = ?", (invoice_no,)
        ).fetchone()
        return row is not None

    def create_application(self, application, decision) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO applications (
                employee_id, expense_type, amount, invoice_no, expense_date,
                purpose, decision, risk_level, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application.employee_id,
                application.expense_type,
                application.amount,
                application.invoice_no,
                application.expense_date,
                application.purpose,
                decision.decision,
                decision.risk_level,
                "pending" if decision.need_human_review else "prechecked",
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_audit(self, application_id: int | None, event: str, details: dict) -> None:
        self.connection.execute(
            "INSERT INTO audit_logs(application_id, event, details) VALUES (?, ?, ?)",
            (application_id, event, json.dumps(details, ensure_ascii=False)),
        )
        self.connection.commit()

    def get_application(self, application_id: int) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_audit(self, application_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT event, details, created_at FROM audit_logs WHERE application_id = ? ORDER BY id",
            (application_id,),
        ).fetchall()
        return [dict(row) for row in rows]

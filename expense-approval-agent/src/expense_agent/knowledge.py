from __future__ import annotations

from pathlib import Path


class PolicyKnowledgeService:
    """检索制度依据用于解释；审批结论由确定性规则引擎产生。"""

    def __init__(self, policy_file: Path):
        self.sections = self._load(policy_file)

    @staticmethod
    def _load(path: Path) -> list[tuple[str, str]]:
        sections = []
        title = ""
        lines: list[str] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("## "):
                if title:
                    sections.append((title, "\n".join(lines).strip()))
                title = raw[3:].strip()
                lines = []
            elif title:
                lines.append(raw)
        if title:
            sections.append((title, "\n".join(lines).strip()))
        return sections

    def search(self, expense_type: str) -> list[str]:
        general = [title for title, _ in self.sections if "通用" in title or "审批" in title]
        specific = [title for title, text in self.sections if expense_type and expense_type in (title + text)]
        return list(dict.fromkeys(specific + general))[:4]

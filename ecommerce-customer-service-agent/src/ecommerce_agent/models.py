from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Route:
    need_tool: bool
    tool_name: str = "none"
    tool_args: dict[str, Any] = field(default_factory=dict)
    missing_params: list[str] = field(default_factory=list)
    need_human: bool = False
    reason: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Route":
        required = {
            "need_tool",
            "tool_name",
            "tool_args",
            "missing_params",
            "need_human",
            "reason",
        }
        missing = required - set(value)
        if missing:
            raise ValueError(f"路由结果缺少字段：{sorted(missing)}")
        route = cls(**{key: value[key] for key in required})
        route.validate()
        return route

    def validate(self) -> None:
        if not isinstance(self.need_tool, bool):
            raise TypeError("need_tool必须是布尔值")
        if not isinstance(self.need_human, bool):
            raise TypeError("need_human必须是布尔值")
        if not isinstance(self.tool_name, str):
            raise TypeError("tool_name必须是字符串")
        if not isinstance(self.tool_args, dict):
            raise TypeError("tool_args必须是字典")
        if not isinstance(self.missing_params, list):
            raise TypeError("missing_params必须是列表")
        if not isinstance(self.reason, str):
            raise TypeError("reason必须是字符串")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    success: bool
    error_code: str | None
    message: str
    data: dict[str, Any] | None = None
    http_status: int | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ToolResult":
        required = {"success", "error_code", "message", "data"}
        missing = required - set(value)
        if missing:
            raise ValueError(f"Tool结果缺少字段：{sorted(missing)}")
        if not isinstance(value["success"], bool):
            raise TypeError("Tool结果的success必须是布尔值")
        return cls(
            success=value["success"],
            error_code=value["error_code"],
            message=value["message"],
            data=value["data"],
            http_status=value.get("http_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResponse:
    success: bool
    path: str
    answer: str
    error_code: str | None = None
    route: Route | None = None
    details: dict[str, Any] | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return value

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from .models import Route, ToolResult


@dataclass(frozen=True)
class ToolSpec:
    required_params: set[str]
    allowed_params: set[str]
    handler: Callable[..., ToolResult]


def _error(code: str, message: str) -> ToolResult:
    return ToolResult(False, code, message)


def _normalize_order_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if re.fullmatch(r"DD\d{4}", value) else None


def _normalize_user_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if re.fullmatch(r"U\d{4}", value) else None


def _normalize_sku(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().upper()
    return value if re.fullmatch(r"[A-Z0-9-]{3,40}", value) else None


class SafeToolExecutor:
    """模型输出视为不可信输入，白名单与参数校验通过后才执行。"""

    def __init__(self, api_client: Any):
        self.tools = {
            "query_order_tool": ToolSpec(
                {"order_id", "user_id"},
                {"order_id", "user_id"},
                api_client.query_order,
            ),
            "query_logistics_tool": ToolSpec(
                {"order_id", "user_id"},
                {"order_id", "user_id"},
                api_client.query_logistics,
            ),
            "query_inventory_tool": ToolSpec(
                {"sku"}, {"sku"}, api_client.query_inventory
            ),
            "query_refund_tool": ToolSpec(
                {"order_id", "user_id"},
                {"order_id", "user_id"},
                api_client.query_refund,
            ),
        }

    def execute(self, route: Route, user_id: str) -> ToolResult:
        if not route.need_tool:
            return _error("TOOL_NOT_REQUIRED", "当前路径不需要调用Tool")
        spec = self.tools.get(route.tool_name)
        if spec is None:
            return _error("TOOL_NOT_ALLOWED", f"不允许调用工具：{route.tool_name}")

        args = dict(route.tool_args)
        if "user_id" in spec.required_params:
            args["user_id"] = user_id

        received = set(args)
        missing = spec.required_params - received
        extra = received - spec.allowed_params
        if missing:
            return _error("MISSING_TOOL_PARAMS", f"缺少参数：{sorted(missing)}")
        if extra:
            return _error("EXTRA_TOOL_PARAMS", f"包含多余参数：{sorted(extra)}")

        safe_args: dict[str, str] = {}
        if "order_id" in args:
            normalized = _normalize_order_id(args["order_id"])
            if normalized is None:
                return _error("INVALID_ORDER_ID", "订单号格式应为DD加4位数字")
            safe_args["order_id"] = normalized
        if "user_id" in args:
            normalized = _normalize_user_id(args["user_id"])
            if normalized is None:
                return _error("INVALID_USER_ID", "用户身份格式不正确")
            safe_args["user_id"] = normalized
        if "sku" in args:
            normalized = _normalize_sku(args["sku"])
            if normalized is None:
                return _error("INVALID_SKU", "SKU格式不正确")
            safe_args["sku"] = normalized

        try:
            result = spec.handler(**safe_args)
            if not isinstance(result, ToolResult):
                return _error("INVALID_TOOL_RESULT", "Tool返回结构不符合约定")
            return result
        except Exception as error:
            return _error("TOOL_EXECUTION_ERROR", f"Tool执行异常：{type(error).__name__}")

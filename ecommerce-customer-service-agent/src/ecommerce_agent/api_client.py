from __future__ import annotations

from typing import Any

import requests

from .models import ToolResult


class BusinessAPIClient:
    def __init__(self, base_url: str, token: str, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _get(self, endpoint: str, params: dict[str, Any]) -> ToolResult:
        try:
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
                params=params,
                timeout=self.timeout,
            )
            try:
                payload = response.json()
            except requests.exceptions.JSONDecodeError:
                return ToolResult(
                    False,
                    "INVALID_JSON_RESPONSE",
                    "业务系统返回的不是合法JSON",
                    http_status=response.status_code,
                )
            payload["http_status"] = response.status_code
            return ToolResult.from_mapping(payload)
        except requests.exceptions.Timeout:
            return ToolResult(False, "API_TIMEOUT", "业务API响应超时")
        except requests.exceptions.ConnectionError:
            return ToolResult(False, "API_CONNECTION_ERROR", "无法连接业务API")
        except requests.exceptions.RequestException as error:
            return ToolResult(
                False,
                "API_REQUEST_ERROR",
                f"业务API请求异常：{type(error).__name__}",
            )

    def query_order(self, order_id: str, user_id: str) -> ToolResult:
        return self._get("/api/orders", {"order_id": order_id, "user_id": user_id})

    def query_logistics(self, order_id: str, user_id: str) -> ToolResult:
        return self._get(
            "/api/logistics", {"order_id": order_id, "user_id": user_id}
        )

    def query_inventory(self, sku: str) -> ToolResult:
        return self._get("/api/inventory", {"sku": sku})

    def query_refund(self, order_id: str, user_id: str) -> ToolResult:
        return self._get("/api/refunds", {"order_id": order_id, "user_id": user_id})

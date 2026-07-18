from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


HOST = os.getenv("MOCK_API_HOST", "127.0.0.1")
PORT = int(os.getenv("MOCK_API_PORT", "8765"))
VALID_TOKEN = os.getenv("BUSINESS_API_TOKEN", "demo-token")

ORDERS = {
    "DD1001": {
        "user_id": "U1001",
        "order_id": "DD1001",
        "product_name": "黑色连衣裙 M码",
        "sku": "DRESS-BLACK-M",
        "order_status": "已发货",
        "pay_status": "已支付",
    },
    "DD1002": {
        "user_id": "U1002",
        "order_id": "DD1002",
        "product_name": "白色外套 L码",
        "sku": "COAT-WHITE-L",
        "order_status": "待发货",
        "pay_status": "已支付",
    },
}

LOGISTICS = {
    "DD1001": {
        "order_id": "DD1001",
        "company": "中通快递",
        "tracking_no": "ZT20260708001",
        "logistics_status": "运输中",
        "latest_trace": "快件已到达杭州转运中心",
    }
}

INVENTORY = {
    "DRESS-BLACK-M": {"sku": "DRESS-BLACK-M", "available_stock": 26},
    "COAT-WHITE-L": {"sku": "COAT-WHITE-L", "available_stock": 0},
}

REFUNDS = {
    "DD1001": {"order_id": "DD1001", "refund_status": "无退款申请"},
    "DD1002": {"order_id": "DD1002", "refund_status": "审核中"},
}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def result(success, code, message, data=None):
        return {"success": success, "error_code": code, "message": message, "data": data}

    def do_GET(self):
        if self.headers.get("Authorization") != f"Bearer {VALID_TOKEN}":
            self.send_json(401, self.result(False, "INVALID_TOKEN", "身份认证失败"))
            return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        order_id = params.get("order_id", [""])[0].strip().upper()
        user_id = params.get("user_id", [""])[0].strip().upper()
        sku = params.get("sku", [""])[0].strip().upper()

        if parsed.path in {"/api/orders", "/api/logistics", "/api/refunds"}:
            if not order_id or not user_id:
                self.send_json(400, self.result(False, "MISSING_PARAMS", "缺少订单号或用户身份"))
                return
            order = ORDERS.get(order_id)
            if order is None:
                self.send_json(200, self.result(False, "ORDER_NOT_FOUND", "未找到订单"))
                return
            if order["user_id"] != user_id:
                self.send_json(403, self.result(False, "ACCESS_DENIED", "无权查看该订单"))
                return
            if parsed.path == "/api/orders":
                data = {key: value for key, value in order.items() if key != "user_id"}
            elif parsed.path == "/api/logistics":
                data = LOGISTICS.get(order_id)
            else:
                data = REFUNDS.get(order_id)
            if data is None:
                self.send_json(200, self.result(False, "DATA_NOT_FOUND", "暂未找到相关记录"))
                return
            self.send_json(200, self.result(True, None, "查询成功", data))
            return

        if parsed.path == "/api/inventory":
            if not sku:
                self.send_json(400, self.result(False, "MISSING_SKU", "缺少SKU"))
                return
            data = INVENTORY.get(sku)
            if data is None:
                self.send_json(200, self.result(False, "SKU_NOT_FOUND", "未找到商品"))
                return
            self.send_json(200, self.result(True, None, "查询成功", data))
            return

        self.send_json(404, self.result(False, "API_NOT_FOUND", "接口不存在"))

    def log_message(self, format, *args):
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"模拟电商业务API：http://{HOST}:{PORT}")
    print("演示用户：U1001；演示订单：DD1001")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

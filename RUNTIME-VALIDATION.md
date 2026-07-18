# Docker 运行验收记录

Compose 启动三个服务：

- `ecommerce-agent`：客服 Agent Web 与编排层，宿主机端口 `5000`。
- `ecommerce-mock-api`：订单、物流、库存、退款模拟业务 API，仅容器网络访问。
- `expense-agent`：费用报销预审与审批协同，宿主机端口 `5100`。

`compose.yaml` 已内置独立的模拟 API 服务，并将客服 Agent 的业务接口地址配置为容器网络地址，避免 Web 容器错误访问自身的 `127.0.0.1:8765`。

验收命令：

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

运行验收至少覆盖：

1. 两个 Web 服务健康检查返回 `ok`。
2. 报销金额 680 元、有效员工和新发票号返回“初步通过”。
3. 客服 Agent 首轮缺少订单号时追问，第二轮提供 `DD1001` 后通过 Tool 返回订单状态。
4. 用户 `U2002` 查询 `DD1001` 时返回权限拒绝。

所有数据均为模拟数据，不代表企业生产环境或真实降本结果。

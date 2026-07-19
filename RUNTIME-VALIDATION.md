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

## Dify 1.16.0 本地验收

报销工作流已在本地 Dify `1.16.0` 完成 DSL 导入和发布，Dify 通过 HTTP Request 节点调用宿主机 `5100` 端口的 Python 预审服务。

| 验收项 | 结果 |
|---|---|
| DSL 导入、节点检查和发布 | 通过 |
| 680 元交通费自动预审 | 工作流状态 `succeeded`，输出“初步通过” |
| 3200 元差旅费规则分支 | 正确暂停在“主管或财务人工审批”节点 |
| 人工审批表单 | 正确显示预审结论、风险、原因、建议和“同意/退回”动作 |
| 点击“同意”后的后台输出 | 已产生 `human_action=approve`、预审结论、原因和申请编号 |

本机 Dify `1.16.0` 的独立 Web App 在提交人工动作后，后台已恢复流程并产生完整输出，但前端事件流会显示 `Stopped by user`，后台错误为 `Client response stream closed before app execution completed`。因此当前验收结论是“人工暂停与审批提交可演示，前端完成态仍需在升级 Dify 或修复 SSE 连接后复验”，不把该路径标记为生产就绪。

Dify 的 SSRF 防护没有整体关闭，只对本项目需要的宿主机域名使用最小白名单：

```yaml
services:
  ssrf_proxy:
    environment:
      SSRF_PROXY_ALLOW_PRIVATE_DOMAINS: host.docker.internal
```

所有数据均为模拟数据，不代表企业生产环境或真实降本结果。

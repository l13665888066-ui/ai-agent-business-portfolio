# Dify 工作流导入说明

文件：`expense-approval-workflow.yml`

这份 DSL 是 **补充编排演示**，用于展示表单、HTTP 请求、条件分支和人工节点。完整报销审批由 Python v2 系统负责，Dify 不作为员工身份、预算、申请状态或审计日志的事实源。

## 前置条件

1. 报销 Python 服务运行在宿主机 `5100` 端口。
2. Dify 使用 Docker Desktop 运行。
3. HTTP Request 节点可访问 `host.docker.internal`。

如果 SSRF 代理阻止宿主机访问，只放行本项目需要的域名：

```yaml
services:
  ssrf_proxy:
    environment:
      SSRF_PROXY_ALLOW_PRIVATE_DOMAINS: host.docker.internal
```

不要关闭全部 SSRF 防护，也不要放行所有私网地址。

## 导入

1. 在 Dify 工作室选择“导入 DSL 文件”。
2. 导入 `expense-approval-workflow.yml`。
3. 检查 HTTP 节点地址：

   `http://host.docker.internal:5100/api/precheck`

4. 每次测试使用新的发票号码。

## 建议测试数据

| 场景 | 员工 | 类型 | 金额 | 预期 |
|---|---|---|---:|---|
| 低风险 | E1001 | 办公费 | 680 | 自动预审通过 |
| 主管复核 | E1001 | 差旅费 | 3200 | 进入主管路径 |
| 财务复核 | E1001 | 差旅费 | 6800 | 进入财务路径 |

## 面试讲解边界

- Dify：可视化流程编排和快速原型。
- Python：确定性规则、权限、状态机、预算和审计。
- SQLite：模拟事实数据。
- DeepSeek：材料表达理解，不做最终审批。
- Embedding + Chroma：制度检索，不替代实时数据库。
- 人工：主管/财务高风险审批和异常兜底。

`/api/precheck` 是兼容入口；完整角色切换、待办、退回重提和审计演示请使用 `http://127.0.0.1:5100`。

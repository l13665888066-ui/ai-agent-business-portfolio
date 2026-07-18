# Dify 工作流导入说明

文件：`expense-approval-workflow.yml`

## 前置条件

1. 报销审批 Python 服务运行在宿主机 `5100` 端口。
2. Dify 使用 Docker Desktop 运行。
3. Dify 的 HTTP Request 节点能访问 `host.docker.internal`。

## 导入和验证

1. 在 Dify 工作室选择“导入 DSL 文件”。
2. 导入 `expense-approval-workflow.yml`。
3. 检查“Python预审API”节点的地址：

   `http://host.docker.internal:5100/api/precheck`

4. 使用下面三组数据验证：

| 场景 | 员工 | 类型 | 金额 | 发票号 | 预期 |
|---|---|---:|---:|---|---|
| 低风险 | E1001 | 交通费 | 680 | DIFY-001 | 初步通过，自动输出 |
| 主管复核 | E1001 | 差旅费 | 3200 | DIFY-002 | 进入人工审批 |
| 异常员工 | E1003 | 交通费 | 300 | DIFY-003 | 高风险人工复核 |

日期可填写 `2026-07-01`，用途可填写“客户拜访交通费用”。每次测试使用新的发票号，避免触发重复发票规则。

## 面试讲解边界

工作流不会让大模型自由判断金额是否合规。Dify负责流程编排，Python规则层负责确定性决策，人工节点负责高风险审批；接口超时、非JSON响应和审批超时均进入兜底路径。

此 DSL 依据 Dify 官方工作流、HTTP、代码、条件分支和人工输入样例编写。导入后的节点版本可能随 Dify 版本升级而自动迁移。

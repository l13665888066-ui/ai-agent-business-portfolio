# 运行验收记录

更新时间：2026-07-26

## 自动化测试

| 项目 | 结果 |
|---|---:|
| 直播电商智能客服 Agent | `28/28` |
| 企业费用报销审批 Agent | `20/20` |
| 合计 | `48/48` |

测试命令：

```powershell
cd ecommerce-customer-service-agent
python -m unittest discover -s tests -v

cd ..\expense-approval-agent
python -m unittest discover -s tests -v
```

## 财务审批浏览器闭环

已按真实界面完成以下操作：

1. 员工 `E1001` 提交 3200 元差旅费，状态为 `pending_manager`。
2. 主管 `M2001` 的待办只出现直属员工申请。
3. 主管未填写意见直接退回时，系统拦截。
4. 填写原因后退回，状态变为 `returned`，审批时间线写入退回动作。
5. 员工补充用途说明并重新提交，状态重新进入 `pending_manager`。
6. 主管同意后状态变为 `approved`，员工申请记录显示“已通过”。
7. 申请详情保留提交、退回、重提、审批动作和操作人。

## AI 与 RAG 联网验收

在不输出密钥的前提下，已验证：

- DeepSeek 模型返回 `mode=llm` 的材料摘要和补充建议。
- 系统摘要由已提交事实生成，模型输出还要经过事实一致性过滤。
- 阿里云 `text-embedding-v4` 成功生成向量。
- Chroma 以余弦距离召回制度，并通过费用类型关键词重排。
- “差旅费、杭州、住宿、高铁”查询首位返回“差旅费规则”。
- 外部调用失败时进入 `rule_fallback_after_llm_error` 或 `local_fallback`，页面明确显示兜底来源。

## Docker 验收口径

Compose 定义三个服务：

- `ecommerce-agent`
- `ecommerce-mock-api`
- `expense-agent`

验收命令：

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

两个 Web 健康检查应返回 `status=ok`。密钥只通过运行环境注入，`.env` 不进入镜像。

## Dify 边界

Dify DSL 保留为可视化编排补充材料，用于展示 HTTP、条件分支和人工节点。旧版独立 Web App 的前端完成态不再作为项目最终验收证据。v2 Python 页面、SQLite 状态机、角色权限、预算占用和审计时间线才是当前可演示的完整闭环。

## 真实性声明

所有员工、订单、预算、票据和申请均为模拟数据，不代表企业生产环境或真实降本结果。当前验收证明的是业务拆解、原型实现、异常控制、测试与工程化交付能力。

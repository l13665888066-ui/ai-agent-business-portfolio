# 架构与关键决策

## 为什么采用受控 Agent

客服场景同时包含自然对话、制度问答和实时订单事实。模型适合理解语言，不适合直接授权、查询任意用户订单或编造实时状态。因此项目把“理解”和“执行”分开：

```text
自然会话 -> Router -> RAG / Tool / 人工
                        |
                 代码层白名单与参数
                        |
                 业务API身份与归属
```

## 模块职责

1. `responder.py / safe_responder.py`：处理自然会话并将结构化结果转成客服表达。
2. `policy_router.py / router.py`：区分规则问答、具体订单Tool和人工；LLM失败时规则降级。
3. `knowledge.py / rag.py`：Embedding批量调用、Chroma去重构建、阈值过滤和关键词兜底。
4. `tools.py`：白名单、参数schema和统一Tool返回。
5. `api_client.py`：调用模拟业务API并统一网络/业务错误。
6. `memory.py / conversation_workflow.py`：pending action、最近已验证订单、TTL、session与user隔离。
7. `workflow.py / production.py`：固定执行顺序与降级策略。
8. `audit.py`：记录路径、错误码和耗时，递归脱敏。

## 规则问题与实时查询分流

```text
“一般多久发货？” -> RAG制度问答
“我的订单发货了吗？” -> 缺参追问 -> 订单Tool
“DD1001” -> 恢复pending订单查询
“多久能到？” -> 复用最近已验证订单 -> 物流Tool
```

只有已通过业务API归属校验的订单才可写入active order上下文。

## 多轮上下文

- `pending action` 保存未完成意图和缺少参数。
- Tool失败时保留意图，允许用户补正。
- active order设置TTL；过期后重新追问。
- session不同或当前user不同，旧上下文不可复用。
- 不把所有聊天历史无限拼入模型。

## 权限边界

Router不负责授权。程序注入当前用户ID，业务API再次校验订单归属。即使模型或用户提供他人订单号，也返回 `ACCESS_DENIED`。日志保留错误码用于定位，但不记录密钥和敏感身份字段。

## RAG工程控制

- 遵守Embedding服务单次批量限制。
- 使用稳定ID和集合清理避免重复文档。
- Top-K和阈值只是测试起点，需要真实问法评测。
- 外部Embedding失败时明确进入关键词兜底。

## 生产化差距

- Redis/数据库持久化会话、幂等与并发控制。
- OAuth/企业SSO提供可信身份。
- 抖店、ERP或客服系统正式API。
- 限流、监控、告警、日志检索和链路追踪。
- 知识版本、离线评测、灰度发布和回滚。
- 客服工作台、人工接管队列和服务SLA。

# 测试报告

更新时间：2026年7月26日

## 结果

```text
Ran 28 tests
OK
```

命令：

```powershell
python -m unittest discover -s tests -v
```

## 覆盖范围

### 自然会话与分流

- 常见及非固定问候进入友好会话层。
- 通用发货规则进入知识问答。
- 具体订单发货问题进入Tool或缺参追问。
- LLM不可用时安全降级。

### 多轮上下文

- 缺订单号后下一轮补参。
- Tool失败后保留原意图。
- 最近已验证订单可被后续物流问法复用。
- active order TTL过期后不再复用。
- session隔离和user隔离。

### RAG

- 关键词与向量知识路径。
- Embedding服务批量限制。
- 向量库重复构建不产生重复条目。
- 向量失败时本地知识兜底。

### Tool与权限

- 订单、物流、库存和退款Tool。
- 非白名单Tool拦截。
- 订单归属校验与`ACCESS_DENIED`。
- 业务错误与连接异常统一返回。

### 审计

- 每条事件按JSONL追加。
- token、authorization、api_key、secret等字段递归脱敏。
- session、user、路径、Tool、错误码和耗时可追踪。

## 验收标准

- 测试由程序断言，不以“终端没报错”为通过。
- Tool统一返回`success/error_code/message/data`。
- 失败路径不得编造订单、物流、库存或退款信息。
- 只有已验证归属的订单可以写入上下文。
- 外部AI失败必须有明确降级，不冒充真实模型结果。

## 仍需生产环境补充

- 真实平台401/429/5xx、回调签名和Token刷新。
- Redis并发会话与幂等。
- 端到端监控、告警和压测。
- 真实客服问法评测集与人工接管SLA。

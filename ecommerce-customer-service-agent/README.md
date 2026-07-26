# 直播电商智能客服 Agent

面向直播电商客服、订单、物流、库存、退款和投诉场景的个人业务原型。项目使用模拟业务数据，未接入抖店正式接口，也未在企业生产环境上线。

## 项目价值

这不是只靠关键词回复的 FAQ，也不是让大模型自由访问订单系统。系统先承接真实客服中的问候和口语表达，再区分制度问题与具体订单问题；只有实时事实查询才进入受控 Tool。

```text
用户消息
  -> 自然会话层（问候、感谢、能力询问）
  -> session上下文与最近已验证订单
  -> LLM Router（失败时规则路由降级）
      ├─ 通用发货/退货规则 -> RAG
      ├─ 具体订单/物流/库存/退款 -> Tool
      ├─ 缺少订单号 -> pending action追问
      └─ 投诉、争议、低置信度 -> 人工转接
  -> 白名单、参数、身份和订单归属校验
  -> 结构化结果、友好回复和脱敏审计日志
```

## 已实现能力

### 自然会话与意图分流

- 通过模型语义理解承接问候、口语、网络表达和能力询问，不依赖有限关键词枚举。
- 模型不可用时保留保守的小对话兜底。
- 区分“通常多久发货”与“我的订单发货了吗”：前者查制度知识，后者需要订单号并调用 Tool。
- LLM Router 返回非法 JSON、超时或低置信度时，规则路由接管；不会把普通问候直接送入“知识库未命中”。

### 多轮订单上下文

- 首轮缺少订单号时保存 `pending action`，下一轮只输入 `DD1001` 可恢复原意图。
- 查询成功后保存最近一次**已验证归属**的订单；用户继续问“多久能到”时可以复用，不重复追问订单号。
- Tool失败后保留原意图，让用户修正订单号后继续，而不是把会话重置成无关问题。
- 会话具有 TTL、session 隔离和 user 隔离；过期或换用户后不能复用旧订单。

### RAG与知识库

- 使用阿里云 Embedding + Chroma 向量检索，外部服务失败时进入关键词检索兜底。
- Embedding 请求按服务批量上限分组，避免一次提交过多文本。
- 使用稳定文档 ID 和清理策略避免重复构建造成向量条目叠加。
- 使用 Top-K、相似度阈值与业务路由共同控制召回；低相关结果不强答。

### Tool、API与安全

- 订单、物流、库存、退款4类模拟业务 Tool。
- Tool 白名单、参数类型、格式和额外字段校验。
- 当前 `user_id` 由系统注入，不信任模型或用户自行提供。
- 订单归属由模拟业务 API 校验，跨用户查询返回 `ACCESS_DENIED`。
- HTTP超时、连接失败、非法响应和业务错误统一映射。
- 投诉、高风险争议和连续失败进入人工转接。

### 工程与审计

- JSONL 审计日志记录 session、user、路由路径、Tool、错误码和耗时。
- `token / authorization / api_key / secret` 等字段递归脱敏。
- Flask 客服访问页面和独立模拟业务 API。
- Dockerfile、Compose、README、架构和测试报告。

## 快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

分别启动：

```powershell
python mock_business_api.py
python web_app.py
```

浏览器访问 `http://127.0.0.1:5000`。

离线情况下，系统使用规则 Router 与关键词知识兜底；配置 DeepSeek 和 Embedding 后使用真实语义路由与向量 RAG。

## 演示账号

- 当前用户：`U1001`
- 当前用户订单：`DD1001`
- 其他用户订单：`DD1002`（用于演示权限拒绝）
- 有库存 SKU：`DRESS-BLACK-M`

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前 `28/28` 项通过，覆盖自然会话、通用发货规则与具体订单分流、LLM/向量降级、Embedding批量限制、向量去重、多轮补参、失败后保留意图、最近订单复用、TTL、session/user隔离、订单归属、Tool白名单和审计脱敏。

## 项目边界

- 订单、物流、库存和退款均为模拟 API。
- 页面身份是演示身份；生产系统应由 SSO 或网关注入可信用户。
- 未实现真实抖店签名、Token刷新、平台限流与回调。
- 内存会话适合本地原型；生产需要 Redis/数据库、幂等、监控和容量评估。
- 向量阈值需要真实问法评测集持续校准。
- 没有企业生产上线或真实降本数据。

更多说明见 [`docs/architecture.md`](docs/architecture.md) 和 [`docs/test-report.md`](docs/test-report.md)。

# 直播电商智能客服 Agent

面向直播电商客服、订单、物流、库存和售后场景的个人业务原型。项目使用模拟业务数据，未接入抖店正式接口，也未在企业生产环境上线。

## 项目价值

这个项目不是单纯的FAQ机器人，而是一条受控业务链路：大模型负责理解问题和建议路径，程序负责校验、执行和兜底，业务数据只能通过白名单Tool获取。

```text
用户问题
  -> LLM Router（异常时规则路由降级）
  -> 人工转接 / 缺参追问 / Tool / RAG
  -> 权限校验与统一结果
  -> 多轮上下文与审计日志
```

## 已实现能力

- DeepSeek + LangChain JSON路由
- Chroma向量检索与RAG阈值过滤
- 订单、物流、库存、退款4类业务Tool
- Tool白名单、参数类型/格式/额外字段校验
- 订单归属校验，阻止跨用户查询
- 缺参追问与下一轮参数续接
- 按session隔离上下文，降低串单风险
- 路由异常时离线规则降级
- HTTP超时、连接失败和业务错误标准化
- JSONL审计日志（敏感字段脱敏）
- Flask演示界面
- 标准库 `unittest` 自动化测试

## 快速启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中配置模型与Embedding服务。随后分别启动：

```powershell
python mock_business_api.py
python web_app.py
```

浏览器访问 `http://127.0.0.1:5000`。

离线情况下，系统会使用规则路由与关键词知识兜底；配置模型后使用LLM Router和向量RAG。

## 演示账号

- 当前用户：`U1001`
- 当前用户订单：`DD1001`
- 其他用户订单：`DD1002`（用于演示权限拒绝）
- 有库存SKU：`DRESS-BLACK-M`

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试覆盖RAG、投诉转人工、多轮缺参续接、会话隔离、订单归属、物流、库存和非法Tool拦截。

## 项目边界

- 当前API、订单和库存均为模拟数据。
- 当前用户身份由演示页面传入；生产系统应接入统一身份认证。
- 向量阈值需要结合真实问法和评测集持续校准。
- 上线前仍需补充限流、监控、持久化会话、密钥托管和正式业务接口联调。

更多说明见 `docs/architecture.md` 和 `docs/test-report.md`。

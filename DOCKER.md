# Docker 本地运行说明

## 1. 环境配置

在仓库根目录复制配置模板：

```powershell
Copy-Item .env.example .env
```

填写以下可选配置：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `ALIYUN_API_KEY`
- `ALIYUN_EMBEDDING_BASE_URL`
- `EMBEDDING_MODEL`

不填写也能启动，财务系统会进入本地规则和关键词检索兜底。`.env` 已被 Git 忽略；Docker 构建上下文也明确排除 `.env`，不会把密钥打进镜像。

## 2. 启动

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

访问地址：

- 直播电商智能客服：`http://127.0.0.1:5000`
- 企业费用报销审批：`http://127.0.0.1:5100`

健康检查：

```powershell
curl.exe http://127.0.0.1:5000/health
curl.exe http://127.0.0.1:5100/health
```

停止：

```powershell
docker compose down
```

## 3. 服务职责

- `ecommerce-agent`：客服页面、Router、RAG、Tool 编排、会话与审计。
- `ecommerce-mock-api`：模拟订单、物流、库存、退款业务 API，仅容器网络访问。
- `expense-agent`：报销页面、角色权限、规则预审、审批状态机、AI 材料理解、制度检索与审计。

两个命名卷只保存运行期模拟数据，不包含真实客户、员工、订单或财务数据。

## 4. Dify 对接

Dify 作为补充可视化工作流，通过以下兼容地址调用 Python 预审：

```text
http://host.docker.internal:5100/api/precheck
```

Dify 不承担 v2 系统的身份权限、预算占用、完整审批状态和审计事实。正式页面统一使用 `/api/applications` 及审批动作接口。

## 5. 生产化差距

本 Compose 只用于本地交付验证。生产环境仍需：

- 企业镜像仓库与漏洞扫描。
- 非 root 运行、密钥托管和网络策略。
- 企业数据库、备份恢复和迁移机制。
- SSO、RBAC、API 网关与请求签名。
- 集中日志、指标、告警和链路追踪。
- 灰度发布、回滚、容量与故障演练。

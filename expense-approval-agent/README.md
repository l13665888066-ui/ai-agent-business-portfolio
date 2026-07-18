# 企业费用报销预审与审批协同 Agent

个人业务原型，用于展示企业内部审批流程自动化。项目使用模拟员工、预算和报销数据，未接入真实财务系统。

## 核心流程

```text
结构化报销表单
  -> 必填字段校验
  -> 员工状态查询
  -> 重复发票检查
  -> 部门预算查询
  -> 确定性金额与风险规则
  -> 低风险初步通过 / 主管复核 / 财务复核
  -> SQLite申请记录与审计日志
```

大模型适合材料理解与制度解释，但不直接决定高风险审批。金额阈值、员工状态、预算、重复发票和人工节点由程序规则控制。

## 已实现能力

- Flask Web 演示与 `/api/precheck` 接口。
- SQLite 员工、预算、申请和审计数据层。
- 必填字段、金额、员工状态、费用类型、重复发票和预算规则。
- 低风险、主管复核、财务复核与异常兜底。
- 报销制度关键词检索与制度来源返回。
- 7个自动化测试。
- Dockerfile 与根目录 Compose 编排。
- Dify 0.6.0 DSL：HTTP、代码解析、条件分支和人工审批节点。

## Docker 运行

在仓库根目录执行：

```powershell
docker compose up --build -d
```

访问 `http://127.0.0.1:5100`。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Dify 导入

导入文件：[`dify/expense-approval-workflow.yml`](dify/expense-approval-workflow.yml)

详细步骤与测试数据：[`dify/README.md`](dify/README.md)

Dify 容器通过下面的地址访问宿主机规则服务：

```text
http://host.docker.internal:5100/api/precheck
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 项目边界

- 使用模拟企业制度、员工、预算和发票数据。
- 当前为个人原型，不代表正式财务付款承诺。
- 生产落地仍需统一身份认证、正式财务接口、权限矩阵、发票验真、密钥托管、监控告警和数据合规评审。

# Docker 本地运行说明

## 启动两个业务原型

在仓库根目录执行：

```powershell
docker compose up --build -d
docker compose ps
```

访问地址：

- 直播电商智能客服 Agent：`http://127.0.0.1:5000`
- 企业费用报销审批 Agent：`http://127.0.0.1:5100`

健康检查：

```powershell
curl.exe http://127.0.0.1:5000/health
curl.exe http://127.0.0.1:5100/health
```

停止服务：

```powershell
docker compose down
```

两个命名卷只保存运行期演示数据，不包含真实客户、员工、订单或财务数据。

## Dify 对接

Dify 运行在 Docker 内时，工作流通过下面的宿主机地址调用报销规则服务：

```text
http://host.docker.internal:5100/api/precheck
```

该设计把职责分开：

- Dify：表单入口、流程编排、条件分支、人工审批与结果展示。
- Python：必填校验、员工状态、预算、重复发票、金额阈值和审计日志。
- SQLite：模拟企业员工、预算、报销申请和审计事实数据。

这是个人业务原型和本地工程化演示，不代表企业生产部署。

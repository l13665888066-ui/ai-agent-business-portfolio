# 企业费用报销预审与审批协同 Agent

个人业务原型，用于展示企业内部审批流程自动化。项目使用模拟员工、预算和报销数据，未接入真实财务系统。

## 关键设计

```text
表单或Dify结构化提取
  -> 必填字段校验
  -> 员工状态查询
  -> 重复发票检查
  -> 部门预算查询
  -> 确定性审批规则
  -> 主管/财务人工节点
  -> SQLite申请与审计日志
```

大模型适合提取材料和解释制度，但不直接决定高风险审批。金额阈值、员工状态、预算、重复发票和人工审批由程序硬规则控制。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

访问 `http://127.0.0.1:5100`。

演示员工：

- `E1001`：销售部在职员工，预算充足。
- `E1002`：市场部在职员工，剩余预算较少。
- `E1003`：非在职员工，用于异常测试。

## 测试

```powershell
python -m unittest discover -s tests -v
```

## Dify接入

后续在Dify Workflow中完成材料结构化提取和制度知识库检索，再通过HTTP节点调用本项目的 `/api/precheck`。具体节点见 `docs/dify-workflow.md`。

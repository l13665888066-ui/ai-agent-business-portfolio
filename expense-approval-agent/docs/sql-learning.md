# 财务审批项目中的基础 SQL

项目包含 6 类表：员工、预算、附件、申请、审批动作、审计日志。

## 查询员工与角色

```sql
SELECT employee_id, name, role, department, manager_id, active
FROM employees
WHERE employee_id = ?;
```

## 查询部门预算

```sql
SELECT monthly_budget, used_amount
FROM budgets
WHERE department = ?;
```

## 检查重复发票

```sql
SELECT id, status
FROM applications
WHERE invoice_no = ?;
```

## 查询直属主管待办

```sql
SELECT id, employee_id, amount, status
FROM applications
WHERE manager_id = ?
  AND status = 'pending_manager'
ORDER BY created_at DESC;
```

## 财务待办

```sql
SELECT id, employee_id, department, amount, status
FROM applications
WHERE status = 'pending_finance'
ORDER BY created_at DESC;
```

## 防止并发超扣预算

```sql
UPDATE budgets
SET used_amount = used_amount + ?
WHERE department = ?
  AND monthly_budget - used_amount >= ?;
```

只有受影响行数为 1 时，预算占用才成功。

## 审批时间线

```sql
SELECT actor_id, actor_role, action, comment, created_at
FROM approval_actions
WHERE application_id = ?
ORDER BY id;
```

## 基础原则

- 所有用户输入都使用参数化查询，不能直接拼接 SQL。
- 申请状态变化和预算占用需要在事务中完成。
- 生产系统还需要数据库账号最小权限、备份恢复、迁移脚本和审计留存策略。

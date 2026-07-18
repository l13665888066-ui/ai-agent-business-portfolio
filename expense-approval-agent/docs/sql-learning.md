# 项目中的基础SQL

## 查询员工

```sql
SELECT * FROM employees WHERE employee_id = ?;
```

## 查询部门预算

```sql
SELECT monthly_budget, used_amount
FROM budgets
WHERE department = ?;
```

## 检查重复发票

```sql
SELECT 1 FROM applications WHERE invoice_no = ?;
```

## 查看待人工审批申请

```sql
SELECT id, employee_id, amount, decision, status
FROM applications
WHERE status = 'pending'
ORDER BY created_at DESC;
```

项目使用参数化查询，避免把用户输入直接拼接进SQL。

# PostgreSQL SQL Queries (continued 2/2)

## Aggregate Functions

### Basic Aggregates
```sql
-- COUNT, SUM, AVG, MIN, MAX
SELECT
  COUNT(*) AS total_orders,
  SUM(total) AS total_revenue,
  AVG(total) AS avg_order_value,
  MIN(total) AS min_order,
  MAX(total) AS max_order
FROM orders;

-- COUNT variations
SELECT COUNT(*) FROM users;              -- All rows
SELECT COUNT(phone_number) FROM users;   -- Non-NULL values
SELECT COUNT(DISTINCT status) FROM orders; -- Unique values
```

### GROUP BY
```sql
-- Aggregate by groups
SELECT status, COUNT(*) AS count
FROM orders
GROUP BY status;

-- Multiple grouping columns
SELECT customer_id, status, COUNT(*) AS count
FROM orders
GROUP BY customer_id, status;

-- With aggregate functions
SELECT customer_id,
  COUNT(*) AS order_count,
  SUM(total) AS total_spent,
  AVG(total) AS avg_order
FROM orders
GROUP BY customer_id;
```

### HAVING
```sql
-- Filter after aggregation
SELECT customer_id, SUM(total) AS total_spent
FROM orders
GROUP BY customer_id
HAVING SUM(total) > 1000;

-- Multiple conditions
SELECT status, COUNT(*) AS count
FROM orders
GROUP BY status
HAVING COUNT(*) > 10;
```

## Window Functions

### ROW_NUMBER
```sql
-- Assign unique number to each row
SELECT id, name, salary,
  ROW_NUMBER() OVER (ORDER BY salary DESC) AS rank
FROM employees;

-- Partition by group
SELECT id, department, salary,
  ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank
FROM employees;
```

### RANK / DENSE_RANK
```sql
-- RANK: gaps in ranking for ties
-- DENSE_RANK: no gaps
SELECT id, name, salary,
  RANK() OVER (ORDER BY salary DESC) AS rank,
  DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank
FROM employees;
```

### LAG / LEAD
```sql
-- Access previous/next row
SELECT date, revenue,
  LAG(revenue) OVER (ORDER BY date) AS prev_revenue,
  LEAD(revenue) OVER (ORDER BY date) AS next_revenue,
  revenue - LAG(revenue) OVER (ORDER BY date) AS change
FROM daily_sales;
```

### Running Totals
```sql
-- Cumulative sum
SELECT date, amount,
  SUM(amount) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total
FROM transactions;

-- Simpler syntax
SELECT date, amount,
  SUM(amount) OVER (ORDER BY date) AS running_total
FROM transactions;
```

### Moving Averages
```sql
-- 7-day moving average
SELECT date, value,
  AVG(value) OVER (
    ORDER BY date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS moving_avg_7d
FROM metrics;
```

## Advanced Patterns

### CASE Expressions
```sql
-- Simple CASE
SELECT name,
  CASE status
    WHEN 'active' THEN 'Active User'
    WHEN 'pending' THEN 'Pending Verification'
    ELSE 'Inactive'
  END AS status_label
FROM users;

-- Searched CASE
SELECT name, age,
  CASE
    WHEN age < 18 THEN 'Minor'
    WHEN age BETWEEN 18 AND 65 THEN 'Adult'
    ELSE 'Senior'
  END AS age_group
FROM users;
```

### COALESCE
```sql
-- Return first non-NULL value
SELECT name, COALESCE(phone_number, email, 'No contact') AS contact
FROM users;
```

### NULLIF
```sql
-- Return NULL if values equal
SELECT name, NULLIF(status, 'deleted') AS active_status
FROM users;
```

### Array Operations
```sql
-- Array aggregate
SELECT customer_id, ARRAY_AGG(product_id) AS products
FROM order_items
GROUP BY customer_id;

-- Unnest array
SELECT unnest(ARRAY[1, 2, 3, 4, 5]);

-- Array contains
SELECT * FROM products WHERE tags @> ARRAY['featured'];
```

### JSON Operations
```sql
-- Query JSON/JSONB
SELECT data->>'name' AS name FROM documents;
SELECT data->'address'->>'city' AS city FROM documents;

-- Check key exists
SELECT * FROM documents WHERE data ? 'email';

-- JSONB operators
SELECT * FROM documents WHERE data @> '{"status": "active"}';

-- JSON aggregation
SELECT json_agg(name) FROM users;
SELECT json_object_agg(id, name) FROM users;
```

## Set Operations

### UNION
```sql
-- Combine results (removes duplicates)
SELECT name FROM customers
UNION
SELECT name FROM suppliers;

-- Keep duplicates
SELECT name FROM customers
UNION ALL
SELECT name FROM suppliers;
```

### INTERSECT
```sql
-- Common rows
SELECT email FROM users
INTERSECT
SELECT email FROM subscribers;
```

### EXCEPT
```sql
-- Rows in first query but not second
SELECT email FROM users
EXCEPT
SELECT email FROM unsubscribed;
```

## Best Practices

1. **Use indexes** on WHERE, JOIN, ORDER BY columns
2. **Avoid SELECT *** - specify needed columns
3. **Use EXISTS** instead of IN for large subqueries
4. **Filter early** - WHERE before JOIN when possible
5. **Use CTEs** for readability over nested subqueries
6. **Parameterize queries** - prevent SQL injection
7. **Use window functions** instead of self-joins
8. **Test with EXPLAIN** - analyze query plans

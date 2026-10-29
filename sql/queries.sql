-- Q1 — WHERE then HAVING
SELECT
    customer_id,
    SUM(order_amount) AS total_qualifying_spend
FROM orders
WHERE LOWER(status) = 'completed'
  AND order_amount > 500
GROUP BY customer_id
HAVING SUM(order_amount) > 8000
ORDER BY total_qualifying_spend DESC, customer_id;

-- Q2 — Three-table join: revenue by city and product category
SELECT
    c.city,
    p.category,
    ROUND(SUM(o.order_amount), 2) AS revenue
FROM orders AS o
JOIN customers AS c
  ON c.customer_id = o.customer_id
JOIN products AS p
  ON p.product_id = o.product_id
WHERE LOWER(o.status) = 'completed'
GROUP BY c.city, p.category
ORDER BY c.city, p.category;

-- Q3 — Scalar subquery: products priced above average catalogue price
SELECT
    product_id,
    product_name,
    price_inr
FROM products
WHERE price_inr > (
    SELECT AVG(price_inr)
    FROM products
)
ORDER BY price_inr DESC, product_id;

-- Q4 — LEFT JOIN: customers with no completed order
SELECT
    c.customer_id,
    c.city
FROM customers AS c
LEFT JOIN orders AS o
  ON o.customer_id = c.customer_id
 AND LOWER(o.status) = 'completed'
WHERE o.order_id IS NULL
ORDER BY c.customer_id;

-- Q5 — CTEs: customer completed spend and average customer spend
WITH customer_spend AS (
    SELECT
        customer_id,
        SUM(order_amount) AS total_spend
    FROM orders
    WHERE LOWER(status) = 'completed'
    GROUP BY customer_id
),
average_spend AS (
    SELECT AVG(total_spend) AS avg_spend
    FROM customer_spend
)
SELECT
    cs.customer_id,
    ROUND(cs.total_spend, 2) AS total_spend,
    ROUND(a.avg_spend, 2) AS average_spend
FROM customer_spend AS cs
CROSS JOIN average_spend AS a
WHERE cs.total_spend > a.avg_spend
ORDER BY cs.total_spend DESC, cs.customer_id;

-- Q6 — Ranking window functions: spend rank within each city
WITH customer_spend AS (
    SELECT
        c.customer_id,
        c.city,
        SUM(o.order_amount) AS total_spend
    FROM orders AS o
    JOIN customers AS c
      ON c.customer_id = o.customer_id
    WHERE LOWER(o.status) = 'completed'
    GROUP BY c.customer_id, c.city
)
SELECT
    customer_id,
    city,
    ROUND(total_spend, 2) AS total_spend,
    RANK() OVER (
        PARTITION BY city
        ORDER BY total_spend DESC
    ) AS spend_rank,
    DENSE_RANK() OVER (
        PARTITION BY city
        ORDER BY total_spend DESC
    ) AS dense_spend_rank,
    ROW_NUMBER() OVER (
        PARTITION BY city
        ORDER BY total_spend DESC, customer_id
    ) AS spend_row_number
FROM customer_spend
ORDER BY city, spend_rank, customer_id;

-- Q7 — Running total of daily completed revenue
WITH daily_revenue AS (
    SELECT
        SUBSTR(order_ts, 1, 10) AS day,
        SUM(order_amount) AS revenue
    FROM orders
    WHERE LOWER(status) = 'completed'
    GROUP BY SUBSTR(order_ts, 1, 10)
)
SELECT
    day,
    ROUND(revenue, 2) AS revenue,
    ROUND(
        SUM(revenue) OVER (
            ORDER BY day
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ),
        2
    ) AS cumulative_revenue
FROM daily_revenue
ORDER BY day;

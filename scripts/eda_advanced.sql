USE SQLDataWarehouse;
GO

/* ============================================================
   1. CHANGE OVER TIME ANALYSIS
   ============================================================ */

   -- Year Analysis

   SELECT
   YEAR(order_date) as order_year,
   SUM(sales_amount) as total_sales,
   count(DISTINCT customer_key) as total_customers,
   SUM(quantity) as total_quantity
   FROM gold.fact_sales
   WHERE order_date IS NOT NULL AND Year(order_date) <= YEAR(GETDATE())
   GROUP BY YEAR(order_date)
   ORDER BY YEAR(order_date);
   GO

   -- Month Analysis

   SELECT
   DATETRUNC(month,order_date) as order_Month,
   SUM(sales_amount) as total_sales,
   count(DISTINCT customer_key) as total_customers,
   SUM(quantity) as total_quantity
   FROM gold.fact_sales
   WHERE order_date IS NOT NULL AND Year(order_date) <= YEAR(GETDATE())
   GROUP BY  DATETRUNC(month,order_date)
   ORDER BY  DATETRUNC(month,order_date);
   GO

/* ============================================================
    2. CUMULATIVE ANALYSIS
============================================================ */

--  Running Total Sales and Moving Average

SELECT
		order_date,
		total_sales,
		SUM(total_sales) OVER (PARTITION BY YEAR(order_date) ORDER BY order_date) AS running_total_sales,
		AVG(avg_price) OVER (ORDER BY order_date) AS moving_average
FROM
   (
   SELECT
   DATETRUNC(month,order_date) as order_date,
   SUM(sales_amount) as total_sales,
   AVG(price) as avg_price
   FROM gold.fact_sales
   WHERE order_date IS NOT NULL AND Year(order_date) <= YEAR(GETDATE())
   GROUP BY  DATETRUNC(month,order_date)
)t;

GO

/* ============================================================
    3. PERFORMANCE ANALYSIS
============================================================ */

/* Analyse the yearly performance of products by comparing their sales to both the average sales performance of the 
product and the previous year's sales */
WITH yearly_product_sales AS(
SELECT
	YEAR(f.order_date) AS order_year,
	p.product_name,
	SUM(f.sales_amount) AS current_sales
	FROM gold.fact_sales f
	LEFT JOIN gold.dim_products p
	ON f.product_key = p.product_key
	WHERE f.order_date IS NOT NULL AND YEAR(f.order_date) <=YEAR(GETDATE())
	GROUP BY YEAR(f.order_date), p.product_name
	)
SELECT
	order_year,
	product_name,
	current_sales,
	AVG(current_sales) OVER (PARTITION BY product_name) avg_sales,
	current_sales - AVG(current_sales) OVER (PARTITION BY product_name) AS diff_avg,
	CASE WHEN current_sales - AVG(current_sales) OVER (PARTITION BY product_name) > 0 THEN 'Above Average'
		 WHEN current_sales - AVG(current_sales) OVER (PARTITION BY product_name) < 0 THEN 'Below Average'
		 ELSE 'Average'
	END Average_Change,
	LAG(current_sales) OVER(PARTITION BY product_name ORDER BY order_year) Previous_Sales,
	current_sales - LAG(current_sales) OVER(PARTITION BY product_name ORDER BY order_year) AS Difference_Sales,
	CASE WHEN current_sales - LAG(current_sales) OVER(PARTITION BY product_name ORDER BY order_year) > 0 THEN 'Increase'
		 WHEN current_sales - LAG(current_sales) OVER(PARTITION BY product_name ORDER BY order_year) < 0 THEN 'Decrease'
		 ELSE 'No Change'
	END Previous_Change
FROM yearly_product_sales
ORDER BY product_name, order_year;
GO

/* ============================================================
    4. PART-TO-WHOLE ANALYSIS
============================================================ */

-- Which categories contribute the most to overall sales
WITH category_sales AS(
SELECT
	category,
	SUM(sales_amount) total_sales
FROM gold.fact_sales f
LEFT JOIN gold.dim_products p
ON p.product_key = f.product_key
GROUP BY category 
)
SELECT
	category,
	total_sales,
	SUM(total_sales) OVER() overall_sales,
	CONCAT(ROUND((CAST(total_sales AS FLOAT)/ SUM(total_sales) OVER())*100,2),'%') AS percentage_of_total
FROM category_sales
ORDER BY total_sales DESC;
GO

/* ============================================================
    5. DATA SEGMENTATION
============================================================ */

/*
Segment products into cost ranges and count how many products fall into each segment
*/
WITH product_segment AS
(SELECT
	product_key,
	product_name,
	cost,
	CASE WHEN cost < 100 THEN 'BELOW 100'
		 WHEN cost BETWEEN 100 AND 500 THEN '100-500'
		when cost BETWEEN 500 AND 1000 THEN '500-1000'
		ELSE 'ABOVE 1000'
		END cost_range
FROM gold.dim_products
)
SELECT
	cost_range,
	COUNT(product_key) AS total_products
FROM product_segment
GROUP BY cost_range
ORDER BY total_products DESC;
GO

/*
Group customers into three segments based on spending:
VIP: >=12 Months and spend more than 5000
REGULAR: >= 12 Months but spend 5000 or less
NEW: <12 Months
*/
WITH customer_spending AS
(
SELECT
	c.customer_key,
	SUM(f.sales_amount) AS total_spending,
	MIN(order_date) AS first_order,
	MAX(order_date) AS last_order,
	DATEDIFF(month, MIN(order_date), MAX(order_date)) AS lifespan
FROM gold.fact_sales f
LEFT JOIN gold.dim_customers c
ON f.customer_key = c.customer_key
GROUP BY c.customer_key
)

SELECT
	customer_segment,
	COUNT(customer_key) AS total_customers
FROM
(SELECT
	customer_key,
	CASE WHEN lifespan >= 12 AND total_spending > 5000 THEN 'VIP'
		 WHEN lifespan >= 12 AND total_spending <= 5000 THEN 'REGULAR'
		 ELSE 'NEW'
	END customer_segment
FROM customer_spending) ts
GROUP BY customer_segment
ORDER BY total_customers DESC;

GO
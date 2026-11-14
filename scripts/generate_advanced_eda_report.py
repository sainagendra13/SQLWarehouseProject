"""Generate a PDF of Advanced EDA SQL Server results.

Install: pip install pyodbc reportlab
Run: python generate_advanced_eda_report.py
Output: scripts/report/advanced_eda.pdf
Requires SQL Server 2022+ for DATETRUNC in the supplied queries.
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import os
import pyodbc
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SERVER = os.getenv("SQL_SERVER", "localhost")  # Replace with the server name from SSMS
DATABASE = "SQLDataWarehouse"
ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")  # Or ODBC Driver 18 for SQL Server
USE_WINDOWS_AUTH = not bool(os.getenv("MSSQL_SA_PASSWORD"))
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = os.getenv("MSSQL_SA_PASSWORD", "")
MAX_ROWS = 20
QUERY_TIMEOUT_SECONDS = int(os.getenv("EDA_QUERY_TIMEOUT", "60"))
CONNECT_TIMEOUT_SECONDS = 5
OUTPUT = Path(__file__).resolve().parent / "report" / "advanced_eda.pdf"

# Keep TOP inside the SQL query to avoid transferring large result sets.
# The outer TOP preserves each query's ORDER BY by sorting on its output columns.
QUERIES = [
    ("1. Change Over Time Analysis", "1.1 Yearly Sales Analysis", """
        SELECT TOP (20)
            YEAR(order_date) AS order_year,
            SUM(sales_amount) AS total_sales,
            COUNT(DISTINCT customer_key) AS total_customers,
            SUM(quantity) AS total_quantity
        FROM gold.fact_sales
        WHERE order_date IS NOT NULL AND YEAR(order_date) <= YEAR(GETDATE())
        GROUP BY YEAR(order_date)
        ORDER BY order_year
    """),
    ("1. Change Over Time Analysis", "1.2 Monthly Sales Analysis", """
        SELECT TOP (20)
            DATETRUNC(month, order_date) AS order_month,
            SUM(sales_amount) AS total_sales,
            COUNT(DISTINCT customer_key) AS total_customers,
            SUM(quantity) AS total_quantity
        FROM gold.fact_sales
        WHERE order_date IS NOT NULL AND YEAR(order_date) <= YEAR(GETDATE())
        GROUP BY DATETRUNC(month, order_date)
        ORDER BY order_month
    """),
    ("2. Cumulative Analysis", "2.1 Running Total and Moving Average", """
        SELECT TOP (20)
            order_date,
            total_sales,
            SUM(total_sales) OVER (
                PARTITION BY YEAR(order_date)
                ORDER BY order_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_total_sales,
            AVG(avg_price) OVER (
                ORDER BY order_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS moving_average
        FROM (
            SELECT
                DATETRUNC(month, order_date) AS order_date,
                SUM(sales_amount) AS total_sales,
                AVG(price) AS avg_price
            FROM gold.fact_sales
            WHERE order_date IS NOT NULL AND YEAR(order_date) <= YEAR(GETDATE())
            GROUP BY DATETRUNC(month, order_date)
        ) t
        ORDER BY order_date
    """),
    ("3. Performance Analysis", "3.1 Yearly Product Sales Performance", """
        WITH yearly_product_sales AS (
            SELECT
                YEAR(f.order_date) AS order_year,
                p.product_name,
                SUM(f.sales_amount) AS current_sales
            FROM gold.fact_sales f
            LEFT JOIN gold.dim_products p ON f.product_key = p.product_key
            WHERE f.order_date IS NOT NULL
              AND YEAR(f.order_date) <= YEAR(GETDATE())
            GROUP BY YEAR(f.order_date), p.product_name
        ), comparison AS (
            SELECT
                order_year, product_name, current_sales,
                AVG(current_sales) OVER (PARTITION BY product_name) AS avg_sales,
                LAG(current_sales) OVER (
                    PARTITION BY product_name ORDER BY order_year
                ) AS previous_sales
            FROM yearly_product_sales
        )
        SELECT TOP (20)
            order_year, product_name, current_sales, avg_sales,
            current_sales - avg_sales AS diff_avg,
            CASE
                WHEN current_sales > avg_sales THEN 'Above Average'
                WHEN current_sales < avg_sales THEN 'Below Average'
                ELSE 'Average'
            END AS average_change,
            previous_sales,
            current_sales - previous_sales AS difference_sales,
            CASE
                WHEN previous_sales IS NULL THEN 'No Previous Year'
                WHEN current_sales > previous_sales THEN 'Increase'
                WHEN current_sales < previous_sales THEN 'Decrease'
                ELSE 'No Change'
            END AS previous_change
        FROM comparison
        ORDER BY product_name, order_year
    """),
    ("4. Part-to-Whole Analysis", "4.1 Category Contribution to Overall Sales", """
        WITH category_sales AS (
            SELECT p.category, SUM(f.sales_amount) AS total_sales
            FROM gold.fact_sales f
            LEFT JOIN gold.dim_products p ON p.product_key = f.product_key
            GROUP BY p.category
        )
        SELECT TOP (20)
            category,
            total_sales,
            SUM(total_sales) OVER () AS overall_sales,
            CONCAT(
                ROUND(100.0 * total_sales /
                      NULLIF(SUM(total_sales) OVER (), 0), 2), '%'
            ) AS percentage_of_total
        FROM category_sales
        ORDER BY total_sales DESC
    """),
    ("5. Data Segmentation", "5.1 Products by Cost Range", """
        WITH product_segment AS (
            SELECT
                product_key,
                CASE
                    WHEN cost < 100 THEN 'BELOW 100'
                    WHEN cost < 500 THEN '100-499'
                    WHEN cost <= 1000 THEN '500-1000'
                    ELSE 'ABOVE 1000'
                END AS cost_range
            FROM gold.dim_products
        )
        SELECT TOP (20)
            cost_range, COUNT(product_key) AS total_products
        FROM product_segment
        GROUP BY cost_range
        ORDER BY total_products DESC
    """),
    ("5. Data Segmentation", "5.2 Customers by Spending and Lifespan", """
        WITH customer_spending AS (
            SELECT
                c.customer_key,
                SUM(f.sales_amount) AS total_spending,
                MIN(f.order_date) AS first_order,
                MAX(f.order_date) AS last_order,
                DATEDIFF(MONTH, MIN(f.order_date), MAX(f.order_date)) AS lifespan
            FROM gold.fact_sales f
            LEFT JOIN gold.dim_customers c
                ON f.customer_key = c.customer_key
            GROUP BY c.customer_key
        ), segmented AS (
            SELECT customer_key,
                CASE
                    WHEN lifespan >= 12 AND total_spending > 5000 THEN 'VIP'
                    WHEN lifespan >= 12 AND total_spending <= 5000 THEN 'REGULAR'
                    ELSE 'NEW'
                END AS customer_segment
            FROM customer_spending
        )
        SELECT TOP (20)
            customer_segment, COUNT(customer_key) AS total_customers
        FROM segmented
        GROUP BY customer_segment
        ORDER BY total_customers DESC
    """),
]


def connect():
    parts = [
        f"DRIVER={{{ODBC_DRIVER}}}", f"SERVER={SERVER}",
        f"DATABASE={DATABASE}", "TrustServerCertificate=yes",
    ]
    if USE_WINDOWS_AUTH:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend([f"UID={SQL_USERNAME}", f"PWD={SQL_PASSWORD}"])
    conn = pyodbc.connect(";".join(parts) + ";", timeout=CONNECT_TIMEOUT_SECONDS,
                          autocommit=True)
    conn.timeout = QUERY_TIMEOUT_SECONDS  # pyodbc timeout is on Connection, NOT Cursor
    return conn


def worker(sql, out_queue):
    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(sql)
        headers = [c[0] for c in cursor.description]
        rows = [tuple("NULL" if value is None else str(value) for value in row)
                for row in cursor.fetchmany(MAX_ROWS)]
        out_queue.put({"status": "ok", "headers": headers, "rows": rows})
    except Exception as exc:
        out_queue.put({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def run_query(sql):
    result_queue = mp.Queue()
    process = mp.Process(target=worker, args=(sql, result_queue))
    started = time.perf_counter()
    process.start()
    try:
        # Read before join to avoid worker blocking while writing to a full queue.
        try:
            result = result_queue.get(timeout=QUERY_TIMEOUT_SECONDS)
        except queue.Empty:
            result = {"status": "timeout", "error": f"Exceeded {QUERY_TIMEOUT_SECONDS}s"}
        if process.is_alive():
            process.join(timeout=0.5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if process.is_alive():
            process.kill()
            process.join()
    finally:
        result_queue.close()
        result_queue.join_thread()
    result["seconds"] = round(time.perf_counter() - started, 2)
    return result


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(34, 22, "SQLDataWarehouse | Advanced EDA")
    canvas.drawRightString(landscape(A4)[0] - 34, 22, f"Page {doc.page}")
    canvas.restoreState()


def make_pdf(results):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="EDA_Title", parent=styles["Title"],
                              fontSize=19, leading=23, alignment=TA_CENTER,
                              textColor=colors.HexColor("#17365D"), spaceAfter=12))
    styles.add(ParagraphStyle(name="EDA_Section", parent=styles["Heading1"],
                              fontSize=13, leading=16, spaceBefore=14, spaceAfter=7,
                              textColor=colors.HexColor("#17365D")))
    styles.add(ParagraphStyle(name="EDA_Subsection", parent=styles["Heading2"],
                              fontSize=10, leading=13, spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle(name="EDA_Cell", fontName="Helvetica", fontSize=7,
                              leading=9, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="EDA_Header", parent=styles["EDA_Cell"],
                              fontName="Helvetica-Bold", textColor=colors.white))
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=landscape(A4),
                            leftMargin=34, rightMargin=34,
                            topMargin=35, bottomMargin=37)
    story = [Paragraph("ADVANCED EXPLORATORY DATA ANALYSIS", styles["EDA_Title"]),
             Paragraph(f"Database: {escape(DATABASE)} | Generated: "
                       f"{datetime.now():%d %b %Y %I:%M %p} | "
                       f"Max {MAX_ROWS} rows/query | Timeout {QUERY_TIMEOUT_SECONDS}s",
                       styles["Normal"]), Spacer(1, 12)]
    current_section = None
    successful = 0
    for section, heading, result in results:
        if section != current_section:
            story.append(Paragraph(escape(section), styles["EDA_Section"]))
            current_section = section
        story.append(Paragraph(escape(heading), styles["EDA_Subsection"]))
        if result["status"] != "ok":
            story.append(Paragraph("SKIPPED: " + escape(result["error"]), styles["Normal"]))
            story.append(Spacer(1, 10))
            continue
        successful += 1
        rows, headers = result["rows"], result["headers"]
        story.append(Paragraph(f"Rows shown: {len(rows)} | Query time: "
                               f"{result['seconds']:.2f}s", styles["Normal"]))
        data = [[Paragraph(escape(str(h)), styles["EDA_Header"]) for h in headers]]
        if rows:
            data.extend([[Paragraph(escape(str(v)), styles["EDA_Cell"]) for v in row]
                         for row in rows])
        else:
            data.append([Paragraph("No records", styles["EDA_Cell"])] +
                        [""] * (len(headers) - 1))
        width = landscape(A4)[0] - 68
        table = Table(data, colWidths=[width / len(headers)] * len(headers),
                      repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F1F5F9")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([Spacer(1, 5), table, Spacer(1, 12)])
    story.append(Paragraph(f"Completed {successful} of {len(results)} analyses.",
                           styles["Normal"]))
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


def main():
    print(f"Advanced EDA: {len(QUERIES)} queries | {QUERY_TIMEOUT_SECONDS}s each | "
          f"max {MAX_ROWS} rows", flush=True)
    results = []
    for section, title, sql in QUERIES:
        print(f"Running {title}...", flush=True)
        result = run_query(sql)
        if result["status"] == "ok":
            print(f"  DONE: {len(result['rows'])} rows in {result['seconds']:.2f}s", flush=True)
        else:
            print(f"  SKIPPED: {result['error']}", flush=True)
        results.append((section, title, result))
    print("Building PDF...", flush=True)
    make_pdf(results)
    print(f"Saved: {OUTPUT}", flush=True)


if __name__ == "__main__":
    mp.freeze_support()  # Required for Windows multiprocessing
    main()

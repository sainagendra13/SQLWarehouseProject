
"""
Gold Layer Exploratory Data Analysis
SQL Server -> PDF Report

Requirements:
    pip install pyodbc reportlab

Output:
    scripts/report/Gold_Layer_EDA_Report.pdf

Features:
    - 19 SQL queries
    - Maximum 20 rows per query
    - 60-second timeout per query
    - Automatically skips timed-out queries
    - Shows execution time
    - Generates only a PDF
"""

import multiprocessing as mp
import queue
import time
from datetime import datetime
from pathlib import Path

import os
import pyodbc

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
    PageBreak,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from xml.sax.saxutils import escape


# ============================================================
# 1. CONFIGURATION
# ============================================================

SERVER = os.getenv("SQL_SERVER", "localhost")
DATABASE = "SQLDataWarehouse"

# Change this if you use another ODBC driver.
ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

USE_WINDOWS_AUTH = not bool(os.getenv("MSSQL_SA_PASSWORD"))

# Only needed when USE_WINDOWS_AUTH = False
SQL_USERNAME = os.getenv("SQL_USERNAME", "sa")
SQL_PASSWORD = os.getenv("MSSQL_SA_PASSWORD", "")

MAX_ROWS = 20

QUERY_TIMEOUT_SECONDS = int(os.getenv("EDA_QUERY_TIMEOUT", "60"))
CONNECT_TIMEOUT_SECONDS = 5

BASE_DIR = Path(__file__).resolve().parent
REPORT_DIR = BASE_DIR / "report"

PDF_PATH = REPORT_DIR / "Gold_Layer_EDA_Report.pdf"


# ============================================================
# 2. DATABASE CONNECTION
# ============================================================

def get_connection():

    if USE_WINDOWS_AUTH:

        connection_string = (
            f"DRIVER={{{ODBC_DRIVER}}};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    else:

        connection_string = (
            f"DRIVER={{{ODBC_DRIVER}}};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={SQL_USERNAME};"
            f"PWD={SQL_PASSWORD};"
            "TrustServerCertificate=yes;"
        )

    conn = pyodbc.connect(
        connection_string,
        timeout=CONNECT_TIMEOUT_SECONDS,
        autocommit=True,
    )

    # Correct: timeout belongs to the connection.
    conn.timeout = QUERY_TIMEOUT_SECONDS

    return conn


# ============================================================
# 3. SQL QUERIES
# ============================================================

QUERIES = [

    # --------------------------------------------------------
    # SECTION 1: DATABASE & SCHEMA EXPLORATION
    # --------------------------------------------------------

    (
        "1. Database & Schema Exploration",
        "1.1 Gold Layer Tables",
        """
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'gold'
        ORDER BY TABLE_NAME
        """
    ),

    (
        "1. Database & Schema Exploration",
        "1.2 Gold Layer Column Metadata",
        """
        SELECT
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'gold'
        ORDER BY TABLE_NAME, ORDINAL_POSITION
        """
    ),

    # --------------------------------------------------------
    # SECTION 2: DIMENSIONAL ANALYSIS
    # --------------------------------------------------------

    (
        "2. Dimensional Analysis",
        "2.1 Customer Countries",
        """
        SELECT DISTINCT country
        FROM gold.dim_customers
        ORDER BY country
        """
    ),

    (
        "2. Dimensional Analysis",
        "2.2 Marital Status",
        """
        SELECT DISTINCT marital_status
        FROM gold.dim_customers
        ORDER BY marital_status
        """
    ),

    (
        "2. Dimensional Analysis",
        "2.3 Gender",
        """
        SELECT DISTINCT gender
        FROM gold.dim_customers
        ORDER BY gender
        """
    ),

    (
        "2. Dimensional Analysis",
        "2.4 Product Hierarchy",
        """
        SELECT DISTINCT
            category,
            subcategory,
            product_line,
            maintenance
        FROM gold.dim_products
        ORDER BY category, subcategory
        """
    ),

    # --------------------------------------------------------
    # SECTION 3: DATE EXPLORATION
    # --------------------------------------------------------

    (
        "3. Date Exploration",
        "3.1 Order Date Boundaries",
        """
        SELECT
            MIN(order_date) AS first_order_date,
            MAX(order_date) AS last_order_date,
            DATEDIFF(
                YEAR,
                MIN(order_date),
                MAX(order_date)
            ) AS order_range_years,
            DATEDIFF(
                MONTH,
                MIN(order_date),
                MAX(order_date)
            ) AS order_range_months
        FROM gold.fact_sales
        """
    ),

    (
        "3. Date Exploration",
        "3.2 Customer Birthdate and Age Boundaries",
        """
        SELECT
            MIN(birthdate) AS oldest_birthdate,
            DATEDIFF(
                YEAR,
                MIN(birthdate),
                GETDATE()
            ) AS oldest_age,
            MAX(birthdate) AS youngest_birthdate,
            DATEDIFF(
                YEAR,
                MAX(birthdate),
                GETDATE()
            ) AS youngest_age
        FROM gold.dim_customers
        """
    ),

    # --------------------------------------------------------
    # SECTION 4: MEASURES EXPLORATION
    # --------------------------------------------------------

    (
        "4. Measures Exploration",
        "4.1 Business KPIs",
        """
        SELECT
            'Total Sales' AS measure_name,
            SUM(sales_amount) AS measure_value
        FROM gold.fact_sales

        UNION ALL

        SELECT
            'Total Quantity Sold',
            SUM(quantity)
        FROM gold.fact_sales

        UNION ALL

        SELECT
            'Average Selling Price',
            AVG(price)
        FROM gold.fact_sales

        UNION ALL

        SELECT
            'Total Number of Orders',
            COUNT(DISTINCT order_number)
        FROM gold.fact_sales

        UNION ALL

        SELECT
            'Total Number of Products',
            COUNT(DISTINCT product_key)
        FROM gold.dim_products

        UNION ALL

        SELECT
            'Total Number of Customers',
            COUNT(DISTINCT customer_key)
        FROM gold.dim_customers

        UNION ALL

        SELECT
            'Total Active Customers (Placed Orders)',
            COUNT(DISTINCT customer_key)
        FROM gold.fact_sales
        """
    ),

    # --------------------------------------------------------
    # SECTION 5: MAGNITUDE ANALYSIS
    # --------------------------------------------------------

    (
        "5. Magnitude Analysis",
        "5.1 Customers by Country",
        """
        SELECT
            country,
            COUNT(customer_key) AS total_customers
        FROM gold.dim_customers
        GROUP BY country
        ORDER BY total_customers DESC
        """
    ),

    (
        "5. Magnitude Analysis",
        "5.2 Customers by Gender",
        """
        SELECT
            gender,
            COUNT(customer_key) AS total_customers
        FROM gold.dim_customers
        GROUP BY gender
        ORDER BY total_customers DESC
        """
    ),

    (
        "5. Magnitude Analysis",
        "5.3 Products and Average Cost by Category",
        """
        SELECT
            category,
            COUNT(product_key) AS total_products,
            AVG(cost) AS avg_cost
        FROM gold.dim_products
        GROUP BY category
        ORDER BY total_products DESC
        """
    ),

    (
        "5. Magnitude Analysis",
        "5.4 Revenue by Category",
        """
        SELECT
            p.category,
            SUM(f.sales_amount) AS total_revenue
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_products p
            ON f.product_key = p.product_key
        GROUP BY p.category
        ORDER BY total_revenue DESC
        """
    ),

    (
        "5. Magnitude Analysis",
        "5.5 Revenue by Customer",
        """
        SELECT
            c.customer_key,
            c.first_name,
            c.last_name,
            SUM(f.sales_amount) AS total_revenue
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_customers c
            ON f.customer_key = c.customer_key
        GROUP BY
            c.customer_key,
            c.first_name,
            c.last_name
        ORDER BY total_revenue DESC
        """
    ),

    (
        "5. Magnitude Analysis",
        "5.6 Sold Items by Country",
        """
        SELECT
            c.country,
            SUM(f.quantity) AS total_sold_items
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_customers c
            ON f.customer_key = c.customer_key
        GROUP BY c.country
        ORDER BY total_sold_items DESC
        """
    ),

    # --------------------------------------------------------
    # SECTION 6: RANKING ANALYSIS
    # --------------------------------------------------------

    (
        "6. Ranking Analysis",
        "6.1 Top 5 Products by Revenue",
        """
        SELECT TOP 5
            p.product_name,
            SUM(f.sales_amount) AS total_revenue
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_products p
            ON f.product_key = p.product_key
        GROUP BY p.product_name
        ORDER BY total_revenue DESC
        """
    ),

    (
        "6. Ranking Analysis",
        "6.2 Bottom 5 Products by Revenue",
        """
        SELECT *
        FROM (
            SELECT
                p.product_name,
                SUM(f.sales_amount) AS total_revenue,
                ROW_NUMBER() OVER (
                    ORDER BY SUM(f.sales_amount) ASC
                ) AS rank_products
            FROM gold.fact_sales f
            LEFT JOIN gold.dim_products p
                ON f.product_key = p.product_key
            GROUP BY p.product_name
        ) t
        WHERE rank_products <= 5
        ORDER BY rank_products
        """
    ),

    (
        "6. Ranking Analysis",
        "6.3 Top 10 Customers by Revenue",
        """
        SELECT TOP 10
            c.customer_key,
            c.first_name,
            c.last_name,
            SUM(f.sales_amount) AS total_revenue
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_customers c
            ON f.customer_key = c.customer_key
        GROUP BY
            c.customer_key,
            c.first_name,
            c.last_name
        ORDER BY total_revenue DESC
        """
    ),

    (
        "6. Ranking Analysis",
        "6.4 Bottom 3 Customers by Order Count",
        """
        SELECT TOP 3
            c.customer_key,
            c.first_name,
            c.last_name,
            COUNT(DISTINCT f.order_number) AS total_orders
        FROM gold.fact_sales f
        LEFT JOIN gold.dim_customers c
            ON f.customer_key = c.customer_key
        GROUP BY
            c.customer_key,
            c.first_name,
            c.last_name
        ORDER BY total_orders ASC
        """
    ),
]


# ============================================================
# 4. EXECUTE QUERY IN SEPARATE PROCESS
# ============================================================

def query_worker(sql, result_queue):

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(sql)

        columns = [
            column[0]
            for column in cursor.description
        ]

        rows = cursor.fetchmany(MAX_ROWS)

        formatted_rows = [
            [
                str(value) if value is not None else "NULL"
                for value in row
            ]
            for row in rows
        ]

        result_queue.put({
            "status": "success",
            "columns": columns,
            "rows": formatted_rows,
        })

    except Exception as exc:

        result_queue.put({
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        })

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


# ============================================================
# 5. TIMEOUT MANAGEMENT
# ============================================================

def execute_with_timeout(sql):

    result_queue = mp.Queue()

    process = mp.Process(
        target=query_worker,
        args=(sql, result_queue),
    )

    start = time.perf_counter()

    process.start()

    process.join(timeout=QUERY_TIMEOUT_SECONDS)

    elapsed = time.perf_counter() - start

    if process.is_alive():

        process.terminate()
        process.join(timeout=3)

        if process.is_alive():
            process.kill()
            process.join()

        result = {
            "status": "timeout",
            "error": (
                f"Query exceeded "
                f"{QUERY_TIMEOUT_SECONDS} seconds"
            ),
        }

    else:

        try:
            result = result_queue.get(timeout=2)

        except queue.Empty:
            result = {
                "status": "error",
                "error": (
                    "Worker exited without returning results. "
                    f"Exit code: {process.exitcode}"
                ),
            }

    result_queue.close()
    result_queue.join_thread()

    result["elapsed"] = round(elapsed, 2)

    return result


# ============================================================
# 6. PDF FORMATTING
# ============================================================

def add_page_number(canvas, doc):

    canvas.saveState()

    width, height = landscape(A4)

    canvas.setFont("Helvetica", 8)

    canvas.drawRightString(
        width - 30,
        20,
        f"Page {doc.page}"
    )

    canvas.restoreState()


def generate_pdf(results):

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=35,
        bottomMargin=35,
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=23,
            alignment=TA_CENTER,
            spaceAfter=15,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=14,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="QueryTitle",
            parent=styles["Heading2"],
            fontSize=10,
            leading=14,
            spaceBefore=9,
            spaceAfter=6,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CellText",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            wordWrap="CJK",
        )
    )

    styles.add(
        ParagraphStyle(
            name="HeaderText",
            parent=styles["CellText"],
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
    )

    story = []

    story.append(
        Paragraph(
            "SQL DATA WAREHOUSE",
            styles["ReportTitle"],
        )
    )

    story.append(
        Paragraph(
            "Gold Layer Exploratory Data Analysis",
            styles["Heading2"],
        )
    )

    generated_at = datetime.now().strftime(
        "%d %B %Y, %I:%M:%S %p"
    )

    story.append(
        Paragraph(
            f"Generated: {generated_at}",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph(
            f"Database: {escape(DATABASE)}",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph(
            f"Maximum rows per query: {MAX_ROWS}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 0.25 * inch))

    current_section = None

    for section, title, result in results:

        if section != current_section:

            current_section = section

            story.append(
                Paragraph(
                    escape(section),
                    styles["SectionTitle"],
                )
            )

        story.append(
            Paragraph(
                escape(title),
                styles["QueryTitle"],
            )
        )

        elapsed = result.get("elapsed", 0)

        if result["status"] != "success":

            error_message = result.get(
                "error",
                "Unknown error"
            )

            story.append(
                Paragraph(
                    f"SKIPPED: {escape(error_message)}",
                    styles["Normal"],
                )
            )

            story.append(Spacer(1, 8))

            continue

        columns = result["columns"]
        rows = result["rows"]

        story.append(
            Paragraph(
                f"Rows displayed: {len(rows)} | "
                f"Execution time: {elapsed:.2f}s",
                styles["Normal"],
            )
        )

        table_data = []

        table_data.append([
            Paragraph(
                escape(str(column)),
                styles["HeaderText"],
            )
            for column in columns
        ])

        for row in rows:

            table_data.append([
                Paragraph(
                    escape(str(value)),
                    styles["CellText"],
                )
                for value in row
            ])

        if not rows:

            table_data.append([
                Paragraph(
                    "No records found",
                    styles["CellText"],
                )
            ] + [""] * (len(columns) - 1))

        available_width = (
            landscape(A4)[0] - 60
        )

        column_width = (
            available_width / len(columns)
        )

        table = Table(
            table_data,
            colWidths=[
                column_width
                for _ in columns
            ],
            repeatRows=1,
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle([
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#17365D"),
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.grey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#F0F4F8"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ])
        )

        story.append(table)
        story.append(Spacer(1, 12))

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )


# ============================================================
# 7. MAIN PROGRAM
# ============================================================

def main():

    print("\n" + "=" * 60)
    print("GOLD LAYER EDA REPORT GENERATOR")
    print("=" * 60)

    print(f"Database: {DATABASE}")
    print(f"Queries: {len(QUERIES)}")
    print(f"Maximum rows: {MAX_ROWS}")
    print(
        f"Timeout per query: "
        f"{QUERY_TIMEOUT_SECONDS}s"
    )

    print("=" * 60 + "\n")

    results = []

    report_start = time.perf_counter()

    for section, title, sql in QUERIES:

        print(
            f"Running {title}... "
            f"(limit {QUERY_TIMEOUT_SECONDS}s)",
            flush=True,
        )

        result = execute_with_timeout(sql)

        if result["status"] == "success":

            print(
                f"  DONE: "
                f"{len(result['rows'])} rows "
                f"in {result['elapsed']:.2f}s",
                flush=True,
            )

        else:

            print(
                f"  SKIPPED after "
                f"{result['elapsed']:.2f}s: "
                f"{result.get('error')}",
                flush=True,
            )

        results.append(
            (section, title, result)
        )

    print("\nBuilding PDF...", flush=True)

    pdf_start = time.perf_counter()

    generate_pdf(results)

    pdf_elapsed = (
        time.perf_counter() - pdf_start
    )

    total_elapsed = (
        time.perf_counter() - report_start
    )

    successful = sum(
        1
        for _, _, result in results
        if result["status"] == "success"
    )

    skipped = len(results) - successful

    print(
        f"PDF built in {pdf_elapsed:.2f}s"
    )

    print("\n" + "=" * 60)
    print("REPORT GENERATION COMPLETED")
    print("=" * 60)

    print(f"Successful queries: {successful}")
    print(f"Skipped queries: {skipped}")
    print(f"Total time: {total_elapsed:.2f}s")

    print(f"\nSaved PDF:\n{PDF_PATH}")


# ============================================================
# 8. ENTRY POINT
# ============================================================

if __name__ == "__main__":

    mp.freeze_support()
    main()

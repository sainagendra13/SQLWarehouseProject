"""One-command SQL Server warehouse pipeline. Run inside Docker Compose."""
import argparse
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'scripts'
LOG = logging.getLogger('warehouse')
DB = 'SQLDataWarehouse'


def connect(database='master'):
    driver = os.getenv('ODBC_DRIVER', 'ODBC Driver 18 for SQL Server')
    host = os.getenv('SQL_SERVER', 'sqlserver')
    password = os.environ['MSSQL_SA_PASSWORD']
    cs = (f'DRIVER={{{driver}}};SERVER={host};DATABASE={database};'
          f'UID=sa;PWD={password};Encrypt=yes;TrustServerCertificate=yes;')
    conn = pyodbc.connect(cs, timeout=8, autocommit=True)
    conn.timeout = int(os.getenv('ETL_QUERY_TIMEOUT', '600'))
    return conn


def batches(sql):
    # GO is a client-side batch separator; not valid T-SQL.
    return [part.strip() for part in re.split(r'^\s*GO\s*(?:--[^\n]*)?$', sql,
                                              flags=re.I | re.M) if part.strip()]


def execute_sql(conn, sql):
    for part in batches(sql):
        cur = conn.cursor()
        try:
            cur.execute(part)
            while True:
                if cur.description:
                    cur.fetchall()
                if not cur.nextset():
                    break
        finally:
            cur.close()


def execute_file(conn, relative, install_proc=False, bronze_path=False):
    path = SCRIPTS / relative
    sql = path.read_text(encoding='utf-8-sig')
    if install_proc:
        # Existing source files end with EXEC; do not run during installation.
        sql = re.sub(r'(?im)^\s*EXEC\s+(?:bronze\.load_bronze|silver\.load_silver)\s*;?\s*$', '', sql)
    if bronze_path:
        # Original SQL uses a Windows repo path and backslash concatenation.
        sql, count = re.subn(r'DECLARE\s+@RepoPath\s+NVARCHAR\(500\)\s*=\s*N\x27[^\x27]*\x27\s*;',
                             "DECLARE @RepoPath NVARCHAR(500) = N'/data';", sql,
                             count=1, flags=re.I)
        if count != 1:
            raise RuntimeError('Could not patch Bronze dataset root path')
        sql = sql.replace("N'\\dataset\\", "N'/dataset/")
    LOG.info('SQL file: %s', relative)
    execute_sql(conn, sql)


def wait_for_server():
    for attempt in range(1, 61):
        try:
            c = connect()
            c.close()
            return
        except (pyodbc.Error, OSError) as exc:
            if attempt == 60:
                raise RuntimeError('SQL Server did not become ready') from exc
            time.sleep(3)


def exists(conn, object_name, obj_type='U'):
    row = conn.cursor().execute('SELECT OBJECT_ID(?, ?)', object_name, obj_type).fetchone()
    return row[0] is not None


def table_names(layer):
    return ['crm_cust_info','crm_prd_info','crm_sales_details',
            'erp_cust_az12','erp_loc_a101','erp_px_cat_g1v2']


def check_dataset():
    expected = ['source_crm/cust_info.csv','source_crm/prd_info.csv',
                'source_crm/sales_details.csv','source_erp/CUST_AZ12.csv',
                'source_erp/LOC_A101.csv','source_erp/PX_CAT_G1V2.csv']
    missing = [f for f in expected if not (ROOT / 'dataset' / f).is_file()]
    if missing:
        raise FileNotFoundError('Missing dataset files: ' + ', '.join(missing))


def verify(conn, stage, objects):
    for name, typ in objects:
        if not exists(conn, name, typ):
            raise RuntimeError(f'{stage}: missing object {name}')
    LOG.info('Validated %s: %d objects', stage, len(objects))


def run_pdf(script):
    LOG.info('Generating PDF with %s', script)
    # The generators use multiprocessing on Windows/Linux; subprocess isolation is safest.
    subprocess.run([sys.executable, str(SCRIPTS / script)],
                   cwd=str(SCRIPTS), check=True,
                   env={**os.environ, 'PYTHONUNBUFFERED': '1'},
                   timeout=int(os.getenv('PDF_STAGE_TIMEOUT', '1500')))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-pdf', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    start = time.monotonic()
    check_dataset()
    wait_for_server()
    with connect('master') as master:
        master.execute("IF DB_ID(N'SQLDataWarehouse') IS NULL CREATE DATABASE SQLDataWarehouse")
    with connect(DB) as conn:
        for schema in ('bronze','silver','gold'):
            execute_sql(conn, f"IF SCHEMA_ID('{schema}') IS NULL EXEC('CREATE SCHEMA {schema}')")
        for layer in ('bronze','silver'):
            names = [f'{layer}.{n}' for n in table_names(layer)]
            present = [exists(conn, n) for n in names]
            if any(present) and not all(present):
                raise RuntimeError(f'{layer}: partial schema detected; repair manually before rerunning')
            if not any(present):
                execute_file(conn, f'{layer}/ddl_{layer}.sql')
            verify(conn, layer, [(n,'U') for n in names])
        execute_file(conn, 'bronze/bulkinsert_bronze.sql', install_proc=True, bronze_path=True)
        execute_file(conn, 'silver/load_silver.sql', install_proc=True)
        LOG.info('Running bronze.load_bronze')
        execute_sql(conn, 'EXEC bronze.load_bronze')
        LOG.info('Running silver.load_silver')
        execute_sql(conn, 'EXEC silver.load_silver')
        execute_file(conn, 'gold/ddl_gold.sql')
        verify(conn, 'gold', [(f'gold.{n}','V') for n in ('dim_customers','dim_products','fact_sales')])
        for view in ('dim_customers','dim_products','fact_sales'):
            conn.cursor().execute(f'SELECT TOP (1) * FROM gold.{view}').fetchall()
        LOG.info('Gold dimensional views ready')
    if not args.skip_pdf:
        run_pdf('generate_gold_eda_report.py')
        run_pdf('generate_advanced_eda_report.py')
    with connect(DB) as conn:
        for name in ('customers','products'):
            execute_file(conn, f'gold/report_{name}.sql')
            verify(conn, name, [(f'gold.report_{name}','V')])
            conn.cursor().execute(f'SELECT TOP (1) * FROM gold.report_{name}').fetchall()
    LOG.info('PIPELINE COMPLETE in %.1fs', time.monotonic() - start)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logging.exception('PIPELINE FAILED')
        sys.exit(1)

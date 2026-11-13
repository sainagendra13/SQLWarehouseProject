
USE SQLDataWarehouse;
GO

CREATE OR ALTER PROCEDURE silver.load_silver
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY

        PRINT 'Starting Silver Layer Loading...';

        ------------------------------------------
        -- 1. CRM Customer Information
        ------------------------------------------
        PRINT 'Loading Customer Information...';

        TRUNCATE TABLE silver.crm_cust_info;

        INSERT INTO silver.crm_cust_info (
            cst_id,
            cst_key,
            cst_firstname,
            cst_lastname,
            cst_marital_status,
            cst_gndr,
            cst_create_date
        )
        SELECT
            cst_id,
            cst_key,
            TRIM(cst_firstname),
            TRIM(cst_lastname),

            -- Convert marital status codes
            CASE
                WHEN UPPER(TRIM(cst_marital_status)) = 'S'
                    THEN 'Single'
                WHEN UPPER(TRIM(cst_marital_status)) = 'M'
                    THEN 'Married'
                ELSE 'n/a'
            END,

            -- Convert gender codes
            CASE
                WHEN UPPER(TRIM(cst_gndr)) = 'F'
                    THEN 'Female'
                WHEN UPPER(TRIM(cst_gndr)) = 'M'
                    THEN 'Male'
                ELSE 'n/a'
            END,

            cst_create_date

        FROM (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY cst_id
                    ORDER BY cst_create_date DESC
                ) AS row_num
            FROM bronze.crm_cust_info
            WHERE cst_id IS NOT NULL
        ) AS customers

        WHERE row_num = 1;


        ------------------------------------------
        -- 2. CRM Product Information
        ------------------------------------------
        PRINT 'Loading Product Information...';

        TRUNCATE TABLE silver.crm_prd_info;

        INSERT INTO silver.crm_prd_info (
            prd_id,
            cat_id,
            prd_key,
            prd_nm,
            prd_cost,
            prd_line,
            prd_start_dt,
            prd_end_dt
        )
        SELECT
            prd_id,

            -- Extract category and product keys
            REPLACE(SUBSTRING(prd_key, 1, 5), '-', '_'),
            SUBSTRING(prd_key, 7, LEN(prd_key)),

            prd_nm,

            -- Replace missing cost with zero
            ISNULL(prd_cost, 0),

            -- Convert product line codes
            CASE
                WHEN UPPER(TRIM(prd_line)) = 'M'
                    THEN 'Mountain'
                WHEN UPPER(TRIM(prd_line)) = 'R'
                    THEN 'Road'
                WHEN UPPER(TRIM(prd_line)) = 'S'
                    THEN 'Other Sales'
                WHEN UPPER(TRIM(prd_line)) = 'T'
                    THEN 'Touring'
                ELSE 'n/a'
            END,

            CAST(prd_start_dt AS DATE),

            -- End date = next start date - 1 day
            CAST(
                DATEADD(
                    DAY, -1,
                    LEAD(prd_start_dt) OVER (
                        PARTITION BY prd_key
                        ORDER BY prd_start_dt
                    )
                ) AS DATE
            )

        FROM bronze.crm_prd_info;


        ------------------------------------------
        -- 3. CRM Sales Details
        ------------------------------------------
        PRINT 'Loading Sales Details...';

        TRUNCATE TABLE silver.crm_sales_details;

        INSERT INTO silver.crm_sales_details (
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,
            sls_order_dt,
            sls_ship_dt,
            sls_due_dt,
            sls_sales,
            sls_quantity,
            sls_price
        )
        SELECT
            sls_ord_num,
            sls_prd_key,
            sls_cust_id,

            -- Convert valid YYYYMMDD values to DATE
            TRY_CONVERT( DATE,NULLIF(CAST(sls_order_dt AS VARCHAR(30)), '0'), 112),
            TRY_CONVERT(DATE,NULLIF(CAST(sls_ship_dt AS VARCHAR(30)), '0'),112),
            TRY_CONVERT(DATE,NULLIF(CAST(sls_due_dt AS VARCHAR(30)), '0'),112),

            -- Recalculate incorrect sales
            CASE
                WHEN sls_sales IS NULL
                     OR sls_sales <= 0
                     OR sls_sales <> sls_quantity * ABS(sls_price)
                    THEN sls_quantity * ABS(sls_price)
                ELSE sls_sales
            END,

            sls_quantity,

            -- Correct missing or negative prices
            CASE
                WHEN sls_price IS NULL OR sls_price <= 0
                    THEN sls_sales / NULLIF(sls_quantity, 0)
                ELSE sls_price
            END

        FROM bronze.crm_sales_details;


        ------------------------------------------
        -- 4. ERP Customer Information
        ------------------------------------------
        PRINT 'Loading ERP Customer Information...';

        TRUNCATE TABLE silver.erp_cust_az12;

        INSERT INTO silver.erp_cust_az12 (
            cid,
            bdate,
            gen
        )
        SELECT

            -- Remove NAS prefix
            CASE
                WHEN cid LIKE 'NAS%'
                    THEN SUBSTRING(cid, 4, LEN(cid))
                ELSE cid
            END,

            -- Remove future birthdates
            CASE
                WHEN bdate > GETDATE() THEN NULL
                ELSE bdate
            END,

            -- Standardize gender
            CASE
                WHEN UPPER(TRIM(gen)) IN ('F', 'FEMALE')
                    THEN 'Female'
                WHEN UPPER(TRIM(gen)) IN ('M', 'MALE')
                    THEN 'Male'
                ELSE 'n/a'
            END

        FROM bronze.erp_cust_az12;


        ------------------------------------------
        -- 5. ERP Location Information
        ------------------------------------------
        PRINT 'Loading ERP Location Information...';

        TRUNCATE TABLE silver.erp_loc_a101;

        INSERT INTO silver.erp_loc_a101 (
            cid,
            cntry
        )
        SELECT

            -- Remove hyphens from customer IDs
            REPLACE(cid, '-', ''),

            -- Standardize country names
            CASE
                WHEN TRIM(cntry) = 'DE'
                    THEN 'Germany'
                WHEN TRIM(cntry) IN ('US', 'USA')
                    THEN 'United States'
                WHEN TRIM(cntry) = ''
                     OR cntry IS NULL
                    THEN 'n/a'
                ELSE TRIM(cntry)
            END

        FROM bronze.erp_loc_a101;


        ------------------------------------------
        -- 6. ERP Product Category
        ------------------------------------------
        PRINT 'Loading ERP Product Categories...';

        TRUNCATE TABLE silver.erp_px_cat_g1v2;

        INSERT INTO silver.erp_px_cat_g1v2 (
            id,
            cat,
            subcat,
            maintenance
        )
        SELECT
            id,
            cat,
            subcat,
            maintenance
        FROM bronze.erp_px_cat_g1v2;


        PRINT 'Silver Layer Loading Completed Successfully!';

    END TRY

    BEGIN CATCH

        PRINT 'Error while loading Silver Layer:';
        PRINT ERROR_MESSAGE();

        THROW;

    END CATCH
END;
GO

-- Execute the procedure
EXEC silver.load_silver;

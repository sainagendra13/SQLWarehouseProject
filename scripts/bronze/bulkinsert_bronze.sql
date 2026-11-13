USE SQLDataWarehouse;
GO

CREATE OR ALTER PROCEDURE bronze.load_bronze
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @RepoPath NVARCHAR(500) =
        N'D:\Data Analytics\SQL\SQLDataWarehouse\SQLWarehouseProject';

    DECLARE @SQL NVARCHAR(MAX);
    DECLARE @FilePath NVARCHAR(1000);
    DECLARE @StartTime DATETIME2;
    DECLARE @EndTime DATETIME2;
    DECLARE @RowsLoaded INT;

    BEGIN TRY

        PRINT '=============================================';
        PRINT 'BRONZE LAYER: DATA LOADING STARTED';
        PRINT '=============================================';

        SET @StartTime = SYSDATETIME();

        ---------------------------------------------------
        -- 1. Load CRM Customer Information
        ---------------------------------------------------
        PRINT 'Loading bronze.crm_cust_info...';

        TRUNCATE TABLE bronze.crm_cust_info;

        SET @FilePath = @RepoPath +
            N'\dataset\source_crm\cust_info.csv';

        SET @SQL = N'
            BULK INSERT bronze.crm_cust_info
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: crm_cust_info loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- 2. Load CRM Product Information
        ---------------------------------------------------
        PRINT 'Loading bronze.crm_prd_info...';

        TRUNCATE TABLE bronze.crm_prd_info;

        SET @FilePath = @RepoPath +
            N'\dataset\source_crm\prd_info.csv';

        SET @SQL = N'
            BULK INSERT bronze.crm_prd_info
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: crm_prd_info loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- 3. Load CRM Sales Details
        ---------------------------------------------------
        PRINT 'Loading bronze.crm_sales_details...';

        TRUNCATE TABLE bronze.crm_sales_details;

        SET @FilePath = @RepoPath +
            N'\dataset\source_crm\sales_details.csv';

        SET @SQL = N'
            BULK INSERT bronze.crm_sales_details
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: crm_sales_details loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- 4. Load ERP Customer Information
        ---------------------------------------------------
        PRINT 'Loading bronze.erp_cust_az12...';

        TRUNCATE TABLE bronze.erp_cust_az12;

        SET @FilePath = @RepoPath +
            N'\dataset\source_erp\CUST_AZ12.csv';

        SET @SQL = N'
            BULK INSERT bronze.erp_cust_az12
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: erp_cust_az12 loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- 5. Load ERP Location Information
        ---------------------------------------------------
        PRINT 'Loading bronze.erp_loc_a101...';

        TRUNCATE TABLE bronze.erp_loc_a101;

        SET @FilePath = @RepoPath +
            N'\dataset\source_erp\LOC_A101.csv';

        SET @SQL = N'
            BULK INSERT bronze.erp_loc_a101
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: erp_loc_a101 loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- 6. Load ERP Product Category
        ---------------------------------------------------
        PRINT 'Loading bronze.erp_px_cat_g1v2...';

        TRUNCATE TABLE bronze.erp_px_cat_g1v2;

        SET @FilePath = @RepoPath +
            N'\dataset\source_erp\PX_CAT_G1V2.csv';

        SET @SQL = N'
            BULK INSERT bronze.erp_px_cat_g1v2
            FROM ''' + REPLACE(@FilePath, '''', '''''') + N'''
            WITH (
                FIRSTROW = 2,
                FIELDTERMINATOR = '','',
                TABLOCK
            );

            SET @RowsLoaded = @@ROWCOUNT;
        ';

        EXEC sys.sp_executesql
            @SQL,
            N'@RowsLoaded INT OUTPUT',
            @RowsLoaded OUTPUT;

        PRINT 'SUCCESS: erp_px_cat_g1v2 loaded.';
        PRINT 'Rows loaded: ' + CAST(@RowsLoaded AS VARCHAR(20));


        ---------------------------------------------------
        -- Execution Summary
        ---------------------------------------------------
        SET @EndTime = SYSDATETIME();

        PRINT '=============================================';
        PRINT 'BRONZE LAYER: DATA LOADING COMPLETED';
        PRINT '=============================================';
        PRINT 'Start Time: ' + CONVERT(VARCHAR(30), @StartTime, 121);
        PRINT 'End Time: ' + CONVERT(VARCHAR(30), @EndTime, 121);
        PRINT 'Duration (seconds): ' +
            CAST(DATEDIFF(SECOND, @StartTime, @EndTime) AS VARCHAR(20));

    END TRY

    BEGIN CATCH

        PRINT '=============================================';
        PRINT 'ERROR OCCURRED DURING BRONZE DATA LOADING';
        PRINT '=============================================';
        PRINT 'Error Number: ' + CAST(ERROR_NUMBER() AS VARCHAR(20));
        PRINT 'Error Message: ' + ERROR_MESSAGE();
        PRINT 'Error Line: ' + CAST(ERROR_LINE() AS VARCHAR(20));

        THROW;

    END CATCH
END;
GO

EXEC bronze.load_bronze;

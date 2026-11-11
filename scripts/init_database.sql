/*
=============================================================
Create Database and Schemas
=============================================================
Script Purpose:
    This script creates a new database named 'DataWarehouse' after checking if it already exists.
    If the database exists, it is dropped and recreated. Additionally, the script sets up three schemas
    within the database: 'bronze', 'silver', and 'gold'.

WARNING:
    Running this script will drop the entire 'DataWarehouse' database if it exists.
    All data in the database will be permanently deleted. Proceed with caution
    and ensure you have proper backups before running this script.
*/


-- Create a database SQLDataWarehouse
use master;
go

IF EXISTS (SELECT 1 FROM sys.databases WHERE name = 'SQLDataWarehouse')
BEGIN
    ALTER DATABASE SQLDataWarehouse SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE SQLDataWarehouse;
END;
GO

create database SQLDataWarehouse;
go

use SQLDataWarehouse;
go

-- Create Schema at all levels

create schema bronze;
go

create schema silver;
go

create schema gold;
go


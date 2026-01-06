/*
	This script is for SQL Server 2025 only.
*/

-- Create database if it doesn't exists yet
if db_id('WikipediaTest') is null begin
	create database WikipediaTest
end
go

-- Use sample database
use WikipediaTest
go

-- Enable Preview Features
alter database scoped configuration
set preview_features = on;
go
select * from sys.database_scoped_configurations where [name] = 'preview_features'
go

-- Enable external rest endpoint used by ai_generate_embeddings function
exec sp_configure 'external rest endpoint enabled', 1
reconfigure
go
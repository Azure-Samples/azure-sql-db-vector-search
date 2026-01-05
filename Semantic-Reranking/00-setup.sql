
/*
    Allow SQL Server to call a REST endpoint.
*/
EXEC sp_configure 'external rest endpoint enabled', 1
RECONFIGURE
GO

/*
    Restore Database in SQL Server 2025
*/
-- WARNING: The REPLACE option will overwrite any existing database named SemanticShoresDB
-- Verify no production database uses this name before running this command
RESTORE DATABASE SemanticShoresDB
FROM DISK = 'path\to\SemanticShoresDB.bak'
WITH MOVE 'SemanticShoresDB' TO 'C:\Data\SemanticShoresDB.mdf',
     MOVE 'SemanticShoresDB' TO 'C:\Data\SemanticShoresDB.ldf',
     REPLACE;
DECLARE @create_sql NVARCHAR(MAX) = ?;
DECLARE @started DATETIME2(7), @finished DATETIME2(7);
DECLARE @create_completed BIT = 0;
SET LOCK_TIMEOUT -1;

BEGIN TRY
    SET @started = SYSUTCDATETIME();
    EXEC sys.sp_executesql @create_sql;
    SET @finished = SYSUTCDATETIME();
    SET @create_completed = 1;

    SELECT @create_completed AS create_completed,
           CONVERT(NVARCHAR(27), @started, 126) + N'Z' AS started_utc,
           CONVERT(FLOAT, DATEDIFF_BIG(NANOSECOND, @started, @finished)) / 1000000000.0 AS build_seconds;
END TRY
BEGIN CATCH
    SELECT @create_completed AS create_completed,
           CONVERT(NVARCHAR(27), @started, 126) + N'Z' AS started_utc,
           CAST(NULL AS FLOAT) AS build_seconds;
    THROW;
END CATCH;
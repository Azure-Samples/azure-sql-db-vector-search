SET NOCOUNT ON;
SET XACT_ABORT ON;

IF DB_NAME() <> N'$(ExpectedDatabase)'
   OR DB_NAME() IN (N'master', N'tempdb', N'model', N'msdb')
    THROW 50000, 'Connect to the intended existing user database.', 1;

SELECT @@VERSION AS server_build, @@SERVERNAME AS server_name,
       DB_NAME() AS database_name, ORIGINAL_LOGIN() AS login_name,
       CONNECTIONPROPERTY('local_net_address') AS server_address,
       CONNECTIONPROPERTY('local_tcp_port') AS server_port;

IF OBJECT_ID(N'dbo.yfcc_$(DatasetSize)_documents') IS NOT NULL
   OR OBJECT_ID(N'dbo.yfcc_$(DatasetSize)_queries') IS NOT NULL
   OR OBJECT_ID(N'dbo.yfcc_$(DatasetSize)_groundtruth') IS NOT NULL
    THROW 50001, 'Destination objects already exist. No drop, truncate, or resume is performed.', 1;

BEGIN TRANSACTION;

CREATE TABLE dbo.yfcc_$(DatasetSize)_documents
(
    id INT NOT NULL PRIMARY KEY CLUSTERED,
    embedding VECTOR($(DocumentDimensions)) NOT NULL
);

CREATE TABLE dbo.yfcc_$(DatasetSize)_queries
(
    id INT NOT NULL PRIMARY KEY CLUSTERED,
    embedding VECTOR($(QueryDimensions)) NOT NULL
);

CREATE TABLE dbo.yfcc_$(DatasetSize)_groundtruth
(
    query_id INT NOT NULL,
    rank INT NOT NULL,
    neighbor_id INT NOT NULL,
    distance REAL NOT NULL,
    PRIMARY KEY CLUSTERED (query_id, rank)
);

IF EXISTS
(
    SELECT 1
    FROM (VALUES
        (N'yfcc_$(DatasetSize)_documents', 1, N'id', N'int', 0),
        (N'yfcc_$(DatasetSize)_documents', 2, N'embedding', N'vector', $(DocumentDimensions)),
        (N'yfcc_$(DatasetSize)_queries', 1, N'id', N'int', 0),
        (N'yfcc_$(DatasetSize)_queries', 2, N'embedding', N'vector', $(QueryDimensions)),
        (N'yfcc_$(DatasetSize)_groundtruth', 1, N'query_id', N'int', 0),
        (N'yfcc_$(DatasetSize)_groundtruth', 2, N'rank', N'int', 0),
        (N'yfcc_$(DatasetSize)_groundtruth', 3, N'neighbor_id', N'int', 0),
        (N'yfcc_$(DatasetSize)_groundtruth', 4, N'distance', N'real', 0)
    ) AS expected(table_name, column_id, column_name, type_name, dimensions)
    FULL OUTER JOIN
    (
        SELECT tables.name AS table_name, columns.column_id, columns.name AS column_name,
               types.name AS type_name, columns.is_nullable, columns.is_identity,
               columns.is_computed, columns.vector_dimensions, columns.vector_base_type
        FROM sys.tables AS tables
        JOIN sys.columns AS columns ON columns.object_id = tables.object_id
        JOIN sys.types AS types ON types.user_type_id = columns.user_type_id
        WHERE tables.schema_id = SCHEMA_ID(N'dbo')
          AND tables.name IN (N'yfcc_$(DatasetSize)_documents', N'yfcc_$(DatasetSize)_queries',
                              N'yfcc_$(DatasetSize)_groundtruth')
    ) AS actual ON actual.table_name = expected.table_name AND actual.column_id = expected.column_id
    WHERE actual.column_id IS NULL OR expected.column_id IS NULL
       OR actual.column_name <> expected.column_name OR actual.type_name <> expected.type_name
       OR actual.is_nullable <> 0 OR actual.is_identity <> 0 OR actual.is_computed <> 0
       OR ISNULL(actual.vector_dimensions, 0) <> expected.dimensions
       OR (expected.type_name = N'vector' AND ISNULL(actual.vector_base_type, -1) <> 0)
)
    THROW 50002, 'Destination schema does not match the native BCP records.', 1;

COMMIT TRANSACTION;
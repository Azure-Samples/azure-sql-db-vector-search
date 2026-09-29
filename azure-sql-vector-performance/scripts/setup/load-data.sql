SET NOCOUNT ON;

DECLARE @loaded_rows BIGINT;
SELECT @loaded_rows = COUNT_BIG(*)
FROM dbo.[$(TableName)]
WHERE [$(IdColumn)] >= $(FirstId) AND [$(IdColumn)] < $(EndId);

SELECT N'$(TableName)' AS dataset_table, $(FirstId) AS first_source_id,
	   $(EndId) AS end_source_id, $(ExpectedRows) AS expected_rows, @loaded_rows AS loaded_rows;

IF @loaded_rows <> $(ExpectedRows)
	THROW 50003, 'Chunk row count mismatch. Retain the chunk; do not replay committed batches.', 1;

IF $(EndId) = $(TotalSourceRows)
BEGIN
	SELECT @loaded_rows = COUNT_BIG(*) FROM dbo.[$(TableName)];
	SELECT N'$(TableName)' AS dataset_table, $(ExpectedTotal) AS expected_total,
		   @loaded_rows AS loaded_total;
	IF @loaded_rows <> $(ExpectedTotal)
		THROW 50004, 'Final table row count mismatch. Retain the final chunk for inspection.', 1;
END;
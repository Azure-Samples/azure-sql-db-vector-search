SET NOCOUNT ON;
DECLARE @run_id BINARY(16) = 0x__RUN_HEX__;
DECLARE @query_id INT = 0, @query_count INT = __QUERY_COUNT__, @k INT = __K__;
DECLARE @q VECTOR(1280), @sink INT, @timing_returned INT, @returned INT;
DECLARE @stamp VARBINARY(128);
DECLARE @found TABLE (id INT NOT NULL PRIMARY KEY);
DECLARE @results TABLE (query_id INT, returned INT, matched INT, ground_truth_count INT, latency_us BIGINT NULL);

BEGIN TRY
    WHILE @query_id < @query_count
    BEGIN
        SET @q = NULL;
        SELECT @q = embedding FROM dbo.yfcc___SIZE___queries WHERE id = @query_id;
        IF @q IS NULL
            THROW 50200, 'Query embedding is missing or NULL.', 1;
        DELETE FROM @found;
        SET @stamp = @run_id + CAST(@query_id AS BINARY(4)) + 0x01;
        SET CONTEXT_INFO @stamp;

        SELECT /*vector-latency:__RUN_HEX__*/ @sink = neighbors.id
        FROM (
            SELECT TOP (@k) WITH APPROXIMATE documents.id
            FROM VECTOR_SEARCH(TABLE = dbo.yfcc___SIZE___documents AS documents,
                               COLUMN = embedding, SIMILAR_TO = @q, METRIC = 'euclidean') AS matches
                 WITH (FORCE_ANN_ONLY)
            ORDER BY matches.distance
        ) AS neighbors
        OPTION (MAXDOP 1);
        SET @timing_returned = @@ROWCOUNT;

        SET @stamp = @run_id + CAST(@query_id AS BINARY(4)) + 0x02;
        SET CONTEXT_INFO @stamp;
        INSERT INTO @found (id)
        SELECT neighbors.id
        FROM (
            SELECT TOP (@k) WITH APPROXIMATE documents.id
            FROM VECTOR_SEARCH(TABLE = dbo.yfcc___SIZE___documents AS documents,
                               COLUMN = embedding, SIMILAR_TO = @q, METRIC = 'euclidean') AS matches
                 WITH (FORCE_ANN_ONLY)
            ORDER BY matches.distance
        ) AS neighbors
        OPTION (MAXDOP 1);
        SET @returned = @@ROWCOUNT;
        IF @returned <> @timing_returned OR @returned > @k
            THROW 50201, 'Latency and recall executions returned inconsistent row counts.', 1;

        INSERT INTO @results
        SELECT @query_id, @returned,
               (SELECT COUNT(*) FROM @found AS found
                JOIN dbo.yfcc___SIZE___groundtruth AS truth ON truth.neighbor_id = found.id
                WHERE truth.query_id = @query_id AND truth.rank BETWEEN 1 AND @k),
               (SELECT COUNT(*) FROM dbo.yfcc___SIZE___groundtruth
                WHERE query_id = @query_id AND rank BETWEEN 1 AND @k), NULL;
        IF (SELECT ground_truth_count FROM @results WHERE query_id = @query_id) <> @k
            THROW 50202, 'Ground-truth coverage changed after validation.', 1;
        SET @query_id += 1;
    END;
    SET CONTEXT_INFO 0x00;
    SELECT query_id, returned, matched, ground_truth_count, latency_us FROM @results ORDER BY query_id;
END TRY
BEGIN CATCH
    SET CONTEXT_INFO 0x00;
    SELECT query_id, returned, matched, ground_truth_count, latency_us FROM @results ORDER BY query_id;
    THROW;
END CATCH;
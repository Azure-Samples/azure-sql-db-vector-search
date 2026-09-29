SET NOCOUNT ON;
SET LOCK_TIMEOUT 10000;
DECLARE @query_count INT = ?, @k INT = ?, @document_count BIGINT = ?, @index_name SYSNAME = ?;
IF NOT EXISTS (
    SELECT 1 FROM sys.vector_indexes AS indexes
    JOIN sys.index_columns AS indexed ON indexed.object_id = indexes.object_id AND indexed.index_id = indexes.index_id
    JOIN sys.columns AS columns ON columns.object_id = indexed.object_id AND columns.column_id = indexed.column_id
    WHERE indexes.object_id = OBJECT_ID(N'dbo.yfcc___SIZE___documents') AND indexes.name = @index_name
      AND indexes.is_disabled = 0 AND columns.name = N'embedding'
      AND LOWER(indexes.distance_metric) = 'euclidean' AND LOWER(indexes.vector_index_type) = 'diskann')
    THROW 50210, 'An existing compatible vector index is required; search never creates one.', 1;
IF (SELECT COUNT(*) FROM sys.columns
    WHERE object_id IN (OBJECT_ID(N'dbo.yfcc___SIZE___documents'), OBJECT_ID(N'dbo.yfcc___SIZE___queries'))
    AND name = N'embedding'
      AND vector_dimensions = 1280 AND vector_base_type = 0) <> 2
    THROW 50211, 'Document and query vectors must both be 1280-dimensional float32.', 1;
IF (SELECT COUNT_BIG(*) FROM dbo.yfcc___SIZE___documents) <> @document_count
   OR EXISTS (SELECT 1 FROM dbo.yfcc___SIZE___documents WHERE embedding IS NULL OR id < 0 OR id >= @document_count)
   OR (SELECT COUNT_BIG(DISTINCT id) FROM dbo.yfcc___SIZE___documents) <> @document_count
    THROW 50212, 'The selected document corpus is incomplete or invalid.', 1;
IF (SELECT COUNT_BIG(*) FROM dbo.yfcc___SIZE___queries WHERE id >= 0 AND id < @query_count) <> @query_count
   OR (SELECT COUNT_BIG(DISTINCT id) FROM dbo.yfcc___SIZE___queries WHERE id >= 0 AND id < @query_count) <> @query_count
   OR EXISTS (SELECT 1 FROM dbo.yfcc___SIZE___queries WHERE id >= 0 AND id < @query_count AND embedding IS NULL)
    THROW 50213, 'Selected query IDs must cover 0..query_count-1 with non-null embeddings.', 1;
IF (SELECT COUNT(DISTINCT query_id) FROM dbo.yfcc___SIZE___groundtruth
    WHERE query_id >= 0 AND query_id < @query_count AND rank BETWEEN 1 AND @k) <> @query_count
   OR EXISTS (
       SELECT query_id FROM dbo.yfcc___SIZE___groundtruth
       WHERE query_id >= 0 AND query_id < @query_count AND rank BETWEEN 1 AND @k
       GROUP BY query_id
       HAVING COUNT(*) <> @k OR COUNT(DISTINCT rank) <> @k OR COUNT(DISTINCT neighbor_id) <> @k
           OR MIN(neighbor_id) < 0 OR MAX(neighbor_id) >= @document_count)
    THROW 50214, 'GT top-k must cover all selected queries with ranks 1..k and unique corpus neighbor IDs.', 1;
SELECT @document_count AS document_count, @query_count AS selected_query_count, @k AS validated_gt_depth,
       @index_name AS index_name;
CREATE TABLE resumedocs (
    id INT IDENTITY(1,1) PRIMARY KEY,
    chunkid NVARCHAR(255),
    filename NVARCHAR(255),
    chunk NVARCHAR(MAX),
    embedding VECTOR(1536)
);

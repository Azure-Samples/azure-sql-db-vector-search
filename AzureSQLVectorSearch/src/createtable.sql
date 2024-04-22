CREATE TABLE [dbo].[embeddings](
[Id] [bigint] NULL,
[ProductId] [nvarchar](500) NULL,
[UserId] [nvarchar](50) NULL,
[score] [bigint] null,
[summary] [nvarchar](max) NULL,
[text] [nvarchar](max) NULL,
[combined] [nvarchar](max) NULL,
[vector] [varbinary](8000) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO


CREATE CLUSTERED COLUMNSTORE INDEX [Csindex] ON [dbo].[embeddings] WITH (DROP_EXISTING = OFF, COMPRESSION_DELAY = 0) ON [PRIMARY]
GO
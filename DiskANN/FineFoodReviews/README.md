# Fine Food Reviews — Hybrid Search

Hybrid vector + full-text search over Amazon Fine Food Reviews. Runs on **Azure SQL** (Hyperscale or General Purpose) and **SQL Server 2025**.

**Scenario:** e-commerce shoppers type BOTH paraphrases (*"healthy oatmeal for a picky eater"*) and product SKUs / brand names (*"Merrick Turducken"*). Vector search misses SKUs; full-text misses paraphrases. Hybrid reciprocal-rank fusion (RRF) surfaces rows that win in either signal.

## Files (run in order once, then re-run only `003` to compare queries)

| # | File | Purpose |
|---|---|---|
| 000 | [`000-setup.sql`](000-setup.sql) | Create the `reviews` table, external model, and (optionally) the source-data external table. |
| 001 | [`001-load-and-embed.sql`](001-load-and-embed.sql) | Load 500 sample reviews from [`../../Datasets/Reviews.csv`](../../Datasets/Reviews.csv), then embed via `AI_GENERATE_EMBEDDINGS`. |
| 002 | [`002-diskann-and-fulltext.sql`](002-diskann-and-fulltext.sql) | Build the DiskANN vector index + the full-text catalog/index on `combined`. |
| 003 | [`003-hybrid-search.sql`](003-hybrid-search.sql) | Vector-only, full-text-only, and hybrid-RRF queries side by side. |

Data source: [`../../Datasets/Reviews.csv`](../../Datasets/Reviews.csv) (500k Amazon Fine Food Reviews; the sample uses the first 500 rows). Pre-computed embeddings alternative: [`../../Datasets/FineFoodEmbeddings.csv`](../../Datasets/FineFoodEmbeddings.csv).

## Timing on a 2-vCore Hyperscale instance (500 rows)

- Embedding 500 rows: ~30 s (network to Azure OpenAI).
- DiskANN build: ~2 s.
- Full-text catalog build: ~10 s.
- Hybrid query: ~150 ms.

## Pre-reqs

- An `AIEmbeddings` external model pointing at a `text-embedding-3-small` deployment. See [`../Wikipedia/001-setup-objects.sql`](../Wikipedia/001-setup-objects.sql) for the setup pattern.
- Full-text search enabled on the database.
- Optional Python helpers ([`_load-reviews.py`](_load-reviews.py), [`_embed-reviews.py`](_embed-reviews.py)) for loading the CSV directly from Python instead of via `OPENROWSET`.

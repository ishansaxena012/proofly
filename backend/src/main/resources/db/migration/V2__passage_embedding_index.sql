-- Approximate-nearest-neighbour index for semantic passage retrieval / dedup.
-- HNSW gives better recall/latency than ivfflat and needs no pre-training pass,
-- so it can be created on an empty table at migration time.
CREATE INDEX IF NOT EXISTS idx_passages_embedding_hnsw
    ON passages USING hnsw (embedding vector_cosine_ops);

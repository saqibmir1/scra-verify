-- Performance optimization indexes for verifications table
-- Run this in Supabase SQL Editor to speed up history queries

-- Composite index for user queries with sorting by created_at
CREATE INDEX IF NOT EXISTS verifications_user_created_idx 
ON public.verifications (user_id, created_at DESC);

-- Index for general created_at sorting
CREATE INDEX IF NOT EXISTS verifications_created_at_idx 
ON public.verifications (created_at DESC);

-- Verify indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'verifications'
ORDER BY indexname;


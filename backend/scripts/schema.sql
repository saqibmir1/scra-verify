-- Minimal schema for Supabase tables used by the app

create table if not exists public.user_settings (
  user_id uuid primary key,
  scra_username text,
  scra_password text,
  updated_at timestamptz default now()
);

create table if not exists public.verifications (
  id bigserial primary key,
  user_id uuid null,
  session_id text not null,
  form_data jsonb not null,
  result jsonb not null,
  status text not null default 'completed',
  timestamp timestamptz not null,
  created_at timestamptz not null default now()
);

-- Indexes for faster queries
create index if not exists verifications_user_id_idx on public.verifications (user_id);
create index if not exists verifications_session_id_idx on public.verifications (session_id);
create index if not exists verifications_user_created_idx on public.verifications (user_id, created_at desc);
create index if not exists verifications_created_at_idx on public.verifications (created_at desc);

create table if not exists public.verification_sessions (
  id bigserial primary key,
  session_id text not null unique,
  user_id uuid not null,
  status text not null default 'in_progress',
  progress int not null default 0,
  current_step text null,
  form_data jsonb null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists verification_sessions_user_id_idx on public.verification_sessions (user_id);

create table if not exists public.verification_screenshots (
  id bigserial primary key,
  session_id text not null,
  step text not null,
  filename text not null,
  description text null,
  storage_path text not null,
  uploaded_at timestamptz not null default now()
);

create index if not exists verification_screenshots_session_id_idx on public.verification_screenshots (session_id);

-- ============================================================================
-- STORAGE POLICIES for verification-files bucket
-- ============================================================================
-- Run these SQL commands in Supabase SQL Editor to enable file access from frontend

-- Allow authenticated users to read all files in verification-files bucket
CREATE POLICY "Authenticated users can read verification files"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'verification-files');

-- Allow service role (backend) to manage files
CREATE POLICY "Service role can insert verification files"
ON storage.objects FOR INSERT
TO service_role
WITH CHECK (bucket_id = 'verification-files');

CREATE POLICY "Service role can update verification files"
ON storage.objects FOR UPDATE
TO service_role
USING (bucket_id = 'verification-files');

CREATE POLICY "Service role can delete verification files"
ON storage.objects FOR DELETE
TO service_role
USING (bucket_id = 'verification-files');



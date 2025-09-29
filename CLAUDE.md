# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an SCRA (Servicemembers Civil Relief Act) military status verification system with automated browser-based verification using Playwright and real-time progress tracking. The application consists of a Python FastAPI backend and a Next.js frontend with Supabase integration.

## Development Commands

### Backend (Python/Poetry)
```bash
cd backend
poetry install                          # Install dependencies
poetry run playwright install chromium  # Install browser
./start.sh                              # Start development server (port 8000)
poetry run uvicorn main:app --reload    # Alternative start command
```

### Frontend (Next.js)
```bash
cd frontend
npm install                             # Install dependencies
npm run dev                             # Start development server (port 3000)
npm run build                           # Build for production
npm run lint                            # Run ESLint
```

### Build Testing
```bash
./test-build.sh                         # Test frontend build locally
```

### Deployment
```bash
git push origin main                     # Auto-deploy backend to Railway
vercel --prod                           # Deploy frontend to Vercel (or auto via Git integration)
```

## Architecture Overview

### Technology Stack
- **Backend**: FastAPI (Python) with Playwright browser automation
- **Frontend**: Next.js 15 with React 19, TypeScript, Tailwind CSS
- **Database**: Supabase (PostgreSQL) with real-time subscriptions
- **Authentication**: Supabase Auth with Google OAuth
- **Storage**: Supabase Storage for screenshots and PDFs
- **Deployment**: Railway (backend), Vercel (frontend)

### Core Components

#### Backend (`backend/`)
- `main.py` - FastAPI server with CORS, verification endpoints
- `puppeteer_agent.py` - Playwright automation for SCRA website navigation
- `supabase_client.py` - Supabase service client for database/storage operations
- `database.py` - SQLite fallback for local development
- `dbg_imgs/` - Session-based debug screenshot storage

#### Frontend (`frontend/src/`)
- `app/page.tsx` - Main verification form with real-time progress
- `app/history/` - Verification history with session management
- `components/` - Reusable UI components (Layout, Settings, Health checks)
- `contexts/SupabaseAuthContext.tsx` - Authentication state management
- `hooks/useRealTimeVerification.ts` - Real-time progress polling
- `lib/` - Utilities (types, validation, API client, Supabase client)

### Key Integration Patterns

#### Real-time Progress Flow
1. Frontend submits verification → Backend creates session
2. Playwright agent navigates SCRA website with screenshot capture
3. Screenshots uploaded to Supabase Storage in real-time
4. Frontend polls `/progress/{session_id}` for live updates
5. PDF result captured and stored on completion

#### Authentication & Authorization
- Supabase Auth handles user sessions
- Backend validates user via Supabase JWT
- SCRA credentials stored per-user in Supabase database
- Frontend manages auth state via React Context

#### Error Handling & Debug
- Playwright captures screenshots at each automation step
- Debug images stored locally (`dbg_imgs/`) and in Supabase
- Comprehensive error logging with session isolation
- Health check endpoints for monitoring

## Environment Configuration

### Backend Environment Variables
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
RESIDENTIAL_PROXY_SERVER=your-proxy-url (optional)
RESIDENTIAL_PROXY_USERNAME=proxy-user (optional)
RESIDENTIAL_PROXY_PASSWORD=proxy-pass (optional)
RAILWAY_ENVIRONMENT=production (set by Railway)
PORT=8000 (set by Railway)
```

### Frontend Environment Variables
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_BACKEND_URL=https://your-railway-domain.railway.app
NEXT_PUBLIC_SITE_URL=https://your-project.vercel.app
```

## Development Workflow

### Adding New Features
1. Update TypeScript types in `frontend/src/lib/types.ts`
2. Add validation schemas in `frontend/src/lib/validation.ts`
3. Implement backend endpoints in `backend/main.py`
4. Update Playwright automation in `backend/puppeteer_agent.py` if needed
5. Build frontend components with real-time state management

### Testing Approach
- Backend: Manual testing via `/health` endpoint and direct API calls
- Frontend: Browser testing with live backend integration
- Automation: Use debug mode (`headless=False`) for visual verification
- Build verification via `./test-build.sh` before deployment

### Database Schema (Supabase)
- `verifications` table: Session records with user association
- `user_credentials` table: Per-user SCRA login credentials
- `verification_files` bucket: Screenshots and PDFs with session organization

## Deployment Infrastructure

### Production URLs
- Frontend: https://your-project.vercel.app/
- Backend API: https://your-railway-domain.railway.app
- Debug page: https://your-project.vercel.app/debug-env

### CI/CD Integration
- Backend auto-deploys to Railway on main branch pushes via GitHub integration
- Frontend auto-deploys to Vercel on main branch pushes via GitHub integration
- Environment variables managed via Railway and Vercel dashboards
- Required environment variables: Supabase credentials, proxy settings

## Important Notes

### Browser Automation Considerations
- SCRA website requires specific navigation patterns and agreement handling
- Session isolation critical for concurrent users
- Proxy support for IP rotation if needed
- Screenshot capture enables real-time progress visibility

### State Management
- Frontend uses localStorage for form persistence
- Real-time verification progress via SWR polling
- Supabase real-time subscriptions for instant updates
- Session-based file organization prevents conflicts

### Security Requirements
- SCRA credentials never exposed to frontend
- SSN handling with masking and validation
- Supabase RLS policies for user data isolation
- HTTPS deployment with secure headers
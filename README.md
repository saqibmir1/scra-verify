# SCRA Verify - Military Active Duty Status Verification

A secure military active duty status verification system using the SCRA (Servicemembers Civil Relief Act) database.

## 🚀 Architecture

- **Frontend**: Next.js 15 (TypeScript) - Deployed on Vercel
- **Backend**: FastAPI (Python) - Deployed on Railway  
- **Database**: Supabase (PostgreSQL)
- **Automation**: Playwright for SCRA website interaction

## 📁 Project Structure

```
scra_verify-stable/
├── frontend/          # Next.js frontend application
├── backend/           # FastAPI backend application
└── .github/workflows/ # CI/CD workflows
```

## 🔧 Setup Instructions

### Prerequisites

- Node.js 18+
- Python 3.11+
- Poetry (Python package manager)
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone git@github.com:saqibmir1/scra-verify.git
   cd scra-verify
   ```

2. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Backend Setup**
   ```bash
   cd backend
   poetry install
   poetry run uvicorn main:app --reload
   ```

## 🚀 Deployment

### Automatic Deployment (CI/CD)

This project uses GitHub Actions for automatic deployment:

- **Frontend**: Automatically deploys to Vercel on push to `main`/`master`
- **Backend**: Automatically deploys to Railway on push to `main`/`master`
- **Tests**: Runs on all pushes and pull requests

### Required GitHub Secrets

Add these secrets to your GitHub repository (`Settings` → `Secrets and variables` → `Actions`):

#### Vercel Secrets
```
VERCEL_TOKEN=your_vercel_token
VERCEL_ORG_ID=team_0GktK6U5SMqU7QuW54CCDulM
VERCEL_PROJECT_ID=prj_fg8crSDy2Es8glvihBzYpVU8WqMg
```

#### Railway Secrets
```
RAILWAY_TOKEN=your_railway_token
RAILWAY_SERVICE_ID=your_service_id
```

### Getting the Secrets

#### Vercel Token
1. Go to [Vercel Account Settings](https://vercel.com/account/tokens)
2. Create a new token with appropriate permissions
3. Copy the token value

#### Railway Token
1. Go to [Railway Account Settings](https://railway.app/account/tokens)
2. Create a new token
3. Copy the token value

#### Railway Service ID
1. Deploy your backend to Railway manually first
2. Get the service ID from the Railway dashboard URL

## 🌐 Live URLs

- **Frontend**: https://frontend-ruddy-sigma-11.vercel.app
- **Backend**: (To be deployed)
- **CI/CD**: ✅ Testing automatic deployment

## 📝 Environment Variables

### Frontend (Vercel)
```
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_BACKEND_URL=your_backend_url
NEXT_PUBLIC_SITE_URL=your_frontend_url
```

### Backend (Railway)
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
DATABASE_URL=your_database_url
```

## 🔄 Workflow

1. **Push to main/master** → Triggers deployment
2. **Create PR** → Runs tests and creates preview deployment
3. **Merge PR** → Deploys to production

## 🛠️ Manual Deployment

If needed, you can deploy manually:

```bash
# Frontend
cd frontend
vercel --prod

# Backend
cd backend
railway deploy
```

## 📊 Features

- ✅ Single record SCRA verification
- ✅ Multi-record CSV batch processing
- ✅ PDF certificate generation and splitting
- ✅ Real-time verification tracking
- ✅ User authentication (Supabase Auth)
- ✅ Verification history
- ✅ Screenshot capture for debugging

## 🔒 Security

- Environment variables for sensitive data
- Supabase Row Level Security (RLS)
- CORS configuration
- Input validation and sanitization

## 📈 Monitoring

- Vercel Analytics (Frontend)
- Railway Metrics (Backend)
- Supabase Dashboard (Database)

---


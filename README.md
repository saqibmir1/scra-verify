# 🎖️ SCRA Verify - Military Active Duty Status Verification

A complete, production-ready system for verifying military active duty status using the official SCRA (Servicemembers Civil Relief Act) database. Features automated browser-based verification, real-time progress tracking, PDF certificate generation, and comprehensive verification history.

![SCRA Verify](https://img.shields.io/badge/Status-Production-green)
![License](https://img.shields.io/badge/License-MIT-blue)

## 🌟 Features

### Core Verification
- ✅ **Single Record Verification** - Verify individual service members instantly
- ✅ **Multi-Record Batch Processing** - Upload CSV files to verify up to 1000 records at once
- ✅ **Automated SCRA Website Interaction** - Uses Playwright for reliable automation
- ✅ **PDF Certificate Generation** - Automatic download and storage of verification certificates
- ✅ **Multi-Record PDF Splitting** - Automatically splits batch PDFs into individual records

### Real-Time Features
- 📸 **Live Screenshot Capture** - See what's happening during verification in real-time
- 📊 **Progress Tracking** - Real-time progress updates via WebSocket
- 🔄 **Session Management** - Track and manage verification sessions
- 📜 **Verification History** - Complete audit trail of all verifications

### User Experience
- 🔐 **Google OAuth Authentication** - Secure login via Supabase Auth
- 💾 **Persistent Storage** - All results, PDFs, and screenshots stored in Supabase
- 🎨 **Modern UI** - Beautiful, responsive interface built with Next.js 15
- ⚡ **Fast Performance** - Optimized for speed and reliability

### Technical Features
- 🌐 **Geo-Restriction Bypass** - Supports residential proxy for US-only SCRA website access
- 🔒 **Secure** - Row-level security, encrypted credentials, CORS protection
- 📱 **Responsive** - Works on desktop, tablet, and mobile
- 🐛 **Debug Mode** - Comprehensive debugging with screenshots and logs

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SCRA Verify System                    │
└─────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│   Frontend       │────────▶│    Backend       │
│   Next.js 15     │  HTTPS  │    FastAPI       │
│   (Vercel)       │◀────────│    (AWS EC2)     │
└──────────────────┘         └──────────────────┘
         │                            │
         │                            │ Playwright
         │                            ▼
         │                   ┌──────────────────┐
         │                   │  SCRA Website    │
         │                   │  (via Proxy)     │
         │                   └──────────────────┘
         │
         ▼
┌──────────────────┐
│    Supabase      │
│  - PostgreSQL    │
│  - Auth (OAuth)  │
│  - Storage       │
└──────────────────┘
```

### Tech Stack

**Frontend**
- Next.js 15 (React 19, App Router)
- TypeScript
- Tailwind CSS
- Supabase Client SDK

**Backend**
- FastAPI (Python 3.11)
- Playwright (Browser Automation)
- Poetry (Dependency Management)
- Supabase Python SDK

**Infrastructure**
- **Frontend Hosting**: Vercel
- **Backend Hosting**: AWS EC2 (Ubuntu)
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Auth**: Supabase Auth (Google OAuth)
- **SSL**: Let's Encrypt (via Certbot)
- **Reverse Proxy**: Nginx
- **VPN**: NordVPN (dedicated US IP)

---

## 📁 Project Structure

```
scra-verify/
├── frontend/                 # Next.js frontend
│   ├── src/
│   │   ├── app/             # Next.js 15 App Router
│   │   │   ├── page.tsx     # Main verification page
│   │   │   ├── history/     # Verification history
│   │   │   └── debug-env/   # Environment debug page
│   │   ├── components/      # React components
│   │   │   ├── Layout.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RealTimeScreenshots.tsx
│   │   │   └── SettingsModal.tsx
│   │   ├── contexts/        # React contexts
│   │   │   └── SupabaseAuthContext.tsx
│   │   ├── hooks/           # Custom React hooks
│   │   │   └── useRealTimeVerification.ts
│   │   └── lib/             # Utilities
│   │       ├── supabase.ts
│   │       ├── backend-api.ts
│   │       ├── validation.ts
│   │       └── types.ts
│   ├── package.json
│   └── next.config.js
│
├── backend/                  # FastAPI backend
│   ├── main.py              # FastAPI app & routes
│   ├── puppeteer_agent.py   # Playwright automation
│   ├── supabase_client.py   # Supabase integration
│   ├── csv_processor.py     # CSV to fixed-width converter
│   ├── pdf_splitter.py      # Multi-record PDF splitter
│   ├── database.py          # Database models
│   ├── Dockerfile           # Production container
│   ├── pyproject.toml       # Poetry dependencies
│   └── scripts/
│       └── init_supabase.py # Database setup script
│
└── .github/
    └── workflows/
        └── deploy-frontend.yml  # Vercel CI/CD
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **Poetry** (Python package manager)
- **Git**
- **Supabase Account** (free tier works)
- **Google OAuth Credentials**
- **SCRA Website Credentials**

### 1. Clone Repository

```bash
git clone git@github.com:saqibmir1/scra-verify.git
cd scra-verify
```

### 2. Frontend Setup (Local Development)

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
cat > .env << 'EOF'
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_DEV_MODE=true
EOF

# Start development server
npm run dev
```

Visit `http://localhost:3000`

### 3. Backend Setup (Local Development)

```bash
cd backend

# Install dependencies
poetry install

# Install Playwright browsers
poetry run playwright install chromium

# Create .env file
cat > .env << 'EOF'
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SCRA_USERNAME=your_scra_username
SCRA_PASSWORD=your_scra_password
NODE_ENV=development
PORT=8000
HEADLESS=false
EOF

# Start development server
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs on `http://localhost:8000`

### 4. Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run the database setup script:

```bash
cd backend
poetry run python scripts/init_supabase.py
```

3. Enable Google OAuth:
   - Go to Supabase Dashboard → Authentication → Providers
   - Enable Google
   - Add Google OAuth credentials
   - Add redirect URL: `https://your-project.supabase.co/auth/v1/callback`

4. Create Storage Bucket:
   - Go to Storage → Create bucket
   - Name: `verification-files`
   - Set as public

---

## 🌐 Production Deployment

### Frontend (Vercel)

1. **Connect to Vercel:**
   - Push code to GitHub
   - Import project on Vercel
   - Select `frontend` as root directory

2. **Environment Variables:**
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
   NEXT_PUBLIC_BACKEND_URL=https://scra.yourdomain.com
   NEXT_PUBLIC_SITE_URL=https://your-app.vercel.app
   NEXT_PUBLIC_DEV_MODE=false
   ```

3. **Deploy:**
   - Vercel auto-deploys on push to `master`
   - Or manually: `vercel --prod`

### Backend (AWS EC2)

#### Initial Setup

1. **Launch EC2 Instance:**
   - Instance type: t3.small (or larger)
   - OS: Amazon Linux 2023
   - Security Groups: Open ports 22, 80, 443, 8000

2. **Install Dependencies:**
```bash
# SSH into EC2
ssh ec2-user@your-ec2-ip

# Update system
sudo yum update -y

# Install Docker
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Install nginx
sudo yum install nginx -y

# Install OpenVPN (for VPN access)
sudo yum install openvpn -y

# Logout and login for docker group
exit
ssh ec2-user@your-ec2-ip
```

3. **Clone Repository:**
```bash
git clone https://github.com/saqibmir1/scra-verify.git
cd scra-verify/backend
```

4. **Setup VPN (NordVPN):**
```bash
# Upload NordVPN config file
# From local: scp nordvpn-us.ovpn ec2-user@your-ec2-ip:~/scra-verify/backend/

# Create auth file
echo -e "your_nordvpn_username\nyour_nordvpn_password" > ~/vpn-auth.txt

# Start VPN
sudo openvpn --config nordvpn-us.ovpn --auth-user-pass ~/vpn-auth.txt --daemon

# Verify VPN connection
sleep 10
curl ifconfig.me  # Should show NordVPN IP
```

5. **Create .env File:**
```bash
cat > .env << 'EOF'
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SCRA_USERNAME=your_scra_username
SCRA_PASSWORD=your_scra_password
NODE_ENV=production
PORT=8000
HEADLESS=true
RESIDENTIAL_PROXY_SERVER=brd.superproxy.io:33335
RESIDENTIAL_PROXY_USERNAME=your_brightdata_username
RESIDENTIAL_PROXY_PASSWORD=your_brightdata_password
EOF
```

6. **Build & Run Docker Container:**
```bash
# Build image
docker build -t scra-backend .

# Run container
docker run -d \
  --name scra-backend \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  --network host \
  scra-backend

# Check logs
docker logs -f scra-backend
```

7. **Setup Domain & SSL:**

Point your domain to EC2:
```bash
# In your DNS provider (e.g., Namecheap, Cloudflare)
# Add A Record:
# Name: scra
# Type: A
# Value: your-ec2-ip
```

Configure Nginx:
```bash
# Create nginx config
sudo tee /etc/nginx/conf.d/scra-backend.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name scra.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increased timeouts for long-running requests
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
EOF

# Test and start nginx
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
```

Get SSL Certificate:
```bash
# Install certbot
sudo yum install python3 augeas-libs -y
sudo python3 -m venv /opt/certbot/
sudo /opt/certbot/bin/pip install --upgrade pip
sudo /opt/certbot/bin/pip install certbot certbot-nginx
sudo ln -s /opt/certbot/bin/certbot /usr/bin/certbot

# Get certificate
sudo certbot --nginx -d scra.yourdomain.com

# Auto-renewal (certbot sets this up automatically)
```

#### Updating Backend

```bash
# SSH into EC2
ssh ec2-user@your-ec2-ip
cd scra-verify/backend

# Pull latest changes
git pull origin master

# Rebuild and restart
docker build -t scra-backend .
docker stop scra-backend
docker rm scra-backend
docker run -d \
  --name scra-backend \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  --network host \
  scra-backend

# Check logs
docker logs -f scra-backend
```

---

## 🔐 Environment Variables

### Frontend (.env)
```bash
# Supabase (public keys)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key

# Backend API
NEXT_PUBLIC_BACKEND_URL=https://scra.yourdomain.com

# Site URL
NEXT_PUBLIC_SITE_URL=https://your-app.vercel.app

# Development mode (set to false in production)
NEXT_PUBLIC_DEV_MODE=false
```

### Backend (.env)
```bash
# Supabase (service role key - keep secret!)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# SCRA credentials
SCRA_USERNAME=your_scra_username
SCRA_PASSWORD=your_scra_password

# Environment
NODE_ENV=production
PORT=8000

# Browser settings
HEADLESS=true

# Residential Proxy (optional, for geo-restriction bypass)
RESIDENTIAL_PROXY_SERVER=brd.superproxy.io:33335
RESIDENTIAL_PROXY_USERNAME=your_proxy_username
RESIDENTIAL_PROXY_PASSWORD=your_proxy_password
```

---

## 📖 How to Use

### Single Record Verification

1. **Login** with Google OAuth
2. Click **"Single Record Verification"**
3. Fill in service member details:
   - First Name, Last Name, Middle Name (optional), Suffix (optional)
   - SSN (9 digits)
   - Date of Birth (YYYYMMDD)
   - Active Duty Status Date (YYYYMMDD)
4. Click **"Verify"**
5. Watch real-time progress and screenshots
6. Download PDF certificate when complete

### Multi-Record Batch Verification

1. **Prepare CSV file** with columns:
   - `SSN` (required)
   - `FirstName` (required)
   - `LastName` (required)
   - `MiddleName` (optional)
   - `DateOfBirth` (YYYYMMDD format)
   - `ActiveDutyStatusDate` (YYYYMMDD format)
   - `CustomerRecordId` (optional, for tracking)

2. Click **"Multi-Record Verification"**
3. Upload CSV file
4. System converts to SCRA fixed-width format
5. Review and confirm
6. Click **"Submit for Verification"**
7. Wait for batch processing (can take 5-10 minutes for 1000 records)
8. Download results:
   - Combined PDF (all results)
   - Individual PDFs (split automatically)

### View History

1. Click **"History"** in navigation
2. See all past verifications with:
   - Service member details
   - Verification status
   - Date/time
   - Success rate statistics
3. Click any record to:
   - View full details
   - Download PDF
   - View screenshots
   - Delete record

---

## 🔧 API Documentation

### Endpoints

#### `GET /health`
Health check endpoint
```json
{
  "status": "healthy",
  "service": "SCRA Military Verification API",
  "version": "1.0.0",
  "database": "connected",
  "storage": "connected"
}
```

#### `POST /verify`
Single record verification
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "middleName": "A",
  "suffix": "Jr",
  "ssn": "123456789",
  "dateOfBirth": "19900101",
  "activeDutyDate": "20200101"
}
```

#### `POST /csv-to-fixed-width`
Convert CSV to SCRA fixed-width format
- Upload CSV file
- Returns fixed-width .txt file

#### `POST /multi-record-verify`
Multi-record batch verification
```json
{
  "fixed_width_content": "..."
}
```

---

## 🐛 Troubleshooting

### Common Issues

**1. CORS Errors**
- Ensure backend `allow_origins` includes your frontend domain
- Check nginx CORS headers

**2. Timeout Errors (504)**
- Increase nginx timeout settings
- Check VPN/proxy connection

**3. Authentication Fails**
- Verify Google OAuth redirect URLs in Supabase
- Check Supabase project settings

**4. Playwright Browser Not Found**
- Run `poetry run playwright install chromium`
- Check Dockerfile has correct dependencies

**5. VPN Connection Issues**
- Verify NordVPN credentials
- Check OpenVPN logs: `sudo journalctl -u openvpn`

### Debug Mode

Enable debug mode for detailed logs:
```bash
# Frontend
NEXT_PUBLIC_DEV_MODE=true

# Backend
NODE_ENV=development
HEADLESS=false  # See browser in action
```

---

## 🔒 Security Considerations

- ✅ **HTTPS Everywhere** - SSL certificates on all endpoints
- ✅ **Environment Variables** - No credentials in code
- ✅ **Row-Level Security** - Supabase RLS policies
- ✅ **CORS Protection** - Whitelist allowed origins
- ✅ **Input Validation** - All user inputs validated
- ✅ **Authentication Required** - Google OAuth mandatory
- ✅ **Service Role Key** - Backend only, never exposed to frontend

---

## 📊 Monitoring & Logs

### Frontend (Vercel)
- View logs: Vercel Dashboard → Deployments → Logs
- Analytics: Vercel Dashboard → Analytics

### Backend (EC2)
```bash
# Docker logs
docker logs -f scra-backend

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# System logs
journalctl -u nginx -f
```

### Database (Supabase)
- Dashboard: https://supabase.com/dashboard
- Query logs in SQL Editor
- Monitor storage usage

---

## 🚨 Production Checklist

Before going live:

- [ ] SSL certificates installed and auto-renewing
- [ ] All environment variables set correctly
- [ ] Supabase RLS policies enabled
- [ ] Google OAuth configured with production URLs
- [ ] VPN/Proxy working and tested
- [ ] Nginx timeouts increased (600s)
- [ ] Docker container auto-restart enabled
- [ ] Monitoring and alerting setup
- [ ] Backup strategy for database
- [ ] Security group rules minimized
- [ ] Rate limiting configured (if needed)

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

This is a private project. Contact the repository owner for access.

---

## 📧 Support

For issues or questions:
- Open an issue on GitHub
- Contact: saqibmir1@github.com

---

**Built with ❤️ using Next.js, FastAPI, Supabase, and Playwright**

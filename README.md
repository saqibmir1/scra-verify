# SCRA Military Status Verification

Automated SCRA (Servicemembers Civil Relief Act) verification system using Puppeteer browser automation with real-time progress tracking and session management.

## 🚀 Live Deployment

| Service | Environment | URL | Status |
|---------|------------|-----|--------|
| **Frontend** | Production | [https://scra-b341a.web.app/](https://scra-b341a.web.app/) | ✅ Live |
| **Backend API** | Production | [https://scra-backend-xnsgnxzzsa-uc.a.run.app](https://scra-backend-xnsgnxzzsa-uc.a.run.app) | ✅ Live |
| **Debug Page** | Production | [https://scra-b341a.web.app/debug-env](https://scra-b341a.web.app/debug-env) | 🔧 Debug |

### Deployment Infrastructure
- **Frontend**: Firebase Hosting with Next.js server-side rendering
- **Backend**: Google Cloud Run with auto-scaling containers  
- **Database**: Supabase (PostgreSQL) with real-time subscriptions
- **Storage**: Supabase Storage for verification files and screenshots
- **CI/CD**: GitHub Actions automated deployments

## 🤖 Automated Deployments

This project uses **GitHub Actions** for continuous deployment:

- **Frontend Deployment**: Automatically deploys to Firebase Hosting on pushes to `main` branch
- **Backend Deployment**: Automatically deploys to Google Cloud Run on pushes to `main` branch  
- **Testing Pipeline**: Runs tests and linting on all pull requests

### GitHub Actions Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy-frontend.yml` | Push to `main` (frontend changes) | Deploy Next.js app to Firebase Hosting |
| `deploy-backend.yml` | Push to `main` (backend changes) | Deploy FastAPI app to Google Cloud Run |
| `test-and-lint.yml` | Push/PR to `main` | Run tests, linting, and type checking |

## Features

- 🎭 **Puppeteer Automation**: Full browser automation for SCRA website navigation
- 📸 **Live Debug Display**: Real-time screenshots showing automation progress  
- 📄 **PDF Capture**: Automatic verification PDF download and serving
- 🗂️ **Session Management**: Organized session-based file storage
- 📋 **History Tracking**: SQLite database with verification history
- 🔄 **State Persistence**: localStorage-based state management
- 🎨 **Responsive Interface**: Clean UI with form validation

## Installation

### Prerequisites
- Node.js 20.x or later
- Python 3.11 or later  
- Valid SCRA credentials
- Google Cloud account (for backend deployment)
- Firebase project (for frontend deployment)

### Backend Setup

```bash
cd backend

# Install Python dependencies using Poetry
poetry install

# Or install with pip
pip install fastapi uvicorn playwright python-dotenv

# Install Playwright browser
playwright install chromium

# Create environment file
cp .env.example .env

# Edit .env with your SCRA credentials:
SCRA_USERNAME=your_scra_username
SCRA_PASSWORD=your_scra_password

# Start backend server
python main.py
# or
poetry run python main.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start frontend development server
npm run dev
```

Visit `http://localhost:3000` to access the application.

## Usage

### Basic Verification Flow

1. **Enter Information**: Fill in service member details (name, SSN, dates)
2. **Live Monitoring**: Watch real-time automation progress with screenshots
3. **PDF Results**: Download verification PDF when complete
4. **History Access**: View past verifications in the History section

### Form Fields

- **Names**: First/Last name (required), Middle name, Suffix (optional)
- **SSN**: 9-digit Social Security Number with auto-formatting
- **Dates**: Date of Birth and Active Duty Date (MM/DD/YYYY format)

### State Persistence

The application automatically saves:
- Form data while typing
- Verification results and status
- Debug screenshots and progress
- Selected image preview
- Session information

Navigate away and return without losing progress.

## Architecture

### Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI server & API endpoints
│   ├── puppeteer_agent.py         # Puppeteer automation engine
│   ├── database.py                # SQLite history management
│   └── dbg_imgs/                  # Session-based debug storage
│       └── {session_id}/          # Individual session folders
│           ├── *.png              # Debug screenshots
│           ├── scra_result.pdf    # Verification PDF
│           └── results_raw.*      # Raw debug data
└── frontend/
    ├── src/app/
    │   ├── page.tsx               # Main verification interface
    │   └── history/page.tsx       # Verification history
    ├── src/components/
    │   └── Layout.tsx             # Navigation sidebar
    └── src/lib/
        ├── types.ts               # TypeScript interfaces
        ├── validation.ts          # Zod form schemas
        └── date-utils.ts          # Date formatting utilities
```

### API Endpoints

- `POST /verify` - Start verification with person data
- `GET /pdf/{session_id}` - Download verification PDF
- `GET /debug-images/{session_id}` - List session debug images
- `GET /image/{session_id}/{filename}` - Serve specific image
- `GET /history` - Get verification history with stats
- `DELETE /history/{record_id}` - Delete verification record
- `GET /health` - Server health & credential status

## Automation Engine

### Puppeteer Features

- **Smart Login Detection**: 20+ form selector strategies
- **Agreement Handling**: Automatic privacy/terms acceptance
- **Date Input Support**: Handles calendar widgets and text fields
- **SSN Confirmation**: Fills repeated confirmation fields
- **PDF Interception**: Captures downloaded verification PDFs
- **Error Recovery**: Comprehensive error handling and screenshots

### Debug Capabilities

- **Step-by-Step Screenshots**: Visual progress tracking
- **Session Organization**: Each verification in separate folder
- **Raw Data Capture**: HTML/text dumps for troubleshooting
- **Real-time Polling**: Frontend polls for new images during automation

### Agreement Detection

Automatically handles common government website patterns:
- Cookie acceptance banners
- Privacy Act statements  
- Terms of service agreements
- Modal dialogs and overlays
- Required checkboxes

## Configuration

### Environment Variables

**Backend (.env)**:
```env
SCRA_USERNAME=your_scra_username
SCRA_PASSWORD=your_scra_password
HEADLESS=true  # Set to false for visual debugging
```

### Debug Mode

For visual debugging, set `headless=False` in `puppeteer_agent.py` or `HEADLESS=false` in your environment.

## Security

- **Server-side Credentials**: SCRA credentials never exposed to client
- **SSN Protection**: Masked in logs and stored with last 4 digits only
- **Session Isolation**: Each verification in separate folder
- **Input Validation**: Comprehensive form validation with Zod
- **HTTPS Ready**: Configured for secure deployment

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify SCRA credentials in `.env`
   - Check account access and IP restrictions
   - Review debug screenshots for login issues

2. **Browser Automation**
   - Ensure Playwright Chromium is installed: `playwright install chromium`
   - Check for permission issues with debug folder
   - Try headful mode for visual debugging

3. **PDF Download Issues**
   - Verify download permissions in session folder
   - Check browser download settings
   - Review automation screenshots for download dialogs

4. **Frontend Connection**
   - Confirm backend is running on port 8000
   - Check CORS configuration for localhost:3000
   - Verify API endpoint accessibility

### Debug Information

- **Live Screenshots**: Monitor automation progress in real-time
- **Session Logs**: Check backend console for detailed automation logs
- **History Database**: SQLite database tracks all attempts with status
- **Error Screenshots**: Captured automatically on failures

## 🔧 GitHub Actions Setup

To enable automated deployments, configure these secrets in your GitHub repository:

### Required Secrets

1. **Frontend Deployment**:
   ```
   FIREBASE_SERVICE_ACCOUNT_SCRA_B341A=<Firebase service account JSON>
   ```

2. **Backend Deployment**:
   ```
   GOOGLE_CLOUD_SERVICE_ACCOUNT_KEY=<GCP service account JSON>
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=<Supabase service role key>
   RESIDENTIAL_PROXY_SERVER=<Proxy server URL>
   RESIDENTIAL_PROXY_USERNAME=<Proxy username>
   RESIDENTIAL_PROXY_PASSWORD=<Proxy password>
   ```

### Manual Deployment Commands

If you need to deploy manually:

```bash
# Deploy frontend
cd frontend
firebase deploy --only hosting

# Deploy backend  
gcloud builds submit --config cloudbuild-artifact.yaml
```

## Development

### Testing

```bash
# Backend health check
curl http://localhost:8000/health

# Frontend development
npm run dev

# Check verification endpoint
curl -X POST http://localhost:8000/verify -H "Content-Type: application/json" -d '{...}'
```

### Building for Production

```bash
# Frontend build
npm run build
npm start

# Backend with gunicorn (example)
pip install gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## Technical Details

### SCRA Integration

The system navigates the official SCRA website at `https://scra.dmdc.osd.mil/scra/` using:
- Session-based authentication
- Form automation with retry logic
- Agreement handling for government compliance
- PDF capture from browser downloads

### Data Flow

1. **Frontend Form** → validates input → sends to API
2. **Backend API** → creates session → starts Puppeteer
3. **Puppeteer Agent** → navigates SCRA → fills forms → captures PDF
4. **Database Storage** → saves verification record
5. **Real-time Updates** → frontend polls for debug images
6. **Results Display** → shows status and downloadable PDF

### Browser Automation Stages

1. **Main Page Load**: Navigate to SCRA, handle agreements
2. **Authentication**: Login with credentials, verify success  
3. **Form Navigation**: Access single-record verification
4. **Data Entry**: Fill personal information, handle date inputs
5. **Submission**: Submit form, handle agreements, capture results
6. **PDF Processing**: Intercept download, save to session folder
7. **Results Extraction**: Parse verification status, finalize

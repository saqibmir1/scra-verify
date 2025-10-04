"""
FastAPI server for SCRA military active duty verification
Updated: Testing Railway deployment with Project Token
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from supabase_client import get_supabase_service
from puppeteer_agent import PuppeteerSCRAAgent
from csv_processor import CSVProcessor


# Initialize FastAPI app
app = FastAPI(
    title="SCRA Military Verification API",
    description="API for military active duty status verification",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:3001",
        "https://scra-verify.vercel.app",
        "https://saqibmir.site",
        "http://saqibmir.site",
        "https://scra.saqibmir.site",
        "http://scra.saqibmir.site"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["x-record-count", "x-validation-success", "content-disposition"],
    allow_origin_regex=r"https://.*\.vercel\.app$"
)

# Initialize Supabase service
supabase_service = get_supabase_service()

# Pydantic models
class PersonData(BaseModel):
    firstName: str
    lastName: str
    middleName: Optional[str] = ""
    suffix: Optional[str] = ""
    ssn: str
    dateOfBirth: str
    activeDutyDate: str


class MultiRecordVerifyData(BaseModel):
    fixed_width_content: str


class DebugImage(BaseModel):
    filename: str
    step: str
    description: str
    timestamp: float
    url: str


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "active",
        "service": "SCRA Military Verification API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for frontend"""
    try:
        svc = get_supabase_service()
        storage_ok = svc.test_storage_connection()
        tables = svc.check_required_tables()
        all_tables_ok = all(tables.values()) if tables else False

        status = "healthy" if (storage_ok and all_tables_ok) else ("partial" if storage_ok or all_tables_ok else "error")

        return {
            "status": status,
            "service": "SCRA Military Verification API",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "database": "connected" if all_tables_ok else "missing_tables",
            "required_tables": tables,
            "storage": "connected" if storage_ok else "missing_bucket",
            "storage_bucket": "verification-files"
        }
    except Exception as e:
        return {
            "status": "error",
            "service": "SCRA Military Verification API",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "database": "error",
            "storage": "error",
            "error": str(e)
        }









@app.post("/verify")
async def verify_active_duty(person_data: PersonData, request: Request, authorization: Optional[str] = Header(None)):
    """
    Verify military active duty status using SCRA database
    """
    try:
        # Check if we're in development mode first
        is_development = os.getenv("NODE_ENV") == "development"
        
        # Get user_id from request headers (sent by frontend) - skip in dev mode
        user_id = request.headers.get('x-user-id')
        
        if not is_development and not user_id:
            raise HTTPException(
                status_code=400,
                detail="User ID required for verification. Please ensure you are logged in."
            )
        
        # Use mock user ID in development mode
        if is_development and not user_id:
            user_id = "dev-user-123"
        
        
        # Get SCRA credentials - try environment variables first, then user settings
        
        # Try environment variables first (works in both dev and production)
        username = os.getenv("SCRA_USERNAME")
        password = os.getenv("SCRA_PASSWORD")
        
        if username and password:
            pass
        else:
            # Fall back to user settings from Supabase if env vars not available
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="SCRA credentials not found in environment variables and no user provided for database lookup."
                )
            # Try to get credentials from user's settings in Supabase
            try:
                user_settings = await supabase_service.get_user_settings(user_id)
                if not user_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="SCRA credentials not found. Please set up your credentials in settings."
                    )
                
                username = user_settings.get('scraUsername') or user_settings.get('scra_username')
                password = user_settings.get('scraPassword') or user_settings.get('scra_password')
                
                if not username or not password:
                    raise HTTPException(
                        status_code=400,
                        detail="SCRA credentials incomplete. Please update your credentials in settings."
                    )
                
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve user credentials. Please try again."
                )
        
        # Create session ID for this verification
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize Puppeteer agent with user_id for real-time updates
        agent = PuppeteerSCRAAgent(username, password, user_id)
        agent.session_id = session_id
        
        # Convert Pydantic model to dict for the agent
        person_dict = person_data.model_dump()
        
        # Perform verification
        result = await agent.verify_person(person_dict)
        
        # Screenshots and PDF data are now included in the result
        if result.get('success'):
            automation_result = result.get('automationResult', {})
            
            # Mark that files are included in response
            automation_result['files_included'] = True
            automation_result['delivery_method'] = 'direct_response'
        
        # Save to Supabase with user_id
        verification_data = {
            'sessionId': session_id,
            'userId': user_id,
            'formData': person_dict,
            'result': result,
            'status': 'completed' if result.get('success') else 'failed',
            'timestamp': datetime.now().isoformat()
        }
        
        # Save verification to database for history
        try:
            await supabase_service.save_verification(verification_data)
        except Exception:
            # Continue anyway - frontend might also save
            pass
        
        # Restructure result for frontend compatibility
        if result.get('success'):
            # Move automationResult to the top level for easy access
            automation_result = result.get('automationResult', {})
            automation_result['sessionId'] = session_id
            
            # Ensure proper data structure for frontend
            result['data'] = {
                'automationResult': automation_result,
                'eligibility': result.get('eligibility', {})
            }
            
            # Keep debug files for now - they'll be cleaned up via separate endpoint or timeout
            agent.keep_debug_files()
        else:
            # Keep debug files for failed verifications
            if 'agent' in locals():
                agent.keep_debug_files()
        
        return result
        
    except Exception as e:
        
        error_result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        # Still save failed attempts to Supabase for history tracking
        try:
            error_verification_data = {
                'sessionId': session_id if 'session_id' in locals() else datetime.now().strftime("%Y%m%d_%H%M%S"),
                'userId': user_id if 'user_id' in locals() else None,
                'formData': person_data.model_dump(),
                'result': error_result,
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
            
            if error_verification_data['userId']:
                await supabase_service.save_verification(error_verification_data)
                
        except Exception as save_error:
            pass
        
        return error_result


@app.post("/csv-to-fixed-width")
async def convert_csv_to_fixed_width(file: UploadFile = File(...)):
    """
    Convert uploaded CSV file to SCRA fixed-width format
    Returns the fixed-width .txt content if validation passes, otherwise returns validation errors
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="File must be a CSV file"
            )
        
        # Read file content
        csv_content = await file.read()
        csv_text = csv_content.decode('utf-8')
        
        # Process CSV
        processor = CSVProcessor()
        validation_result = processor.validate_csv_file(csv_text)
        
        if not validation_result['valid']:
            return {
                "success": False,
                "validation_errors": validation_result['errors'],
                "error_count": validation_result['error_count'],
                "timestamp": datetime.now().isoformat()
            }
        
        if validation_result['record_count'] == 0:
            return {
                "success": False,
                "validation_errors": ["No valid records found in CSV file"],
                "error_count": 1,
                "timestamp": datetime.now().isoformat()
            }
        
        # Generate fixed-width content
        from csv_processor import process_csv_for_scra
        fixed_width_content, records, errors = process_csv_for_scra(csv_text)
        
        if errors:
            return {
                "success": False,
                "validation_errors": errors,
                "error_count": len(errors),
                "timestamp": datetime.now().isoformat()
            }
        
        # Return fixed-width content as downloadable file
        # Use short filename format to meet 30 character limit
        timestamp = datetime.now().strftime('%m%d%H%M')  # MMDDHHMM format
        filename = f"scra_{timestamp}.txt"  # e.g., "scra_01151030.txt" (16 chars)
        
        return Response(
            content=fixed_width_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Record-Count": str(len(records)),
                "X-Validation-Success": "true"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV file: {str(e)}"
        )


@app.post("/multi-record-verify")
async def verify_multi_records(data: MultiRecordVerifyData, request: Request, authorization: Optional[str] = Header(None)):
    """
    Verify multiple records using fixed-width text content for SCRA database
    """
    try:
        # Check if we're in development mode first
        is_development = os.getenv("NODE_ENV") == "development"
        
        # Get user_id from request headers (sent by frontend) - skip in dev mode
        user_id = request.headers.get('x-user-id')
        
        if not is_development and not user_id:
            raise HTTPException(
                status_code=400,
                detail="User ID required for verification. Please ensure you are logged in."
            )
        
        # Use mock user ID in development mode
        if is_development and not user_id:
            user_id = "dev-user-123"
        
        # Validate fixed-width content
        if not data.fixed_width_content.strip():
            raise HTTPException(
                status_code=400,
                detail="Fixed-width content cannot be empty"
            )
        
        # Parse records from fixed-width content for counting
        lines = [line for line in data.fixed_width_content.split('\n') if line.strip()]
        record_count = len(lines)
        
        if record_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No records found in fixed-width content"
            )
        
        # Get SCRA credentials - try environment variables first, then user settings
        username = os.getenv("SCRA_USERNAME")
        password = os.getenv("SCRA_PASSWORD")
        
        if username and password:
            pass
        else:
            # Fall back to user settings from Supabase if env vars not available
            if not user_id:
                raise HTTPException(
                    status_code=400,
                    detail="SCRA credentials not found in environment variables and no user provided for database lookup."
                )
            # Try to get credentials from user's settings in Supabase
            try:
                user_settings = await supabase_service.get_user_settings(user_id)
                if not user_settings:
                    raise HTTPException(
                        status_code=400,
                        detail="SCRA credentials not found. Please set up your credentials in settings."
                    )
                
                username = user_settings.get('scraUsername') or user_settings.get('scra_username')
                password = user_settings.get('scraPassword') or user_settings.get('scra_password')
                
                if not username or not password:
                    raise HTTPException(
                        status_code=400,
                        detail="SCRA credentials incomplete. Please update your credentials in settings."
                    )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve user credentials. Please try again."
                )
        
        # Create session ID for this verification
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Initialize Puppeteer agent with user_id for real-time updates
        agent = PuppeteerSCRAAgent(username, password, user_id)
        agent.session_id = session_id
        
        # Perform multi-record verification using fixed-width content directly
        result = await agent.verify_multiple_records_fixed_width(data.fixed_width_content)
        
        # Screenshots and PDF data are now included in the result
        if result.get('success'):
            automation_result = result.get('automationResult', {})
            
            # Mark that files are included in response
            automation_result['files_included'] = True
            automation_result['delivery_method'] = 'direct_response'
        
        # Save to Supabase with user_id
        verification_data = {
            'sessionId': session_id,
            'userId': user_id,
            'formData': {
                'type': 'multi_record',
                'record_count': record_count,
                'fixed_width_preview': data.fixed_width_content[:500] + '...' if len(data.fixed_width_content) > 500 else data.fixed_width_content
            },
            'result': result,
            'status': 'completed' if result.get('success') else 'failed',
            'timestamp': datetime.now().isoformat()
        }
        
        # Save verification to database for history
        try:
            await supabase_service.save_verification(verification_data)
        except Exception:
            # Continue anyway - frontend might also save
            pass
        
        # Restructure result for frontend compatibility
        if result.get('success'):
            # Move automationResult to the top level for easy access
            automation_result = result.get('automationResult', {})
            automation_result['sessionId'] = session_id
            
            # Ensure proper data structure for frontend
            result['data'] = {
                'automationResult': automation_result,
                'processingResult': result.get('processingResult', {}),
                'multiRecordRequest': result.get('multiRecordRequest', {})
            }
            
            # Keep debug files for now - they'll be cleaned up via separate endpoint or timeout
            agent.keep_debug_files()
        else:
            # Keep debug files for failed verifications
            if 'agent' in locals():
                agent.keep_debug_files()
        
        return result
        
    except Exception as e:
        
        error_result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        # Still save failed attempts to Supabase for history tracking
        try:
            error_verification_data = {
                'sessionId': session_id if 'session_id' in locals() else datetime.now().strftime("%Y%m%d_%H%M%S"),
                'userId': user_id if 'user_id' in locals() else None,
                'formData': {
                    'type': 'multi_record',
                    'fixed_width_length': len(data.fixed_width_content) if 'data' in locals() else 0
                },
                'result': error_result,
                'status': 'failed',
                'timestamp': datetime.now().isoformat()
            }
            
            if error_verification_data['userId']:
                await supabase_service.save_verification(error_verification_data)
                
        except Exception as save_error:
            pass
        
        return error_result


@app.post("/verification/{session_id}/uploaded")
async def mark_verification_uploaded(session_id: str):
    """Mark a verification as successfully uploaded to Supabase, allowing debug cleanup"""
    try:
        from pathlib import Path
        import os
        
        # Only handle debug files in development mode
        if os.getenv('NODE_ENV', '').lower() != 'development':
            return {"success": True, "message": "Production mode: No debug files to clean up"}
        
        debug_dir = Path("dbg_imgs") / session_id
        if debug_dir.exists():
            import shutil
            shutil.rmtree(debug_dir)
            return {"success": True, "message": f"Debug files cleaned up for session {session_id}"}
        else:
            return {"success": False, "message": f"No debug files found for session {session_id}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/verification/{session_id}/debug-status")
async def get_debug_status(session_id: str, authorization: Optional[str] = Header(None)):
    """Get the status of debug files and real-time screenshots for a verification session"""
    try:
        from pathlib import Path
        import os
        
        # Get real-time screenshots from Supabase (works in both dev and production)
        user_id = None
        if authorization and authorization.startswith('Bearer '):
            # Extract user_id if available
            pass
            
        supabase_screenshots = await supabase_service.get_session_screenshots(session_id, user_id)
        supabase_count = len(supabase_screenshots)
        
        # Also check local debug files in development mode
        local_screenshots = 0
        local_pdfs = 0
        debug_path = None
        
        if os.getenv('NODE_ENV', '').lower() == 'development':
            debug_dir = Path("dbg_imgs") / session_id
            if debug_dir.exists():
                local_screenshots = len(list((debug_dir / 'screenshots').glob('*.png')))
                local_pdfs = len(list((debug_dir / 'pdfs').glob('*.pdf')))
                debug_path = str(debug_dir)
        
        return {
            "success": True,
            "session_id": session_id,
            "supabase_screenshots": supabase_count,
            "local_screenshots": local_screenshots,
            "local_pdfs": local_pdfs,
            "debug_path": debug_path,
            "latest_screenshots": supabase_screenshots[-5:] if supabase_screenshots else [],  # Last 5 for quick preview
            "message": f"Found {supabase_count} real-time screenshots in Supabase" + 
                      (f" and {local_screenshots} local debug files" if local_screenshots else "")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/pdf/{session_id}")
async def get_verification_pdf(session_id: str):
    """PDF endpoint - files are now sent directly to frontend"""
    raise HTTPException(
        status_code=410, 
        detail="PDF files are now sent directly to frontend and uploaded to Supabase Storage by the client."
    )


@app.get("/screenshots/{session_id}")
async def get_session_screenshots(session_id: str, authorization: Optional[str] = Header(None)):
    """Get all screenshots for a verification session"""
    try:
        # Extract user ID from authorization header if available
        user_id = None
        if authorization and authorization.startswith('Bearer '):
            # JWT token validation would be implemented here in production
            pass
        
        screenshots = await supabase_service.get_session_screenshots(session_id, user_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "screenshot_count": len(screenshots),
            "screenshots": screenshots
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve screenshots: {str(e)}")


@app.get("/screenshots/user/{user_id}/latest")
async def get_user_latest_screenshots(user_id: str, limit: int = 10, authorization: Optional[str] = Header(None)):
    """Get latest screenshots for a user across all sessions"""
    try:
        # Validate authorization for user data access
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="Authorization required")
        
        screenshots = await supabase_service.get_latest_screenshots(user_id, limit)
        
        return {
            "success": True,
            "user_id": user_id,
            "screenshot_count": len(screenshots),
            "screenshots": screenshots
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user screenshots: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
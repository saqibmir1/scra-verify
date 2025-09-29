"""
Supabase client configuration for the SCRA verification backend
"""

import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from datetime import datetime
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

class SupabaseService:
    def __init__(self):
        # Environment variables for Supabase
        self.url = os.getenv("SUPABASE_URL")
        # Accept both SUPABASE_SERVICE_KEY and SUPABASE_SERVICE_ROLE_KEY for convenience
        self.service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.bucket_name = "verification-files"
        
        if not self.url or not self.service_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set"
            )
        
        # Create client with service role key (full access)
        self.client: Client = create_client(self.url, self.service_key)
        self._url = self.url
        
        # Ensure required storage bucket exists
        self._ensure_storage_bucket()
        self.bucket_ready = self.check_bucket_exists()
        
    def _ensure_storage_bucket(self):
        """Ensure the storage bucket exists; try to create it if missing and validate afterwards."""
        try:
            # Quick existence check
            if self.check_bucket_exists():
                print(f"✅ Storage bucket '{self.bucket_name}' is accessible and ready")
                return

            print(f"⚠️ Storage bucket '{self.bucket_name}' not found. Attempting to create...")
            try:
                # Prefer direct HTTP call to avoid SDK silent failures
                create_url = f"{self.url}/storage/v1/bucket"
                headers = {
                    "apikey": self.service_key,
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "name": self.bucket_name,
                    "public": False
                }
                resp = httpx.post(create_url, headers=headers, json=payload, timeout=15.0)
                if resp.status_code not in (200, 201):
                    # Fallback to SDK if direct call didn't succeed
                    try:
                        self.client.storage.create_bucket(self.bucket_name, {
                            "public": False,
                            "allowedMimeTypes": ["image/png", "image/jpeg", "application/pdf"],
                            "fileSizeLimit": 10485760
                        })
                    except Exception:
                        pass
                # Validate creation
                if self.check_bucket_exists():
                    print(f"✅ Created storage bucket '{self.bucket_name}' successfully")
                else:
                    print(f"❌ Bucket '{self.bucket_name}' still not accessible after creation attempt")
            except Exception as create_error:
                print(f"ℹ️ Could not create bucket '{self.bucket_name}' (may already exist or insufficient permissions): {create_error}")
        except Exception as e:
            print(f"⚠️ Storage bucket verification failed: {e}")
            print(f"📝 Please ensure the '{self.bucket_name}' bucket exists in your Supabase Storage")

    def check_bucket_exists(self) -> bool:
        """Return True if the storage bucket exists and is accessible."""
        try:
            # Use Storage REST API to avoid SDK silent successes
            url = f"{self.url}/storage/v1/bucket/{self.bucket_name}"
            headers = {
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}"
            }
            resp = httpx.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                return True
            if resp.status_code == 404:
                return False
            # Unexpected response - treat as missing
            return False
        except Exception:
            return False
    
    def get_client(self) -> Client:
        """Get the Supabase client instance"""
        return self.client
    
    # User Management
    async def create_user(self, email: str, password: str) -> Dict[str, Any]:
        """Create a new user"""
        try:
            response = self.client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True
            })
            return {"success": True, "user": response.user}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            response = self.client.auth.admin.get_user_by_id(user_id)
            return response.user if response else None
        except Exception as e:
            return None
    
    # User Settings
    async def save_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Save user settings to user_settings table"""
        try:
            # Upsert user settings
            response = self.client.table("user_settings").upsert({
                "user_id": user_id,
                "scra_username": settings.get("scraUsername"),
                "scra_password": settings.get("scraPassword"),
                "updated_at": datetime.now().isoformat()
            }).execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    async def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user settings"""
        try:
            response = self.client.table("user_settings").select("*").eq("user_id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            return None
    
    # Verification History
    async def save_verification(self, verification_data: Dict[str, Any]) -> bool:
        """Save verification record to database"""
        try:
            # Prepare data for insertion
            insert_data = {
                "session_id": verification_data["sessionId"],
                "form_data": verification_data["formData"],
                "result": verification_data["result"],
                "status": verification_data.get("status", "completed"),
                "timestamp": verification_data.get("timestamp", datetime.now().isoformat()),
                "created_at": datetime.now().isoformat()
            }
            
            # Only add user_id if it exists (for authenticated users)
            if verification_data.get("userId"):
                insert_data["user_id"] = verification_data["userId"]
            
            response = self.client.table("verifications").insert(insert_data).execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    async def get_user_verifications(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get verification history for a user"""
        try:
            response = self.client.table("verifications")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .offset(offset)\
                .execute()
            
            return response.data or []
        except Exception as e:
            return []
    
    async def delete_verification(self, session_id: str, user_id: str) -> bool:
        """Delete a verification record"""
        try:
            response = self.client.table("verifications")\
                .delete()\
                .eq("session_id", session_id)\
                .eq("user_id", user_id)\
                .execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    # Real-time Session Management
    async def create_verification_session(self, session_id: str, user_id: str, form_data: dict) -> bool:
        """Create a new verification session for real-time tracking"""
        try:
            response = self.client.table("verification_sessions").insert({
                "session_id": session_id,
                "user_id": user_id,
                "status": "in_progress",
                "progress": 0,
                "form_data": form_data,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    async def update_session_progress(self, session_id: str, current_step: str, progress: int) -> bool:
        """Update session progress and current step"""
        try:
            response = self.client.table("verification_sessions").update({
                "current_step": current_step,
                "progress": progress,
                "updated_at": datetime.now().isoformat()
            }).eq("session_id", session_id).execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    async def complete_session(self, session_id: str, status: str, error_message: str = None) -> bool:
        """Mark session as completed or failed"""
        try:
            update_data = {
                "status": status,
                "progress": 100 if status == "completed" else 0,
                "updated_at": datetime.now().isoformat()
            }
            if error_message:
                update_data["error_message"] = error_message
                
            response = self.client.table("verification_sessions").update(update_data).eq("session_id", session_id).execute()
            
            return len(response.data) > 0
        except Exception as e:
            return False
    
    def test_storage_connection(self) -> bool:
        """Test that storage is reachable and the required bucket exists."""
        exists = self.check_bucket_exists()
        if exists:
            print(f"🔍 Storage connection test passed for bucket '{self.bucket_name}'")
        else:
            print(f"❌ Storage connection test failed or bucket '{self.bucket_name}' missing")
        return exists

    def check_required_tables(self) -> Dict[str, bool]:
        """Check presence of required tables by attempting a minimal select."""
        required = [
            "verifications",
            "verification_screenshots",
            "verification_sessions",
            "user_settings",
        ]
        results: Dict[str, bool] = {}
        for table in required:
            try:
                # select minimal column name; PostgREST tolerates '*' but we'll use '*'
                self.client.table(table).select("*").limit(1).execute()
                results[table] = True
            except Exception:
                results[table] = False
        return results

    async def upload_screenshot_realtime(self, session_id: str, step: str, filename: str, description: str, screenshot_data: bytes, user_id: Optional[str] = None, max_retries: int = 3) -> bool:
        """Upload screenshot to storage and track in database with enhanced metadata and retry logic"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                # Upload to Supabase Storage
                storage_path = f"sessions/{session_id}/screenshots/{filename}"
                
                # Add retry delay for subsequent attempts
                if attempt > 0:
                    await asyncio.sleep(attempt * 0.5)  # Progressive backoff: 0.5s, 1s, 1.5s
                
                response = self.client.storage.from_("verification-files").upload(
                    storage_path, 
                    screenshot_data, 
                    {
                        "content-type": "image/png",
                        "upsert": "true"
                    }
                )
                
                if response:
                    # Record in screenshots table (using existing schema)
                    screenshot_record = {
                        "session_id": session_id,
                        "step": step,
                        "filename": filename,
                        "description": description,
                        "storage_path": storage_path,
                        "uploaded_at": datetime.now().isoformat()
                    }
                    
                    # Note: user_id and file_size columns may need to be added to the database schema
                    # For now, we'll store without them to maintain compatibility
                    
                    # Try database insert with retry
                    try:
                        self.client.table("verification_screenshots").insert(screenshot_record).execute()
                        print(f"📤 Screenshot uploaded successfully: {filename} (attempt {attempt + 1})")
                        return True
                    except Exception as db_e:
                        print(f"⚠️ Database insert failed for {filename} (attempt {attempt + 1}): {db_e}")
                        if attempt == max_retries - 1:  # Last attempt
                            # At least the file was uploaded to storage
                            print(f"📤 Screenshot uploaded to storage but database record failed: {filename}")
                            return True  # Consider partial success since file is in storage
                        continue
                else:
                    print(f"⚠️ Storage upload failed for {filename} (attempt {attempt + 1})")
                    
            except Exception as e:
                print(f"❌ Screenshot upload error for {filename} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:  # Last attempt
                    print(f"💥 Final upload failure for {filename} after {max_retries} attempts")
                    return False
                
        return False

    async def upload_pdf_realtime(self, session_id: str, filename: str, pdf_data: bytes, user_id: str = None) -> bool:
        """Upload PDF to storage and get public URL"""
        try:
            # Upload to Supabase Storage - use consistent path structure
            if user_id:
                storage_path = f"users/{user_id}/verifications/{session_id}/pdfs/{filename}"
            else:
                storage_path = f"sessions/{session_id}/pdfs/{filename}"
            
            response = self.client.storage.from_("verification-files").upload(
                storage_path, 
                pdf_data, 
                {
                    "content-type": "application/pdf",
                    "upsert": "true"
                }
            )
            
            if response:
                return True
            
            return False
        except Exception as e:
            return False

    # File Storage
    async def upload_file(self, bucket: str, file_path: str, file_data: bytes, content_type: str = "application/octet-stream") -> Optional[str]:
        """Upload file to Supabase Storage"""
        try:
            response = self.client.storage.from_(bucket).upload(file_path, file_data, {
                "content-type": content_type,
                "upsert": "true"
            })
            
            if response:
                # Get public URL
                public_url = self.client.storage.from_(bucket).get_public_url(file_path)
                return public_url
            return None
        except Exception as e:
            return None
    
    async def get_file_url(self, bucket: str, file_path: str) -> Optional[str]:
        """Get public URL for a file"""
        try:
            return self.client.storage.from_(bucket).get_public_url(file_path)
        except Exception as e:
            return None
    
    async def delete_file(self, bucket: str, file_path: str) -> bool:
        """Delete file from storage"""
        try:
            response = self.client.storage.from_(bucket).remove([file_path])
            return len(response) > 0
        except Exception as e:
            return False

    async def get_session_screenshots(self, session_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all screenshots for a session, ordered chronologically"""
        try:
            # Note: user_id filtering disabled for now due to schema constraints
            query = self.client.table("verification_screenshots").select("*").eq("session_id", session_id)
            
            response = query.order("uploaded_at").execute()
            
            screenshots = []
            for row in response.data:
                # Generate signed URL for frontend access
                signed_url = self.client.storage.from_("verification-files").create_signed_url(
                    row["storage_path"], 
                    expires_in=3600  # 1 hour
                )
                
                screenshots.append({
                    "id": row["id"],
                    "step": row["step"],
                    "filename": row["filename"],
                    "description": row["description"],
                    "uploaded_at": row["uploaded_at"],
                    "url": signed_url.get("signedURL") if signed_url else None
                })
            
            return screenshots
        except Exception as e:
            print(f"Error getting session screenshots: {e}")
            return []

    async def get_latest_screenshots(self, user_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest screenshots (user filtering disabled due to schema constraints)"""
        try:
            # Note: user_id filtering disabled for now due to schema constraints
            response = self.client.table("verification_screenshots")\
                .select("*")\
                .order("uploaded_at", desc=True)\
                .limit(limit)\
                .execute()
            
            screenshots = []
            for row in response.data:
                # Generate signed URL for frontend access
                signed_url = self.client.storage.from_("verification-files").create_signed_url(
                    row["storage_path"], 
                    expires_in=3600  # 1 hour
                )
                
                screenshots.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "step": row["step"],
                    "filename": row["filename"],
                    "description": row["description"],
                    "uploaded_at": row["uploaded_at"],
                    "url": signed_url.get("signedURL") if signed_url else None
                })
            
            return screenshots
        except Exception as e:
            print(f"Error getting latest screenshots: {e}")
            return []

# Global instance
supabase_service = None

def get_supabase_service() -> SupabaseService:
    """Get or create the global Supabase service instance"""
    global supabase_service
    if supabase_service is None:
        supabase_service = SupabaseService()
    return supabase_service
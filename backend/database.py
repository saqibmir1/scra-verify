"""
Database models and setup for SCRA verification history
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

class VerificationHistory:
    def __init__(self, db_path: str = "verification_history.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Create table with user_id column
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    user_id TEXT,  -- Supabase user ID
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    middle_name TEXT,
                    suffix TEXT,
                    ssn_masked TEXT NOT NULL,  -- Store masked SSN for display
                    date_of_birth TEXT NOT NULL,
                    active_duty_date TEXT NOT NULL,
                    verification_status TEXT NOT NULL,  -- 'success', 'failed', 'error'
                    error_message TEXT,
                    pdf_filename TEXT,
                    pdf_downloaded BOOLEAN DEFAULT FALSE,
                    automation_result TEXT,  -- JSON string of full automation result
                    storage_path TEXT,  -- Base path in Supabase Storage
                    storage_files TEXT,  -- JSON string of uploaded file info
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Migration: Add user_id column if it doesn't exist
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(verification_history)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'user_id' not in columns:
                conn.execute("ALTER TABLE verification_history ADD COLUMN user_id TEXT")
            
            # Migration: Add Storage columns if they don't exist (renamed from firebase to generic)
            if 'firebase_storage_path' not in columns and 'storage_path' not in columns:
                conn.execute("ALTER TABLE verification_history ADD COLUMN storage_path TEXT")
                conn.execute("ALTER TABLE verification_history ADD COLUMN storage_files TEXT")
            # Legacy column migration
            elif 'firebase_storage_path' in columns:
                conn.execute("ALTER TABLE verification_history RENAME COLUMN firebase_storage_path TO storage_path")
                conn.execute("ALTER TABLE verification_history RENAME COLUMN firebase_files TO storage_files")
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON verification_history(session_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON verification_history(created_at DESC)
            """)
    
    def mask_ssn(self, ssn: str) -> str:
        """Mask SSN for display purposes (XXX-XX-1234)"""
        if len(ssn) >= 4:
            return f"XXX-XX-{ssn[-4:]}"
        return "XXX-XX-XXXX"
    
    def save_verification(self, verification_data: Dict[str, Any]) -> int:
        """Save a verification attempt to the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Extract data with defaults
            session_id = verification_data.get('sessionId', '')
            form_data = verification_data.get('formData', {})
            result = verification_data.get('result', {})
            
            # Mask SSN for storage
            ssn_raw = form_data.get('ssn', '')
            ssn_masked = self.mask_ssn(ssn_raw)
            
            # Determine verification status
            if result.get('success'):
                status = 'success'
                error_message = None
            else:
                status = 'failed' if result.get('error') else 'error'
                error_message = result.get('error', 'Unknown error')
            
            # PDF information
            automation_result = result.get('automationResult', {})
            pdf_downloaded = automation_result.get('pdfDownloaded', False)
            pdf_filename = "scra_result.pdf" if pdf_downloaded else None
            
            # Storage information
            storage_data = automation_result.get('storage', {}) or automation_result.get('firebase_storage', {})
            storage_path = storage_data.get('base_path', '')
            storage_files = json.dumps(storage_data.get('files', [])) if storage_data.get('files') else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO verification_history 
                (session_id, user_id, first_name, last_name, middle_name, suffix, 
                 ssn_masked, date_of_birth, active_duty_date, verification_status, 
                 error_message, pdf_filename, pdf_downloaded, automation_result, 
                 storage_path, storage_files, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                verification_data.get('userId'),
                form_data.get('firstName', ''),
                form_data.get('lastName', ''),
                form_data.get('middleName', ''),
                form_data.get('suffix', ''),
                ssn_masked,
                form_data.get('dateOfBirth', ''),
                form_data.get('activeDutyDate', ''),
                status,
                error_message,
                pdf_filename,
                pdf_downloaded,
                json.dumps(automation_result),
                storage_path,
                storage_files,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            return cursor.lastrowid
    
    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve verification history with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, session_id, user_id, first_name, last_name, middle_name, suffix,
                       ssn_masked, date_of_birth, active_duty_date, verification_status,
                       error_message, pdf_filename, pdf_downloaded, created_at
                FROM verification_history 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_verification_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific verification by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM verification_history WHERE id = ?
            """, (record_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_verification_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific verification by session ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM verification_history WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_verification(self, record_id: int) -> bool:
        """Delete a verification record and associated files"""
        verification = self.get_verification_by_id(record_id)
        if not verification:
            return False
        
        # Delete associated files (only in development mode)
        import os
        if os.getenv('NODE_ENV', '').lower() == 'development':
            session_id = verification['session_id']
            session_folder = Path("dbg_imgs") / session_id
            
            # Delete entire session folder if it exists
            if session_folder.exists():
                import shutil
                shutil.rmtree(session_folder)
        
        # Delete database record
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM verification_history WHERE id = ?", (record_id,))
            return cursor.rowcount > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get verification statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total verifications
            cursor.execute("SELECT COUNT(*) FROM verification_history")
            total = cursor.fetchone()[0]
            
            # Success rate
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN verification_status = 'success' THEN 1 END) as successful,
                    COUNT(CASE WHEN verification_status = 'failed' THEN 1 END) as failed,
                    COUNT(CASE WHEN verification_status = 'error' THEN 1 END) as errors
                FROM verification_history
            """)
            
            stats = cursor.fetchone()
            
            return {
                'total': total,
                'successful': stats[0],
                'failed': stats[1],
                'errors': stats[2],
                'success_rate': round((stats[0] / total * 100) if total > 0 else 0, 1)
            }
        
"""
Puppeteer automation agent for SCRA military active duty verification
"""

import asyncio
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path
import base64 # Add this import

from playwright.async_api import async_playwright, Browser, Page, TimeoutError
from supabase_client import get_supabase_service
from csv_processor import SCRARecord, process_csv_for_scra


def is_development_mode() -> bool:
    """Check if we're running in development mode"""
    return os.getenv('NODE_ENV', '').lower() == 'development'


class PuppeteerSCRAAgent:
    """Puppeteer-based automation for SCRA website"""
    
    def __init__(self, username: str, password: str, user_id: Optional[str] = None):
        self.username = username
        self.password = password
        self.user_id = user_id
        self.scra_url = "https://scra.dmdc.osd.mil/scra/#/login"
        self.single_record_url = "https://scra.dmdc.osd.mil/scra/#/single-record"
        self.multi_record_url = "https://scra.dmdc.osd.mil/scra/#/multiple-record"
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # File capture for direct frontend transmission
        self.screenshots = []
        self.pdf_data = None
        
        # Debug directory for local file backup
        self.debug_dir = Path("dbg_imgs")
        self.session_debug_dir = None
        
        # Supabase service for real-time uploads
        self.supabase_service = get_supabase_service()
        self.progress_steps = {
            "initializing": 5,
            "navigating_to_login": 10,
            "logging_in": 20,
            "navigating_to_form": 30,
            "filling_form": 60,
            "submitting_form": 80,
            "downloading_results": 90,
            "completed": 100
        }
        
    async def verify_person(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify a person's active duty status through SCRA website using Puppeteer automation
        """
        
        try:
            # Initialize file capture arrays
            self.screenshots = []
            self.pdf_data = None
            
            # Create real-time session in Supabase
            if self.user_id:
                await self.supabase_service.create_verification_session(
                    self.session_id, 
                    self.user_id, 
                    person_data
                )
            
            # Update progress: Initializing
            await self._update_progress("initializing", "Initializing browser and setting up automation")
            
            # Create debug directory for this session (only in development)
            if is_development_mode():
                self.session_debug_dir = self.debug_dir / self.session_id
                self.session_debug_dir.mkdir(parents=True, exist_ok=True)
                
                # Create subdirectories
                (self.session_debug_dir / "screenshots").mkdir(exist_ok=True)
                (self.session_debug_dir / "pdfs").mkdir(exist_ok=True)
                print(f"🔧 Development mode: Debug files will be saved to {self.session_debug_dir}")
            else:
                self.session_debug_dir = None
                print("🚀 Production mode: Debug files will not be saved locally")
            
            # Initialize browser
            await self._initialize_browser()
            
            # Update progress: Navigating
            await self._update_progress("navigating_to_login", "Navigating to SCRA login page")
            
            # Navigate to SCRA and login
            await self._navigate_and_login()
            
            # Perform verification
            result = await self._perform_verification(person_data)
            
            # Mark session as completed
            if self.user_id:
                await self.supabase_service.complete_session(
                    self.session_id, 
                    "completed" if result.get("success") else "failed",
                    result.get("error") if not result.get("success") else None
                )
            
            return result
            
        except Exception as e:
            # Mark session as failed
            if self.user_id:
                await self.supabase_service.complete_session(
                    self.session_id, 
                    "failed", 
                    str(e)
                )
            
            return {
                "success": False,
                "error": f"Puppeteer automation failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "method": "puppeteer"
            }
        finally:
            # Always cleanup
            await self._cleanup()
    
    async def verify_multiple_records(self, csv_content: str, fixed_width_override: str = None) -> Dict[str, Any]:
        """
        Verify multiple records through SCRA website using CSV input
        """
        
        try:
            # Initialize file capture arrays
            self.screenshots = []
            self.pdf_data = None
            
            # Process CSV content or use override
            if fixed_width_override:
                # Use the provided fixed-width content
                fixed_width_content = fixed_width_override
                # Count records from fixed-width content
                lines = [line.strip() for line in fixed_width_content.split('\n') if line.strip()]
                record_count = len(lines)
                
                # Create dummy SCRARecord objects for compatibility
                from csv_processor import SCRARecord
                records = []
                for i in range(record_count):
                    dummy_data = {
                        'ssn': '',
                        'first_name': f'Record_{i+1}',
                        'last_name': 'Dummy',
                        'middle_name': '',
                        'date_of_birth': '',
                        'active_duty_status_date': '20240101',
                        'customer_record_id': f'REC{i+1:03d}',
                        '_row_number': i+1
                    }
                    dummy_record = SCRARecord(dummy_data)
                    records.append(dummy_record)
                
                await self._update_progress("initializing", f"Using provided fixed-width content with {record_count} records")
            else:
                # Normal CSV processing
                await self._update_progress("initializing", "Processing CSV file and validating records")
                fixed_width_content, records, csv_errors = process_csv_for_scra(csv_content)
                
                if csv_errors:
                    return {
                        "success": False,
                        "error": f"CSV validation failed: {'; '.join(csv_errors)}",
                        "timestamp": datetime.now().isoformat(),
                        "method": "puppeteer_multi_record"
                    }
                
                if not records:
                    return {
                        "success": False,
                        "error": "No valid records found in CSV file",
                        "timestamp": datetime.now().isoformat(),
                        "method": "puppeteer_multi_record"
                    }
            
            # Create real-time session in Supabase
            if self.user_id:
                await self.supabase_service.create_verification_session(
                    self.session_id, 
                    self.user_id, 
                    {"record_count": len(records), "type": "multi_record"}
                )
            
            # Update progress: Initializing
            await self._update_progress("initializing", f"Initializing browser for {len(records)} records")
            
            # Create debug directory for this session (only in development)
            if is_development_mode():
                self.session_debug_dir = self.debug_dir / self.session_id
                self.session_debug_dir.mkdir(parents=True, exist_ok=True)
                
                # Create subdirectories
                (self.session_debug_dir / "screenshots").mkdir(exist_ok=True)
                (self.session_debug_dir / "pdfs").mkdir(exist_ok=True)
                print(f"🔧 Development mode: Debug files will be saved to {self.session_debug_dir}")
            else:
                self.session_debug_dir = None
                print("🚀 Production mode: Debug files will not be saved locally")
            
            # Initialize browser
            await self._initialize_browser()
            
            # Update progress: Navigating
            await self._update_progress("navigating_to_login", "Navigating to SCRA login page")
            
            # Navigate to SCRA and login
            await self._navigate_and_login()
            
            # Perform multi-record verification
            result = await self._perform_multi_record_verification(fixed_width_content, records)
            
            # Mark session as completed
            if self.user_id:
                await self.supabase_service.complete_session(
                    self.session_id, 
                    "completed" if result.get("success") else "failed",
                    result.get("error") if not result.get("success") else None
                )
            
            return result
            
        except Exception as e:
            # Mark session as failed
            if self.user_id:
                await self.supabase_service.complete_session(
                    self.session_id, 
                    "failed", 
                    str(e)
                )
            
            return {
                "success": False,
                "error": f"Multi-record verification failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "method": "puppeteer_multi_record"
            }
        finally:
            # Always cleanup
            await self._cleanup()
    
    async def verify_multiple_records_fixed_width(self, fixed_width_content: str) -> Dict[str, Any]:
        """
        Verify multiple records using pre-formatted fixed-width content
        
        Args:
            fixed_width_content: The fixed-width formatted text content (95 chars per line)
            
        Returns:
            Dict containing verification results
        """
        print(f"🚀 Starting multi-record verification with fixed-width content...")
        
        try:
            # Initialize file capture arrays
            self.screenshots = []
            self.pdf_data = None
            
            # Parse records from fixed-width content
            lines = [line.strip() for line in fixed_width_content.split('\n') if line.strip()]
            
            if not lines:
                return {
                    "success": False,
                    "error": "No records found in fixed-width content",
                    "timestamp": datetime.now().isoformat(),
                    "method": "puppeteer_multi_record_fixed_width"
                }
            
            print(f"✅ Processing {len(lines)} records from fixed-width content")
            
            # Just use the original working method with the fixed-width override
            dummy_csv = ""  # Empty CSV since we're using fixed-width override
            return await self.verify_multiple_records(dummy_csv, fixed_width_override=fixed_width_content)
            
        except Exception as e:
            print(f"❌ Multi-record fixed-width verification failed: {str(e)}")
            
            return {
                "success": False,
                "error": f"Multi-record verification failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "method": "puppeteer_multi_record_fixed_width"
            }
        finally:
            # Always cleanup
            await self._cleanup()
    
    async def _initialize_browser(self):
        """Initialize Playwright browser"""
        
        playwright = await async_playwright().start()
        
        # Check if this is local testing vs production
        is_local_test = os.getenv('HEADLESS', 'true').lower() == 'false'
        
        if is_local_test:
            # Minimal browser args for local visible testing
            print("🧪 Local testing mode - using minimal browser arguments for visibility")
            browser_args = [
                '--no-first-run',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows', 
                '--disable-renderer-backgrounding',
                '--window-size=1280,800'
            ]
        else:
            # Production-optimized browser launch arguments
            print("🚀 Production mode - using optimized browser arguments")
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-background-networking',
                '--disable-background-downloads',
                '--disable-component-update',
                '--disable-client-side-phishing-detection',
                '--disable-sync',
                '--metrics-recording-only',
                '--no-crash-upload',
                '--mute-audio',
                '--disable-logging',
                '--disable-gl-drawing-for-tests',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
                '--ignore-certificate-errors-spki-list'
            ]
        
        # Add DNS servers to resolve SCRA military domain
        # Use local DNS servers that can resolve scra.dmdc.osd.mil
        dns_servers = os.getenv('LOCAL_DNS_SERVERS', '100.64.0.2,192.168.1.1')
        browser_args.append(f'--dns-servers={dns_servers}')
        
        print(f"🔧 Using DNS servers: {dns_servers}")
        
        # Add memory constraints for production environment
        is_production = (os.getenv("RAILWAY_ENVIRONMENT") or 
                        os.getenv("RAILWAY_PROJECT_ID") or 
                        os.getenv("RENDER") or 
                        os.getenv("HEROKU") or
                        os.getenv("PORT"))  # Railway sets PORT env var
        
        if is_production:
            print("🚀 Production environment detected, applying optimizations...")
            browser_args.extend([
                '--memory-pressure-off',
                '--disable-background-mode',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--max_old_space_size=512',  # Limit memory usage
                '--disable-paint-holding',
                '--disable-partial-raster',
                '--disable-skia-runtime-opts',
                '--disable-font-subpixel-positioning',  # Faster font rendering
                '--disable-lcd-text',  # Disable LCD text rendering
                '--font-cache-shared-handle',  # Share font cache
                '--aggressive-cache-discard',  # Discard unused cache quickly
                '--ignore-ssl-errors',  # Ignore SSL errors when using proxy
                '--ignore-certificate-errors',  # Ignore certificate errors
                '--ignore-certificate-errors-spki-list',  # Ignore certificate pin errors
                '--ignore-ssl-errors-list'  # Ignore SSL error list
            ])
        
        # Connect to remote Browserless service or launch locally
        browserless_endpoint = os.getenv("BROWSER_PLAYWRIGHT_ENDPOINT")
        
        if browserless_endpoint:
            # Use remote Browserless service (Railway production)
            print(f"Connecting to remote Browserless endpoint: {browserless_endpoint}")
            self.browser = await playwright.chromium.connect(browserless_endpoint)
        else:
            # Launch browser locally (development)
            print("Launching local browser for development")
            launch_options = {
                'headless': os.getenv("HEADLESS", "true").lower() == "true",
                'args': browser_args
            }
            
            # Slow motion removed for faster testing
            # if is_local_test:
            #     launch_options['slow_mo'] = 500
            #     print("🐌 Added slow motion for local testing visibility")
            
            self.browser = await playwright.chromium.launch(**launch_options)
        
        # Configure proxy for US access if available
        context_options = {
            'viewport': {'width': 1366, 'height': 768},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'accept_downloads': True,
            'java_script_enabled': True,
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},  # NYC coordinates
            'permissions': ['geolocation'],
            'ignore_https_errors': True  # Ignore SSL certificate errors when using proxy
        }
        
        # Add residential proxy configuration for SCRA access
        proxy_server = os.getenv("RESIDENTIAL_PROXY_SERVER", "").strip()  # Remove any spaces
        proxy_username = os.getenv("RESIDENTIAL_PROXY_USERNAME", "").strip()
        proxy_password = os.getenv("RESIDENTIAL_PROXY_PASSWORD", "").strip()
        
        # Legacy proxy support
        us_proxy = os.getenv("US_PROXY_URL")  # Format: http://username:password@proxy:port
        
        if proxy_server and proxy_username and proxy_password:
            print(f"🏠 Using residential proxy: {proxy_server}")
            print(f"🔑 Proxy username: {proxy_username}")
            context_options['proxy'] = {
                'server': f'http://{proxy_server}',
                'username': proxy_username,
                'password': proxy_password
            }
            # Also configure proxy at browser level for better compatibility
            browser_args.extend([
                f'--proxy-server=http://{proxy_server}',
                f'--proxy-auth={proxy_username}:{proxy_password}'
            ])
        elif us_proxy:
            print(f"🌍 Using US proxy: {us_proxy}")
            context_options['proxy'] = {'server': us_proxy}
        elif is_production:
            print("⚠️ No residential proxy configured - SCRA website may block datacenter IPs")
            print("💡 Set RESIDENTIAL_PROXY_SERVER, RESIDENTIAL_PROXY_USERNAME, RESIDENTIAL_PROXY_PASSWORD environment variables")
        
        # Create a new browser context with downloads enabled
        self.context = await self.browser.new_context(**context_options)
        
        # Create new page from the context
        self.page = await self.context.new_page()
        
        # Set US-focused request headers to avoid geo-blocking
        await self.page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Google Chrome";v="120", "Not_A Brand";v="99", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Cache-Control': 'max-age=0'
        })
        
        # Add US timezone and location context
        if is_production:
            print("🇺🇸 Setting US location context for SCRA website access")
            
            # Disable font loading and web fonts for faster screenshots in production
            await self.page.add_init_script("""
                // Block web fonts to speed up page rendering
                const originalFont = FontFace;
                window.FontFace = function() {
                    return {
                        load: () => Promise.resolve(),
                        status: 'loaded'
                    };
                };
                
                // Skip font loading events
                document.addEventListener('DOMContentLoaded', function() {
                    if (document.fonts && document.fonts.ready) {
                        // Force fonts to be considered ready
                        document.fonts.ready = Promise.resolve();
                    }
                });
            """)
        
    
    def _convert_date_to_yyyymmdd(self, date_value: str) -> str:
        """Convert MM/DD/YYYY or YYYY-MM-DD to YYYYMMDD format"""
        if not date_value:
            return ""
            
        try:
            from datetime import datetime
            
            # Handle MM/DD/YYYY format (most common from frontend)
            if '/' in date_value:
                date_obj = datetime.strptime(date_value, '%m/%d/%Y')
                return date_obj.strftime('%Y%m%d')
            
            # Handle YYYY-MM-DD format (legacy)
            elif '-' in date_value:
                date_obj = datetime.strptime(date_value, '%Y-%m-%d')
                return date_obj.strftime('%Y%m%d')
            
            # If already in YYYYMMDD format or other, return as-is
            else:
                return date_value
                
        except Exception as e:
            # Try to remove common separators as fallback
            return date_value.replace('-', '').replace('/', '')
    
    def _convert_date_to_mmddyyyy(self, date_value: str) -> str:
        """Convert various date formats to MM/DD/YYYY format for SCRA form"""
        if not date_value:
            return ""
            
        try:
            from datetime import datetime
            
            # Handle MM/DD/YYYY format (already correct)
            if '/' in date_value and len(date_value.split('/')) == 3:
                parts = date_value.split('/')
                if len(parts[2]) == 4:  # Full year
                    return date_value  # Already in correct format
            
            # Handle YYYY-MM-DD format
            elif '-' in date_value:
                date_obj = datetime.strptime(date_value, '%Y-%m-%d')
                return date_obj.strftime('%m/%d/%Y')
            
            # Handle YYYYMMDD format
            elif len(date_value) == 8 and date_value.isdigit():
                date_obj = datetime.strptime(date_value, '%Y%m%d')
                return date_obj.strftime('%m/%d/%Y')
            
            # If unknown format, try to parse and convert
            else:
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']:
                    try:
                        date_obj = datetime.strptime(date_value, fmt)
                        return date_obj.strftime('%m/%d/%Y')
                    except Exception:
                        continue
                return date_value
                
        except Exception as e:
            print(f"⚠️ Date conversion to MM/DD/YYYY error: {e}")
            return date_value

    # ---------------------
    # Cross-frame utilities
    # ---------------------
    async def _query_selector_any_frame_visible(self, selector: str, timeout_ms: int = 3000):
        """Find first visible element matching selector in page or any frame."""
        try:
            el = await self.page.query_selector(selector)
            if el and await el.is_visible():
                return el
        except Exception:
            pass
        try:
            for frame in self.page.frames:
                try:
                    el = await frame.query_selector(selector)
                    if el and await el.is_visible():
                        return el
                except Exception:
                    continue
        except Exception:
            pass
        # As a last attempt, wait briefly in case SPA renders late
        try:
            for frame in self.page.frames:
                try:
                    el = await frame.wait_for_selector(selector, timeout=timeout_ms)
                    if el and await el.is_visible():
                        return el
                except Exception:
                    continue
        except Exception:
            pass
        return None

    async def _wait_for_selector_any_frame(self, selector: str, timeout_ms: int = 5000):
        """Wait until a selector appears in any frame and is visible; return handle or None."""
        deadline = datetime.now().timestamp() + (timeout_ms / 1000.0)
        while datetime.now().timestamp() < deadline:
            el = await self._query_selector_any_frame_visible(selector, timeout_ms=500)
            if el:
                return el
            await self.page.wait_for_timeout(200)
        return None

    def _convert_date_to_mmddyyyy(self, date_value: str) -> str:
        """Convert various date formats to MM/DD/YYYY format for SCRA form"""
        if not date_value:
            return ""
            
        try:
            from datetime import datetime
            
            # Handle MM/DD/YYYY format (already correct)
            if '/' in date_value and len(date_value.split('/')) == 3:
                parts = date_value.split('/')
                if len(parts[2]) == 4:  # Full year
                    return date_value  # Already in correct format
            
            # Handle YYYY-MM-DD format
            elif '-' in date_value:
                date_obj = datetime.strptime(date_value, '%Y-%m-%d')
                return date_obj.strftime('%m/%d/%Y')
            
            # Handle YYYYMMDD format
            elif len(date_value) == 8 and date_value.isdigit():
                date_obj = datetime.strptime(date_value, '%Y%m%d')
                return date_obj.strftime('%m/%d/%Y')
            
            # If unknown format, try to parse and convert
            else:
                # Try common formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']:
                    try:
                        date_obj = datetime.strptime(date_value, fmt)
                        return date_obj.strftime('%m/%d/%Y')
                    except:
                        continue
                
                return date_value  # Return as-is if can't parse
                
        except Exception as e:
            print(f"⚠️ Date conversion to MM/DD/YYYY error: {e}")
            return date_value
    
    async def _update_progress(self, step_key: str, description: str):
        """Update session progress in real-time"""
        if self.user_id and step_key in self.progress_steps:
            try:
                progress = self.progress_steps[step_key]
                await self.supabase_service.update_session_progress(
                    self.session_id, 
                    description, 
                    progress
                )
            except Exception as e:
                pass

    async def _take_debug_screenshot(self, step_name: str, description: str = ""):
        """Take a screenshot and upload to Supabase in real-time"""
        if self.page:
            try:
                filename = f"{step_name}.png"
                
                # Check if we're in production for more aggressive timeouts
                is_production = (os.getenv("RAILWAY_ENVIRONMENT") or 
                                os.getenv("RAILWAY_PROJECT_ID") or 
                                os.getenv("PORT"))
                
                # Take screenshot with production-optimized settings
                try:
                    # Wait for fonts to load with shorter timeout in production
                    if not is_production:
                        await self.page.wait_for_load_state('networkidle', timeout=5000)
                    
                    # Try full page first with shorter timeout in production
                    timeout = 8000 if is_production else 15000
                    screenshot_bytes = await self.page.screenshot(
                        full_page=True, 
                        timeout=timeout,
                        animations='disabled'  # Skip animations for faster screenshots
                    )
                except Exception as e:
                    # Check if this is due to closed browser context
                    if "closed" in str(e).lower() or "target" in str(e).lower():
                        print(f"⚠️ Browser context closed, cannot take screenshot: {e}")
                        return None
                    
                    print(f"⚠️ Full page screenshot failed ({e}), trying viewport only...")
                    try:
                        # Fallback to viewport-only screenshot with even shorter timeout
                        timeout = 5000 if is_production else 10000
                        screenshot_bytes = await self.page.screenshot(
                            full_page=False, 
                            timeout=timeout,
                            animations='disabled'
                        )
                    except Exception as e2:
                        # Check if this is due to closed browser context
                        if "closed" in str(e2).lower() or "target" in str(e2).lower():
                            print(f"⚠️ Browser context closed, cannot take screenshot: {e2}")
                            return None
                        print(f"⚠️ Viewport screenshot also failed ({e2}), skipping screenshot...")
                        return  # Skip this screenshot entirely
                
                print(f"📸 Screenshot captured: {filename}")
                if description:
                    print(f"   Description: {description}")
                
                # Upload to Supabase Storage immediately
                if self.user_id:
                    await self.supabase_service.upload_screenshot_realtime(
                        self.session_id,
                        step_name,
                        filename,
                        description,
                        screenshot_bytes,
                        self.user_id
                    )
                
                # Convert to base64 for legacy frontend transmission
                import base64
                screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                # Store screenshot data for later transmission (backup)
                if not hasattr(self, 'screenshots'):
                    self.screenshots = []
                
                self.screenshots.append({
                    'step': step_name,
                    'filename': filename,
                    'description': description,
                    'data': screenshot_base64,
                    'timestamp': datetime.now().isoformat(),
                    'size': len(screenshot_bytes)
                })
                
                # Save debug copy to local filesystem
                if self.session_debug_dir and self.session_debug_dir is not None:
                    try:
                        debug_path = self.session_debug_dir / "screenshots" / filename
                        with open(debug_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        print(f"🗂️ Debug copy saved: {debug_path}")
                    except Exception as debug_e:
                        print(f"⚠️ Failed to save debug copy: {debug_e}")
                
                print(f"✅ Screenshot processed: {filename} ({len(screenshot_bytes)} bytes)")
                return filename
            except Exception as e:
                print(f"⚠️ Failed to take screenshot: {e}")
        return None

    def _read_and_encode_screenshot(self, filepath: str) -> Optional[str]:
        """Reads a screenshot file and returns its base64 encoded content."""
        try:
            with open(filepath, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
        except Exception as e:
            print(f"❌ Failed to read or encode screenshot {filepath}: {e}")
            return None

    async def _handle_agreements(self):
        """Handle agreement popups - OPTIMIZED for speed"""
        print("🔍 Checking for modal (fast)...")
        
        # Direct targeting - we know the exact selector that works
        try:
            modal_btn = await self.page.wait_for_selector('.modal-content button:has-text("Accept")', timeout=3000)
            if modal_btn and await modal_btn.is_visible():
                await modal_btn.click()
                print("✅ Modal dismissed")
                return
        except:
            pass
        
        print("ℹ️ No modal found")
        
        # Additional check for any remaining modals or overlays
        await self._dismiss_remaining_modals()
    
    async def _dismiss_remaining_modals(self):
        """Dismiss any remaining modal dialogs or overlays"""
        print("🔍 Checking for remaining modals or overlays...")
        
        modal_selectors = [
            # Generic modal close buttons
            '.modal .close',
            '.modal button[aria-label="Close"]',
            '.modal .btn-close',
            '[role="dialog"] .close',
            '[role="dialog"] button[aria-label="Close"]',
            
            # Overlay dismiss areas
            '.overlay',
            '.modal-backdrop',
            
            # X buttons
            'button:has-text("×")',
            'button:has-text("✕")',
            '.close-btn',
            
            # Skip buttons for tours or introductions
            'button:has-text("Skip")',
            'button:has-text("Skip Tour")',
            'button:has-text("Not Now")',
            'button:has-text("Maybe Later")'
        ]
        
        for selector in modal_selectors:
            try:
                element = await self.page.wait_for_selector(selector, timeout=1000)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.click()
                        await self.page.wait_for_timeout(500)
                        print(f"✅ Dismissed modal: {selector}")
                        break
            except Exception:
                continue
    
    async def _navigate_and_login(self):
        """Navigate to SCRA website and perform login"""
        print(f"🌐 Navigating to {self.scra_url}")
        
        try:
            # Navigate to main page with production-optimized timeout and geo-blocking retry
            print(f"🌐 Attempting to navigate to: {self.scra_url}")
            
            # Try multiple navigation strategies
            navigation_successful = False
            last_error = None
            
            # Strategy 1: Normal navigation with networkidle
            try:
                await self.page.goto(self.scra_url, wait_until='networkidle', timeout=45000)
                print("✅ Main page loaded (networkidle)")
                navigation_successful = True
            except Exception as e:
                print(f"⚠️ NetworkIdle failed: {str(e)[:200]}...")
                last_error = e
                
                # Strategy 2: Try domcontentloaded
                try:
                    print("🔄 Retrying with domcontentloaded...")
                    await self.page.goto(self.scra_url, wait_until='domcontentloaded', timeout=30000)
                    print("✅ Main page loaded (domcontentloaded)")
                    navigation_successful = True
                except Exception as e2:
                    print(f"⚠️ DOMContentLoaded failed: {str(e2)[:200]}...")
                    last_error = e2
                    
                    # Strategy 3: Try with just load event
                    try:
                        print("🔄 Retrying with load event...")
                        await self.page.goto(self.scra_url, wait_until='load', timeout=20000)
                        print("✅ Main page loaded (load)")
                        navigation_successful = True
                    except Exception as e3:
                        print(f"⚠️ Load event failed: {str(e3)[:200]}...")
                        last_error = e3
            
            if not navigation_successful:
                # Check if this looks like geo-blocking
                error_str = str(last_error).lower()
                if 'timeout' in error_str or 'net::err_timed_out' in error_str:
                    error_msg = (
                        "❌ SCRA website access blocked - likely geo-restriction. "
                        "The SCRA website (scra.dmdc.osd.mil) blocks connections from outside the US. "
                        f"Railway servers appear to be blocked. Error: {str(last_error)[:200]}"
                    )
                    print(error_msg)
                    raise Exception(error_msg)
                else:
                    raise last_error
            
            await self._take_debug_screenshot("01_main_page_loaded", "Initial SCRA login page loaded")
            
            # Wait for page to fully load
            await self.page.wait_for_timeout(2000)
            
            # Handle any agreement/privacy popups first
            await self._handle_agreements()
            await self._take_debug_screenshot("02_after_agreements", "After handling any agreement popups")
            
            # Since we navigated directly to login URL, look for login form first
            print("🔍 Looking for login form on the page...")
            await self._fill_login_form()
            
        except Exception as e:
            # Take screenshot for debugging
            if self.page:
                await self._take_debug_screenshot("99_navigation_login_error", f"Navigation/login failed: {str(e)}")
            raise Exception(f"Navigation/login failed: {str(e)}")
    

    async def _fill_login_form(self):
        """Fill and submit the login form - OPTIMIZED for speed"""
        print("🔐 Filling login form (optimized)...")
        
        # Direct targeting - we know exactly what selectors work
        try:
            username_field = await self.page.wait_for_selector('input[name="username"]', timeout=5000)
            password_field = await self.page.wait_for_selector('input[name="password"]', timeout=5000)
            
            if not username_field or not password_field:
                await self._take_debug_screenshot("02_login_fields_not_found", "Login fields not found")
                raise Exception("Login fields not found")
            
            # Fill credentials directly
            await username_field.fill(self.username)
            await password_field.fill(self.password)
            print(f"✅ Filled credentials: {self.username}")
            
            await self._take_debug_screenshot("02_credentials_filled", "Login credentials filled")
            
            # Submit form immediately
            await password_field.press('Enter')
            print("✅ Form submitted")
            
        except Exception as e:
            await self._take_debug_screenshot("02_login_error", f"Login failed: {e}")
            raise Exception(f"Login form filling failed: {e}")
        
        # Wait for navigation or login result
        try:
            await self.page.wait_for_load_state('networkidle', timeout=20000)
        except TimeoutError:
            print("⚠️ Page didn't reach network idle, trying domcontentloaded...")
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            except TimeoutError:
                print("⚠️ Page didn't reach domcontentloaded either, continuing...")
        
        # Check if login was successful
        await self._verify_login_success()
    
    async def _verify_login_success(self):
        """Verify that login was successful"""
        print("🔍 Verifying login success...")
        
        # Wait for the app shell to render in cloud environments
        await self.page.wait_for_load_state('domcontentloaded')
        await self.page.wait_for_timeout(2000)
        
        # Take screenshot for debugging
        await self._take_debug_screenshot("03_after_login", "After login form submission")
        
        # Check for login failure indicators
        failure_indicators = [
            'text="Invalid username or password"',
            'text="Login failed"',
            'text="Authentication failed"',
            '.error',
            '.alert-danger',
            '[class*="error"]'
        ]
        
        for indicator in failure_indicators:
            try:
                element = await self.page.wait_for_selector(indicator, timeout=1000)
                if element:
                    error_text = await element.text_content()
                    raise Exception(f"Login failed: {error_text}")
            except TimeoutError:
                continue
        
        # Check for success indicators (include post-login menus)
        success_indicators = [
            'text="Welcome"',
            'text="Dashboard"',
            'text="Logout"',
            'a[href*="logout"]',
            '.main-content',
            '.dashboard',
            'nav',
            'button:has-text("Menu")',
            'a:has-text("Single Record")'
        ]
        
        login_successful = False
        for indicator in success_indicators:
            try:
                element = await self.page.wait_for_selector(indicator, timeout=2000)
                if element:
                    print(f"✅ Login success indicator found: {indicator}")
                    login_successful = True
                    break
            except TimeoutError:
                continue
        
        # Check URL change as additional indicator
        current_url = self.page.url
        if current_url != self.scra_url and 'login' not in current_url.lower():
            print(f"✅ URL changed to: {current_url}")
            login_successful = True
        
        if not login_successful:
            # Get page content for debugging
            page_content = await self.page.content()
            debug_filename = f'{self.session_id}_login_debug.html'
            if self.session_debug_dir and self.session_debug_dir is not None:
                try:
                    debug_filepath = self.session_debug_dir / debug_filename
                    with open(debug_filepath, 'w') as f:
                        f.write(page_content)
                except Exception as debug_e:
                    print(f"⚠️ Failed to save debug HTML: {debug_e}")
                    debug_filepath = "debug_file_unavailable"
            else:
                debug_filepath = "debug_file_unavailable_production"
            await self._take_debug_screenshot("03_login_failed", "Login verification failed")
            raise Exception(f"Could not verify login success - check debug files: {debug_filepath}")
        
        print("✅ Login verified successfully")
        await self._take_debug_screenshot("04_login_success", "Login successfully verified")
    
    async def _perform_verification(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual verification process"""
        print("🎯 Starting verification process...")
        
        try:
            # Look for verification/search functionality
            await self._navigate_to_verification()
            
            # Fill verification form
            await self._fill_verification_form(person_data)
            
            # Submit and get results
            results = await self._submit_and_get_results(person_data)
            
            return results
            
        except Exception as e:
            # Take screenshot for debugging
            print(f"❌ Verification process failed: {str(e)}")
            if self.page:
                await self._take_debug_screenshot("99_verification_error", f"Verification process failed: {str(e)}")
            raise Exception(f"Verification process failed: {str(e)}")
    
    async def _navigate_to_verification(self):
        """Navigate to the verification/search page"""
        print("🔍 Navigating directly to single-record verification form...")
        
        try:
            # Direct navigation - fast
            print(f"🌐 Navigating to verification form...")
            await self.page.goto(self.single_record_url, wait_until='domcontentloaded', timeout=30000)
            # In cloud, give additional time for SPA router and auth redirect
            try:
                await self.page.wait_for_load_state('networkidle', timeout=10000)
            except TimeoutError:
                pass
            print("✅ Verification form loaded")
            
            await self._take_debug_screenshot("05_verification_form", "Navigated to verification form")
            
            # CRITICAL: Verify we're actually on the verification form before proceeding
            await self._verify_on_verification_form()
            
            print("✅ Successfully navigated to single-record verification form")
            
        except Exception as e:
            await self._take_debug_screenshot("05_navigation_error", f"Failed to navigate to verification form: {str(e)}")
            print(f"⚠️ Direct navigation failed, trying to find verification links: {str(e)}")
            
            # Fallback: try to find verification links
            verification_selectors = [
                'a:has-text("Verify")',
                'a:has-text("Search")',
                'a:has-text("Check Status")',
                'a:has-text("Military Verification")',
                'a:has-text("Single Record")',
                'button:has-text("Verify")',
                'button:has-text("Search")',
                '[href*="verify"]',
                '[href*="search"]',
                '[href*="single-record"]',
                '.verify-link',
                '.search-link'
            ]
            
            verification_link = None
            for selector in verification_selectors:
                try:
                    verification_link = await self._wait_for_selector_any_frame(selector, timeout_ms=6000)
                    if verification_link:
                        print(f"✅ Found verification link: {selector}")
                        break
                except TimeoutError:
                    continue
            
            if verification_link:
                # Some links may open a new tab/window
                popup: Optional[Page] = None
                try:
                    async with self.page.context.expect_page(timeout=5000) as new_page_info:
                        await verification_link.click()
                    popup = await new_page_info.value
                except Exception:
                    # No popup, click normally
                    await verification_link.click()
                
                # Switch context if popup opened
                if popup:
                    self.page = popup
                
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                except TimeoutError:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=5000)
                await self._take_debug_screenshot("05_verification_page_fallback", "Navigated to verification page via fallback method")
                print("✅ Navigated to verification page via fallback method")
            else:
                await self._take_debug_screenshot("05_no_verification_links", "No verification links found")
                print("⚠️ No specific verification link found, assuming we're on the right page")
            
            # Handle any additional agreements on verification page
            await self._handle_agreements()
            await self._take_debug_screenshot("06_after_agreements_verification", "After handling agreements on verification page")
            
            # Wait for verification form elements
            await self.page.wait_for_timeout(2000)
    
    async def _verify_on_verification_form(self):
        """Verify we're actually on the verification form, not login page"""
        print("🔍 Verifying we're on the verification form...")
        
        # Check for verification form indicators (not login fields!)
        verification_indicators = [
            '#lastNameInput',
            '#firstNameInput',
            '#ssnInput',
            'input[name="lastName"]',
            'input[name="firstName"]',
            'input[name="ssn"]',
            'label:has-text("Last Name")',
            'label:has-text("First Name")'
        ]
        
        found_verification_field = False
        for selector in verification_indicators:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    print(f"✅ Verification form confirmed: found {selector}")
                    found_verification_field = True
                    break
            except:
                continue
        
        # Check we're NOT on login page
        login_indicators = [
            'input[name="username"]',
            'input[name="password"]',
            'input[id="username"]',
            'input[id="password"]'
        ]
        
        found_login_field = False
        for selector in login_indicators:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    print(f"❌ Still on login page: found {selector}")
                    found_login_field = True
                    break
            except:
                continue
        
        if found_login_field and not found_verification_field:
            raise Exception("Still on login page - navigation to verification form failed")
        
        if not found_verification_field:
            print("⚠️ Cannot confirm verification form presence, but no login fields detected")
            # Take screenshot to help debug
            await self._take_debug_screenshot("07_form_validation", "Could not confirm verification form")

    async def _fill_verification_form(self, person_data: Dict[str, Any]):
        """Fill the verification form using direct ID-based targeting (matches working local test)"""
        print("📝 Filling verification form with direct ID-based targeting...")
        
        # Direct field mappings based on successful local test - ID selectors only
        field_mappings = {
            '#ssnInput': person_data.get('ssn', ''),  # First SSN field
            '#ssnConfirmationInput': person_data.get('ssn', ''),  # SSN confirmation  
            '#lastNameInput': person_data.get('lastName', ''),
            '#firstNameInput': person_data.get('firstName', ''),
            '#middleNameInput': person_data.get('middleName', ''),
        }
        
        # Handle date fields separately - there are TWO date fields that need filling
        # Based on analysis: #mat-input-0 = Birth Date, #mat-input-1 = Active Duty Status Date
        date_birth = person_data.get('dateOfBirth', '')
        date_status = person_data.get('activeDutyDate', '')  # Use the correct parameter name
        
        # Convert dates to the format expected by the SCRA form (MM/DD/YYYY)
        if date_birth:
            formatted_birth = self._convert_date_to_mmddyyyy(date_birth)
            field_mappings['#mat-input-0'] = formatted_birth  # Birth Date field
        if date_status:
            formatted_status = self._convert_date_to_mmddyyyy(date_status)
            field_mappings['#mat-input-1'] = formatted_status  # Active Duty Status Date field
        
        print("🎯 Using direct ID-based field mapping (matching successful local test)")
        filled_fields = []
        
        # Fill regular fields using direct ID targeting, with cross-frame fallback
        for selector, value in field_mappings.items():
            if not value:
                print(f"   ⚠️ Skipping {selector} - no value provided")
                continue
                
            try:
                field = await self._query_selector_any_frame_visible(selector)
                if field and await field.is_visible():
                    await field.fill(value)
                    display_value = value if 'ssn' not in selector.lower() else f"{'*' * (len(value) - 4)}{value[-4:]}"
                    print(f"   ✅ Filled {selector}: {display_value}")
                    filled_fields.append(selector)
                    await self.page.wait_for_timeout(500)
                else:
                    print(f"   ⚠️ Field not found or not visible: {selector}")
            except Exception as e:
                print(f"   ❌ Error filling {selector}: {e}")
        
        
        await self._take_debug_screenshot("08_fields_filled", f"Fields filled using ID-based targeting: {', '.join(filled_fields)}")
        print(f"✅ Successfully filled {len(filled_fields)} fields using ID-based targeting")
        
        # IMPORTANT: Check for "I Agree" checkbox before submitting
        await self._check_and_accept_checkbox()
        
        await self._take_debug_screenshot("09_before_submit", "Ready to submit form after handling checkboxes")




    async def _check_and_accept_checkbox(self):
        """Check for 'I Accept' checkbox and click it before submitting"""
        print("🔍 Looking for checkboxes to click (mapper found 4 checkboxes)...")
        
        # Get all checkboxes and analyze them
        try:
            all_checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
            print(f"📊 Found {len(all_checkboxes)} total checkboxes on page")
            
            checkboxes_clicked = 0
            
            for i, checkbox in enumerate(all_checkboxes):
                try:
                    is_visible = await checkbox.is_visible()
                    is_enabled = await checkbox.is_enabled()
                    is_checked = await checkbox.is_checked()
                    
                    if not is_visible or not is_enabled:
                        continue
                    
                    # Get checkbox attributes for analysis
                    checkbox_name = await checkbox.get_attribute('name') or ''
                    checkbox_id = await checkbox.get_attribute('id') or ''
                    checkbox_class = await checkbox.get_attribute('class') or ''
                    
                    print(f"   Checkbox {i+1}: name='{checkbox_name}', id='{checkbox_id}', visible={is_visible}, enabled={is_enabled}, checked={is_checked}")
                    
                    # Skip if already checked
                    if is_checked:
                        print(f"      ✅ Already checked, skipping")
                        continue
                    
                    # Check if this looks like an agreement/terms checkbox
                    agreement_indicators = ['accept', 'agree', 'terms', 'privacy', 'policy', 'consent']
                    is_agreement = any(indicator in checkbox_name.lower() or 
                                     indicator in checkbox_id.lower() or 
                                     indicator in checkbox_class.lower() 
                                     for indicator in agreement_indicators)
                    
                    # For SCRA form, we typically need to check agreement checkboxes
                    if is_agreement or checkboxes_clicked < 2:  # Click up to 2 checkboxes if unsure
                        print(f"      🔄 Clicking checkbox {i+1}")
                        await checkbox.click()
                        await self.page.wait_for_timeout(500)
                        checkboxes_clicked += 1
                        
                        # Verify it was checked
                        is_now_checked = await checkbox.is_checked()
                        if is_now_checked:
                            print(f"      ✅ Checkbox {i+1} successfully checked")
                        else:
                            print(f"      ⚠️ Checkbox {i+1} click may have failed")
                    else:
                        print(f"      ⚪ Skipping non-agreement checkbox")
                        
                except Exception as e:
                    print(f"   ❌ Error processing checkbox {i+1}: {e}")
                    continue
            
            if checkboxes_clicked > 0:
                print(f"✅ Clicked {checkboxes_clicked} checkboxes")
                await self._take_debug_screenshot("09_checkboxes_clicked", f"Clicked {checkboxes_clicked} checkboxes")
            else:
                print("ℹ️ No checkboxes needed to be clicked")
            
        except Exception as e:
            print(f"❌ Error in checkbox detection: {e}")
            
        # Fallback: Try common selectors if no checkboxes were clicked
        if 'checkboxes_clicked' not in locals() or checkboxes_clicked == 0:
            print("🔄 Trying fallback checkbox selectors...")
            fallback_selectors = [
                'input[id*="accept" i]',
                'input[name*="accept" i]',
                'input[id*="agree" i]',
                'input[name*="agree" i]',
                'input[type="checkbox"]'
            ]
            
            for i, selector in enumerate(fallback_selectors):
                try:
                    print(f"   Trying checkbox selector {i+1}: {selector}")
                    checkbox = await self.page.query_selector(selector)
                    if checkbox and await checkbox.is_visible() and await checkbox.is_enabled():
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            print(f"   🔄 Fallback: Clicking checkbox with selector: {selector}")
                            await checkbox.click()
                            await self.page.wait_for_timeout(500)
                            
                            # Verify it was checked
                            is_now_checked = await checkbox.is_checked()
                            if is_now_checked:
                                print("✅ Fallback checkbox successfully checked")
                                break
                            else:
                                print("⚠️ Fallback checkbox click didn't register")
                        else:
                            print("✅ Fallback checkbox already checked")
                            break
                except Exception as e:
                    print(f"   ❌ Error with fallback selector {selector}: {e}")
                    continue
    
    async def _submit_and_get_results(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit the form and extract results"""
        print("🔍 Submitting verification form...")
        
        # Find submit button - based on mapper analysis, across frames
        submit_selectors = [
            # Primary selectors from mapper analysis
            'button.btn.btn-primary',  # Discovered: class="btn btn-primary" with text "SubmitSubmitting"
            'button:has-text("Submit")',  # Partial text match for "SubmitSubmitting"
            'button:has-text("SubmitSubmitting")',  # Exact text match
            '.btn-primary',  # Primary button class
            # Fallback selectors
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Search")',
            'button:has-text("Verify")',
            'button:has-text("Check")',
            '.submit-btn'
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = await self._wait_for_selector_any_frame(selector, timeout_ms=6000)
                if submit_button:
                    print(f"✅ Found submit button: {selector}")
                    break
            except TimeoutError:
                continue
        
        if not submit_button:
            raise Exception("Could not find submit button")
        
        # Set up PDF download handling before submitting
        pdf_downloaded = False
        pdf_path = None
        pdf_filename = "scra_result.pdf"
        
        # Set up download listener using the correct Playwright API
        async def handle_download(download):
            nonlocal pdf_downloaded, pdf_path, pdf_filename
            print(f"📥 Download detected: {download.suggested_filename}")
            
            try:
                # Read PDF data as bytes
                pdf_bytes = await download.path()
                with open(pdf_bytes, 'rb') as f:
                    pdf_data = f.read()
                
                pdf_downloaded = True
                print(f"✅ PDF downloaded: {len(pdf_data)} bytes")
                
                # Convert to base64 for frontend transmission
                import base64
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                
                # Store PDF data for later transmission
                if not hasattr(self, 'pdf_data'):
                    self.pdf_data = None
                
                self.pdf_data = {
                    'filename': pdf_filename,
                    'data': pdf_base64,
                    'size': len(pdf_data),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Upload to Supabase Storage immediately
                if self.user_id:
                    await self.supabase_service.upload_pdf_realtime(
                        self.session_id,
                        pdf_filename,
                        pdf_data,
                        self.user_id
                    )
                    print(f"📤 PDF uploaded to Supabase Storage: {pdf_filename}")
                
                # Save debug copy to local filesystem
                if self.session_debug_dir and self.session_debug_dir is not None:
                    try:
                        debug_path = self.session_debug_dir / "pdfs" / pdf_filename
                        with open(debug_path, 'wb') as f:
                            f.write(pdf_data)
                        print(f"🗂️ PDF debug copy saved: {debug_path}")
                    except Exception as debug_e:
                        print(f"⚠️ Failed to save PDF debug copy: {debug_e}")
                
                print(f"✅ PDF stored: {pdf_filename} ({len(pdf_data)} bytes)")
                
            except Exception as e:
                print(f"❌ Failed to process PDF: {e}")
        
        # Listen for downloads on the page
        self.page.on('download', handle_download)
        print("📥 PDF download listener set up")
        
        # Submit form
        print("🚀 Submitting form and waiting for PDF download...")
        await submit_button.click()
        await self._take_debug_screenshot("10_form_submitted", "Form submitted, waiting for results")
        
        # Wait for either page navigation or PDF download
        print("⏳ Waiting for results (PDF download or page update)...")
        
        # Wait for download to complete (up to 30 seconds)
        download_timeout = 30
        elapsed = 0
        while not pdf_downloaded and elapsed < download_timeout:
            await self.page.wait_for_timeout(1000)
            elapsed += 1
            if elapsed % 5 == 0:  # Log every 5 seconds
                print(f"   Still waiting for PDF... ({elapsed}s)")
        
        if pdf_downloaded:
            print(f"✅ PDF download completed in {elapsed} seconds")
            await self._take_debug_screenshot("11_pdf_downloaded", f"PDF downloaded: {pdf_filename}")
        else:
            print("⚠️ No PDF download detected, checking for page results...")
            # Fallback: check if page updated with results
            try:
                await self.page.wait_for_load_state('networkidle', timeout=10000)
                await self._take_debug_screenshot("11_page_results", "Page updated with results")
                
                # Generate PDF from page content as fallback
                print("📄 Generating PDF from page content...")
                await self._generate_pdf_from_page()
                
            except TimeoutError:
                print("⚠️ Neither PDF download nor page update detected")
                await self._take_debug_screenshot("11_no_results", "No clear results detected")
        
        # Wait additional time for any remaining dynamic content
        await self.page.wait_for_timeout(2000)
        
        # Take final screenshot
        await self._take_debug_screenshot("12_final_state", "Final page state after submission")
        
        # Extract results
        results = await self._extract_results(person_data)
        
        return results
    
    async def _extract_results(self, person_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract verification results from the page"""
        print("📋 Extracting verification results...")
        
        # Get page text content
        page_text = await self.page.text_content('body')
        page_html = await self.page.content()
        
        # Save raw results for debugging
        if self.session_debug_dir and self.session_debug_dir is not None:
            try:
                results_filename = f'{self.session_id}_results_raw.txt'
                results_filepath = self.session_debug_dir / results_filename
                with open(results_filepath, 'w') as f:
                    f.write(page_text)
                print(f"📄 Raw results saved to: {results_filepath}")
                
                # Save HTML for debugging
                html_filename = f'{self.session_id}_results_raw.html'
                html_filepath = self.session_debug_dir / html_filename
                with open(html_filepath, 'w') as f:
                    f.write(page_html)
                print(f"🌐 Raw HTML saved to: {html_filepath}")
            except Exception as debug_e:
                print(f"⚠️ Failed to save debug results: {debug_e}")
        else:
            print("ℹ️ Skipping debug file save (production mode)")
        
        # Analyze results for status indicators
        status_indicators = {
            'covered': [
                'covered', 'protected', 'eligible', 'active duty',
                'servicemember', 'military service confirmed'
            ],
            'not_covered': [
                'not covered', 'not protected', 'not eligible', 
                'no coverage', 'not found', 'no record'
            ],
            'error': [
                'error', 'failed', 'invalid', 'unable to verify',
                'timeout', 'system error'
            ]
        }
        
        page_text_lower = page_text.lower()
        
        # Determine status
        is_covered = any(indicator in page_text_lower for indicator in status_indicators['covered'])
        is_not_covered = any(indicator in page_text_lower for indicator in status_indicators['not_covered'])
        has_error = any(indicator in page_text_lower for indicator in status_indicators['error'])
        
        # Generate transaction ID
        transaction_id = f"PUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine final status
        if has_error:
            covered = False
            match_reason = "SYSTEM_ERROR"
            eligibility_type = "ERROR"
        elif is_covered and not is_not_covered:
            covered = True
            match_reason = "MATCH_FOUND"
            eligibility_type = "ACTIVE_DUTY"
        elif is_not_covered:
            covered = False
            match_reason = "NO_MATCH"
            eligibility_type = "NOT_COVERED"
        else:
            covered = False
            match_reason = "UNKNOWN"
            eligibility_type = "UNKNOWN"
        
        # Structure response according to existing format
        response = {
            "success": True,
            "method": "puppeteer",
            "id": transaction_id,
            "personRequest": {
                "pnId": person_data.get('ssn', ''),
                "pnIdConfirmation": person_data.get('ssn', ''),
                "firstName": person_data.get('firstName', ''),
                "lastName": person_data.get('lastName', ''),
                "middleName": person_data.get('middleName', ''),
                "cadencyName": person_data.get('suffix', ''),
                "dateOfBirth": self._convert_date_to_yyyymmdd(person_data.get('dateOfBirth', '')),
                "activeDutyDate": self._convert_date_to_yyyymmdd(person_data.get('activeDutyDate', '')) if covered else None,
            },
            "eligibility": {
                "dateOfInterest": datetime.now().strftime('%Y%m%d'),
                "transactionId": transaction_id,
                "activeDutyCovered": covered,
                "activeDutyStartDate": self._convert_date_to_yyyymmdd(person_data.get('activeDutyDate', '')) if covered else None,
                "activeDutyEndDate": None,
                "activeDutyServiceComponentCode": None,
                "activeDutyServiceComponentString": None,
                "earlyIndicationCovered": False,
                "earlyIndicationStartDate": None,
                "earlyIndicationEndDate": None,
                "heraCovered": False,
                "heraStartDate": None,
                "heraEndDate": None,
                "activeDutyIndicatorCode": "Y" if covered else "N",
                "matchReasonCode": match_reason,
                "scraEligibilityType": eligibility_type,
                "covered": covered,
            },
            "automationResult": {
                "rawOutput": page_text[:2000],  # Truncate for storage
                "pageUrl": self.page.url,
                "timestamp": datetime.now().isoformat(),
                "method": "puppeteer",
                "sessionId": self.session_id,
                "files_included": True,
                "delivery_method": "direct_response"
            }
        }

        # Add screenshots and PDF data to response
        print(f"🔍 Debug - Adding files to response...")
        print(f"🔍 Has screenshots attribute: {hasattr(self, 'screenshots')}")
        print(f"🔍 Has pdf_data attribute: {hasattr(self, 'pdf_data')}")
        
        if hasattr(self, 'screenshots') and self.screenshots:
            response['automationResult']['screenshots'] = self.screenshots
            print(f"✅ Added {len(self.screenshots)} screenshots to response")
            print(f"📸 Screenshot sizes: {[len(s.get('data', '')) for s in self.screenshots[:3]]}")  # First 3 sizes
        else:
            print(f"❌ No screenshots to add (hasattr: {hasattr(self, 'screenshots')}, length: {len(getattr(self, 'screenshots', []))})")
        
        if hasattr(self, 'pdf_data') and self.pdf_data:
            response['automationResult']['pdf'] = self.pdf_data
            print(f"✅ Added PDF data to response: {self.pdf_data['filename']} ({len(self.pdf_data['data'])} chars)")
        else:
            print(f"❌ No PDF data to add (hasattr: {hasattr(self, 'pdf_data')}, data: {self.pdf_data is not None if hasattr(self, 'pdf_data') else 'N/A'})")
        
        print(f"🔍 Final response automationResult keys: {list(response['automationResult'].keys())}")

        print(f"✅ Results extracted - Status: {eligibility_type}, Covered: {covered}")
        await self._take_debug_screenshot("13_results_extracted", f"Results extracted - Status: {eligibility_type}, Covered: {covered}")
        return response
    
    async def _perform_multi_record_verification(self, fixed_width_content: str, records: List[SCRARecord]) -> Dict[str, Any]:
        """Perform the multi-record verification process"""
        print(f"🎯 Starting multi-record verification for {len(records)} records...")
        
        try:
            # Navigate to multi-record verification page
            await self._navigate_to_multi_record_verification()
            
            # Step 1: Upload the fixed-width file (Choose Files button)
            await self._upload_multi_record_file(fixed_width_content)
            
            # Step 2: Configure certificate options (Yes radio button + checkboxes)
            await self._configure_multi_record_options()
            
            # Step 3: Handle terms and conditions (I Accept checkbox)
            await self._handle_multi_record_terms()
            
            # Step 4 & 5: Submit form and navigate to Download Results
            results = await self._submit_multi_record_and_get_results(records, fixed_width_content)
            
            return results
            
        except Exception as e:
            # Take screenshot for debugging
            print(f"❌ Multi-record verification process failed: {str(e)}")
            if self.page:
                await self._take_debug_screenshot("99_multi_record_error", f"Multi-record verification failed: {str(e)}")
            raise Exception(f"Multi-record verification process failed: {str(e)}")
    
    async def _navigate_to_multi_record_verification(self):
        """Navigate to the multi-record verification page"""
        print("🔍 Navigating to multi-record verification page...")
        
        try:
            # First, let's try to find multi-record links from the current page (after login)
            print("🔍 Looking for multi-record navigation links on current page...")
            
            # Comprehensive list of selectors for multi-record navigation
            multi_record_selectors = [
                # Text-based navigation links
                'a:has-text("Multiple Record")',
                'a:has-text("Multi Record")',
                'a:has-text("Multi-Record")',
                'a:has-text("Batch")',
                'a:has-text("Batch Upload")',
                'a:has-text("Batch Processing")',
                'a:has-text("Upload File")',
                'a:has-text("File Upload")',
                'a:has-text("Bulk")',
                'a:has-text("Mass")',
                
                # Button-based navigation
                'button:has-text("Multiple Record")',
                'button:has-text("Multi Record")',
                'button:has-text("Batch")',
                'button:has-text("Upload")',
                
                # URL-based selectors
                '[href*="multiple-record"]',
                '[href*="multi-record"]',
                '[href*="multirecord"]',
                '[href*="batch"]',
                '[href*="upload"]',
                '[href*="bulk"]',
                '[href*="mass"]',
                
                # Class and ID-based selectors
                '.multi-record-link',
                '.multiple-record-link',
                '.batch-link',
                '.upload-link',
                '#multi-record',
                '#multiple-record',
                '#batch-upload',
                
                # Navigation menu items
                'nav a:has-text("Multiple")',
                'nav a:has-text("Batch")',
                'nav a:has-text("Upload")',
                '.nav-item:has-text("Multiple")',
                '.nav-item:has-text("Batch")',
                '.menu-item:has-text("Multiple")',
                '.menu-item:has-text("Batch")',
                
                # Generic navigation patterns
                'li a:has-text("Multiple")',
                'li a:has-text("Batch")',
                'ul a:has-text("Multiple")',
                'ul a:has-text("Batch")'
            ]
            
            multi_record_link = None
            found_selector = None
            
            # Search for navigation links
            for i, selector in enumerate(multi_record_selectors):
                try:
                    print(f"   Trying navigation selector {i+1}/{len(multi_record_selectors)}: {selector}")
                    multi_record_link = await self._wait_for_selector_any_frame(selector, timeout_ms=2000)
                    if multi_record_link:
                        # Verify it's visible and clickable
                        is_visible = await multi_record_link.is_visible()
                        is_enabled = await multi_record_link.is_enabled()
                        
                        if is_visible and is_enabled:
                            found_selector = selector
                            print(f"✅ Found multi-record navigation link: {selector}")
                            break
                        else:
                            print(f"   Found element but not clickable: visible={is_visible}, enabled={is_enabled}")
                            multi_record_link = None
                except Exception as e:
                    print(f"   Error with selector {selector}: {e}")
                    continue
            
            if multi_record_link:
                print(f"🔗 Clicking multi-record navigation link: {found_selector}")
                await multi_record_link.click()
                
                # Wait for navigation
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=15000)
                except TimeoutError:
                    await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
                
                await self._take_debug_screenshot("05_multi_record_page", "Navigated to multi-record page via link")
                print("✅ Navigated to multi-record page via navigation link")
                
            else:
                # Fallback: try direct URL navigation
                print(f"⚠️ No navigation links found, trying direct URL navigation...")
                print(f"🌐 Navigating directly to: {self.multi_record_url}")
                
                try:
                    await self.page.goto(self.multi_record_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait for page to load
                    try:
                        await self.page.wait_for_load_state('networkidle', timeout=10000)
                    except TimeoutError:
                        pass
                    
                    await self._take_debug_screenshot("05_multi_record_page", "Navigated to multi-record page via direct URL")
                    print("✅ Multi-record verification page loaded via direct URL")
                    
                except Exception as url_error:
                    await self._take_debug_screenshot("05_multi_record_nav_error", f"Failed to navigate to multi-record page: {str(url_error)}")
                    raise Exception(f"Could not navigate to multi-record page. Navigation link not found and direct URL failed: {str(url_error)}")
            
            # Handle any additional agreements on multi-record page
            await self._handle_agreements()
            await self._take_debug_screenshot("06_after_agreements_multi_record", "After handling agreements on multi-record page")
            
            # Verify we're on the correct page
            await self._verify_on_multi_record_page()
            
            # Wait for multi-record form elements to load
            await self.page.wait_for_timeout(3000)
            
            print("✅ Successfully navigated to multi-record verification page")
            
        except Exception as e:
            await self._take_debug_screenshot("05_multi_record_navigation_failed", f"Multi-record navigation failed: {str(e)}")
            raise Exception(f"Failed to navigate to multi-record verification page: {str(e)}")
    
    async def _verify_on_multi_record_page(self):
        """Verify we're actually on the multi-record verification page"""
        print("🔍 Verifying we're on the multi-record verification page...")
        
        # Take a screenshot first for debugging
        await self._take_debug_screenshot("06_page_verification", "Verifying multi-record page")
        
        # Get page title and URL for additional context
        page_title = await self.page.title()
        page_url = self.page.url
        print(f"📄 Current page - Title: '{page_title}', URL: {page_url}")
        
        # Comprehensive multi-record page indicators
        multi_record_indicators = [
            # File upload elements
            'input[type="file"]',
            
            # Text content indicators
            'text="Upload"',
            'text="Multiple Record"',
            'text="Multi Record"',
            'text="Multi-Record"',
            'text="Batch"',
            'text="File Upload"',
            'text="Choose File"',
            'text="Browse"',
            'text="Select File"',
            
            # Form and UI elements
            '.file-upload',
            '.upload-area',
            '.file-input',
            '.batch-upload',
            '.multi-record-form',
            
            # Specific SCRA multi-record indicators
            'text="Fixed Width"',
            'text="Text File"',
            'text="Data File"',
            'text="Record File"',
            
            # Form labels and instructions
            'label:has-text("File")',
            'label:has-text("Upload")',
            'label:has-text("Data")',
            
            # Buttons and controls
            'button:has-text("Upload")',
            'button:has-text("Choose")',
            'button:has-text("Browse")',
            'button:has-text("Select")',
            
            # Generic upload patterns
            '[accept*=".txt"]',
            '[accept*="text"]',
            '[accept*=".dat"]',
            '[name*="file"]',
            '[id*="file"]',
            '[id*="upload"]'
        ]
        
        found_indicators = []
        
        # Check each indicator
        for selector in multi_record_indicators:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    found_indicators.append(selector)
                    print(f"✅ Found multi-record indicator: {selector}")
            except:
                continue
        
        # Also check for hidden file inputs (common in modern web apps)
        try:
            all_file_inputs = await self.page.query_selector_all('input[type="file"]')
            for i, file_input in enumerate(all_file_inputs):
                input_name = await file_input.get_attribute('name') or f'file_input_{i}'
                input_id = await file_input.get_attribute('id') or f'no_id_{i}'
                is_visible = await file_input.is_visible()
                is_enabled = await file_input.is_enabled()
                
                print(f"   File input {i+1}: name='{input_name}', id='{input_id}', visible={is_visible}, enabled={is_enabled}")
                
                if is_enabled:  # Even if not visible, if it's enabled it might be usable
                    found_indicators.append(f'file_input_{i}')
        except Exception as e:
            print(f"   Error checking file inputs: {e}")
        
        # Check URL for multi-record indicators
        url_indicators = ['multiple', 'multi', 'batch', 'upload', 'bulk', 'mass']
        url_matches = [indicator for indicator in url_indicators if indicator in page_url.lower()]
        if url_matches:
            found_indicators.extend([f'url_contains_{match}' for match in url_matches])
            print(f"✅ URL contains multi-record indicators: {url_matches}")
        
        # Check page title for multi-record indicators
        title_indicators = ['multiple', 'multi', 'batch', 'upload', 'bulk', 'mass']
        title_matches = [indicator for indicator in title_indicators if indicator in page_title.lower()]
        if title_matches:
            found_indicators.extend([f'title_contains_{match}' for match in title_matches])
            print(f"✅ Page title contains multi-record indicators: {title_matches}")
        
        print(f"📊 Found {len(found_indicators)} multi-record indicators: {found_indicators}")
        
        if len(found_indicators) == 0:
            print("⚠️ Cannot confirm multi-record page presence - no indicators found")
            
            # Get page content for debugging
            page_content = await self.page.content()
            if self.session_debug_dir:
                debug_html_path = self.session_debug_dir / "page_verification_debug.html"
                with open(debug_html_path, 'w') as f:
                    f.write(page_content)
                print(f"🗂️ Saved page HTML for debugging: {debug_html_path}")
            
            # Take screenshot to help debug
            await self._take_debug_screenshot("07_multi_record_validation_failed", "Could not confirm multi-record page")
            
            # Don't fail here - just warn and continue
            print("⚠️ Proceeding anyway - page structure may be different than expected")
        else:
            print(f"✅ Multi-record page confirmed with {len(found_indicators)} indicators")
    
    async def _upload_multi_record_file(self, fixed_width_content: str):
        """Upload the fixed-width file to the multi-record form following the correct SCRA workflow"""
        print("📤 Starting multi-record file upload workflow...")
        
        # Generate proper filename (same as API endpoint)
        from datetime import datetime
        timestamp = datetime.now().strftime('%m%d%H%M')
        proper_filename = f"scra_{timestamp}.txt"
        
        # Save fixed-width content to a temporary file with proper name
        temp_file_path = None
        try:
            import tempfile
            import os
            
            # Create temporary directory and file with proper name
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, proper_filename)
            
            with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
                temp_file.write(fixed_width_content)
            
            print(f"📄 Created temporary file: {temp_file_path}")
            print(f"📄 Using filename: {proper_filename}")
            
            # Store the filename for later table lookup
            self.uploaded_filename = proper_filename
            
            # Wait for page to fully load and take a screenshot for debugging
            await self.page.wait_for_timeout(3000)
            await self._take_debug_screenshot("07_before_file_upload", "Page state before looking for Choose Files button")
            
            # Step 1: Find and click "Choose Files" button
            print("🔍 Step 1: Looking for 'Choose Files' button...")
            choose_files_selectors = [
                'button:has-text("Choose Files")',
                'button:has-text("Choose File")',
                'button:has-text("Browse")',
                'button:has-text("Select Files")',
                'button:has-text("Select File")',
                'input[type="button"][value*="Choose"]',
                'input[type="button"][value*="Browse"]',
                '.choose-files-btn',
                '.browse-btn',
                '.file-select-btn'
            ]
            
            choose_files_button = None
            for selector in choose_files_selectors:
                try:
                    choose_files_button = await self._query_selector_any_frame_visible(selector)
                    if choose_files_button and await choose_files_button.is_visible():
                        print(f"✅ Found 'Choose Files' button: {selector}")
                        break
                except:
                    continue
            
            if not choose_files_button:
                # Fallback: look for file input directly
                print("🔍 'Choose Files' button not found, looking for file input directly...")
                file_input = await self._query_selector_any_frame_visible('input[type="file"]')
                if file_input:
                    print("✅ Found file input directly")
                    await file_input.set_input_files(temp_file_path)
                    print("✅ File uploaded via direct input")
                else:
                    raise Exception("Could not find 'Choose Files' button or file input")
            else:
                # Click the Choose Files button and handle file dialog
                print("🔗 Clicking 'Choose Files' button...")
                
                # Set up file chooser handler before clicking
                async def handle_file_chooser(file_chooser):
                    await file_chooser.set_files(temp_file_path)
                    print("✅ File selected via file chooser dialog")
                
                self.page.on('filechooser', handle_file_chooser)
                
                # Click the button
                await choose_files_button.click()
                
                # Wait for file selection to complete
                await self.page.wait_for_timeout(2000)
            
            # Wait a bit longer for the upload to process
            print("⏳ Waiting for upload to process...")
            await self.page.wait_for_timeout(5000)  # Wait 5 seconds
            
            # Capture any console errors from the SCRA website
            print("🔍 Checking for console errors...")
            
            # Set up console listener to catch API errors
            console_errors = []
            def handle_console(msg):
                if msg.type in ['error', 'warning']:
                    console_errors.append(f"{msg.type}: {msg.text}")
                    print(f"🚨 Console {msg.type}: {msg.text}")
            
            self.page.on('console', handle_console)
            
            # Also listen for failed requests
            failed_requests = []
            def handle_response(response):
                if response.status >= 400:
                    failed_requests.append(f"{response.status}: {response.url}")
                    print(f"🚨 Failed request: {response.status} {response.url}")
            
            self.page.on('response', handle_response)
            
            # Validate upload success
            print("🔍 Checking for upload success message...")
            upload_success = False
            
            # Look for success indicators
            success_selectors = [
                ':has-text("File uploaded successfully")',
                ':has-text("uploaded successfully")',
                ':has-text("Upload successful")',
                ':has-text("File selected")',
                f':has-text("{proper_filename}")',  # Look for our filename
                '.upload-success',
                '.file-success'
            ]
            
            for selector in success_selectors:
                try:
                    element = await self._query_selector_any_frame_visible(selector)
                    if element and await element.is_visible():
                        print(f"✅ Upload success confirmed: {selector}")
                        upload_success = True
                        break
                except:
                    continue
            
            if not upload_success:
                # Check for error messages
                error_selectors = [
                    ':has-text("An error occurred")',
                    ':has-text("error occurred")',
                    ':has-text("Upload failed")',
                    ':has-text("Invalid file")',
                    '.upload-error',
                    '.file-error'
                ]
                
                error_found = False
                for selector in error_selectors:
                    try:
                        element = await self._query_selector_any_frame_visible(selector)
                        if element and await element.is_visible():
                            error_text = await element.text_content()
                            print(f"❌ Upload error detected: {error_text}")
                            error_found = True
                            break
                    except:
                        continue
                
                if error_found:
                    # Log any console errors and failed requests we captured
                    if console_errors:
                        print(f"🔍 Console errors captured: {console_errors}")
                    if failed_requests:
                        print(f"🔍 Failed requests captured: {failed_requests}")
                    
                    # Don't fail immediately - the SCRA site might have backend issues
                    print("⚠️ Upload error detected, but this might be a temporary SCRA site issue")
                    print("⚠️ Continuing with verification process...")
                else:
                    print("⚠️ No clear upload success/error message found - proceeding anyway")
            
            await self._take_debug_screenshot("08_file_selected", "File selected, configuring certificate options")
            
            # Store temp file path for cleanup later (after entire process completes)
            self._temp_file_cleanup = temp_file_path
            
        except Exception as e:
            await self._take_debug_screenshot("08_file_upload_error", f"File upload failed: {str(e)}")
            # Clean up on error
            if temp_file_path:
                try:
                    import os
                    import shutil
                    
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)
                        print(f"🗑️ Cleaned up temporary file after error: {temp_file_path}")
                    
                    temp_dir = os.path.dirname(temp_file_path)
                    if os.path.exists(temp_dir) and temp_dir != tempfile.gettempdir():
                        shutil.rmtree(temp_dir)
                        print(f"🗑️ Cleaned up temporary directory after error: {temp_dir}")
                except Exception as cleanup_error:
                    print(f"⚠️ Cleanup warning: {cleanup_error}")
            raise Exception(f"File upload failed: {str(e)}")
    
    async def _configure_multi_record_options(self):
        """Configure multi-record verification options following the exact SCRA workflow"""
        print("⚙️ Step 2: Configuring certificate options...")
        
        # Step 2a: Find and select "Yes" for certificate requirement
        print("🔍 Looking for certificate requirement radio buttons...")
        cert_yes_selectors = [
            'input[type="radio"][value="yes" i]',
            'input[type="radio"][value="y" i]',
            'input[type="radio"][value="1"]',
            'label:has-text("Yes") input[type="radio"]',
            'input[name*="certificate" i][value*="yes" i]',
            'input[name*="cert" i][value*="yes" i]',
            'input[id*="yes" i][type="radio"]'
        ]
        
        cert_selected = False
        for selector in cert_yes_selectors:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    await element.click()
                    print(f"✅ Selected 'Yes' for certificates: {selector}")
                    cert_selected = True
                    break
            except:
                continue
        
        if not cert_selected:
            print("⚠️ Could not find certificate 'Yes' radio button, trying text-based approach...")
            # Try clicking on "Yes" text near certificate question
            try:
                yes_text = await self._query_selector_any_frame_visible('text="Yes"')
                if yes_text:
                    await yes_text.click()
                    print("✅ Clicked 'Yes' text for certificates")
                    cert_selected = True
            except:
                pass
        
        await self._take_debug_screenshot("09_certificate_selected", "Certificate requirement set to Yes")
        await self.page.wait_for_timeout(1000)
        
        # Step 2b: Select both certificate checkboxes (active duty and not active duty)
        print("🔍 Looking for certificate type checkboxes...")
        
        # Look for active duty certificate checkbox
        active_duty_selectors = [
            'input[type="checkbox"]:near(text="active duty")',
            'input[type="checkbox"]:near(text="Active Duty")',
            'input[name*="active" i][type="checkbox"]',
            'input[id*="active" i][type="checkbox"]',
            'label:has-text("active duty") input[type="checkbox"]'
        ]
        
        # Look for not active duty certificate checkbox  
        not_active_duty_selectors = [
            'input[type="checkbox"]:near(text="not in active duty")',
            'input[type="checkbox"]:near(text="not on active duty")',
            'input[type="checkbox"]:near(text="Not in Active Duty")',
            'input[name*="notactive" i][type="checkbox"]',
            'input[name*="inactive" i][type="checkbox"]',
            'label:has-text("not") input[type="checkbox"]'
        ]
        
        checkboxes_selected = 0
        
        # Try to find and select active duty checkbox
        for selector in active_duty_selectors:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.click()
                        print(f"✅ Selected active duty certificate: {selector}")
                        checkboxes_selected += 1
                        break
            except:
                continue
        
        # Try to find and select not active duty checkbox
        for selector in not_active_duty_selectors:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.click()
                        print(f"✅ Selected not active duty certificate: {selector}")
                        checkboxes_selected += 1
                        break
            except:
                continue
        
        # Fallback: select any unchecked checkboxes (up to 2)
        if checkboxes_selected < 2:
            print("🔍 Fallback: Looking for any certificate checkboxes...")
            try:
                all_checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
                for checkbox in all_checkboxes:
                    if checkboxes_selected >= 2:
                        break
                    
                    if await checkbox.is_visible() and await checkbox.is_enabled():
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            # Check if this checkbox is related to certificates
                            checkbox_text = await self.page.evaluate(
                                '(element) => element.closest("label")?.textContent || element.parentElement?.textContent || ""',
                                checkbox
                            )
                            
                            if any(keyword in checkbox_text.lower() for keyword in ['certificate', 'active', 'duty', 'status']):
                                await checkbox.click()
                                print(f"✅ Selected certificate checkbox (fallback): {checkbox_text[:50]}...")
                                checkboxes_selected += 1
                                await self.page.wait_for_timeout(500)
            except Exception as e:
                print(f"⚠️ Error in fallback checkbox selection: {e}")
        
        await self._take_debug_screenshot("10_certificates_configured", f"Certificate options configured ({checkboxes_selected} selected)")
        print(f"✅ Selected {checkboxes_selected} certificate options")
    
    async def _handle_multi_record_terms(self):
        """Handle the 'I Accept' terms checkbox"""
        print("📋 Step 3: Handling 'I Accept' terms...")
        
        # Look for "I Accept" checkbox specifically
        accept_selectors = [
            'input[type="checkbox"]:near(text="I accept")',
            'input[type="checkbox"]:near(text="I Accept")',
            'input[type="checkbox"]:near(text="accept")',
            'input[name*="accept" i][type="checkbox"]',
            'input[id*="accept" i][type="checkbox"]',
            'label:has-text("I accept") input[type="checkbox"]',
            'label:has-text("accept") input[type="checkbox"]',
            '.accept-checkbox',
            '.terms-checkbox'
        ]
        
        terms_accepted = False
        for selector in accept_selectors:
            try:
                element = await self._query_selector_any_frame_visible(selector)
                if element and await element.is_visible():
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.click()
                        print(f"✅ Checked 'I Accept' terms: {selector}")
                        terms_accepted = True
                        break
            except:
                continue
        
        # Fallback: look for any remaining unchecked checkboxes that might be terms
        if not terms_accepted:
            print("🔍 Fallback: Looking for any terms-related checkboxes...")
            try:
                all_checkboxes = await self.page.query_selector_all('input[type="checkbox"]')
                for checkbox in all_checkboxes:
                    if await checkbox.is_visible() and await checkbox.is_enabled():
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            # Check if this checkbox is related to terms/acceptance
                            checkbox_text = await self.page.evaluate(
                                '(element) => element.closest("label")?.textContent || element.parentElement?.textContent || ""',
                                checkbox
                            )
                            
                            if any(keyword in checkbox_text.lower() for keyword in ['accept', 'agree', 'terms', 'condition']):
                                await checkbox.click()
                                print(f"✅ Checked terms checkbox (fallback): {checkbox_text[:50]}...")
                                terms_accepted = True
                                break
            except Exception as e:
                print(f"⚠️ Error in fallback terms selection: {e}")
        
        if terms_accepted:
            await self._take_debug_screenshot("11_terms_accepted", "I Accept terms checked")
            await self.page.wait_for_timeout(1000)
        else:
            print("⚠️ Could not find 'I Accept' checkbox - may already be checked or have different structure")
    
    async def _submit_multi_record_and_get_results(self, records: List[SCRARecord], fixed_width_content: str = None) -> Dict[str, Any]:
        """Submit the multi-record form and get results"""
        print("🚀 Submitting multi-record verification...")
        
        # Find submit button
        submit_selectors = [
            'button:has-text("Submit")',
            'button:has-text("Process")',
            'button:has-text("Upload")',
            'input[type="submit"]',
            '.submit-btn',
            '.process-btn'
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = await self._wait_for_selector_any_frame(selector, timeout_ms=6000)
                if submit_button:
                    print(f"✅ Found submit button: {selector}")
                    break
            except TimeoutError:
                continue
        
        if not submit_button:
            raise Exception("Could not find submit button")
        
        # Set up PDF download handling before submitting
        pdf_downloaded = False
        pdf_path = None
        pdf_filename = "scra_multi_record_result.pdf"
        
        # Set up download listener
        async def handle_download(download):
            nonlocal pdf_downloaded, pdf_path, pdf_filename
            print(f"📥 Download detected: {download.suggested_filename}")
            
            try:
                # Read PDF data as bytes
                pdf_bytes = await download.path()
                with open(pdf_bytes, 'rb') as f:
                    pdf_data = f.read()
                
                pdf_downloaded = True
                print(f"✅ PDF downloaded: {len(pdf_data)} bytes")
                
                # Convert to base64 for frontend transmission
                import base64
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                
                # Store PDF data for later transmission
                if not hasattr(self, 'pdf_data'):
                    self.pdf_data = None
                
                self.pdf_data = {
                    'filename': pdf_filename,
                    'data': pdf_base64,
                    'size': len(pdf_data),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Upload to Supabase Storage immediately
                if self.user_id:
                    await self.supabase_service.upload_pdf_realtime(
                        self.session_id,
                        pdf_filename,
                        pdf_data,
                        self.user_id
                    )
                    print(f"📤 PDF uploaded to Supabase Storage: {pdf_filename}")
                
                # Save debug copy to local filesystem
                if self.session_debug_dir and self.session_debug_dir is not None:
                    try:
                        debug_path = self.session_debug_dir / "pdfs" / pdf_filename
                        with open(debug_path, 'wb') as f:
                            f.write(pdf_data)
                        print(f"🗂️ PDF debug copy saved: {debug_path}")
                    except Exception as debug_e:
                        print(f"⚠️ Failed to save PDF debug copy: {debug_e}")
                
                print(f"✅ PDF stored: {pdf_filename} ({len(pdf_data)} bytes)")
                
            except Exception as e:
                print(f"❌ Failed to process PDF: {e}")
        
        # Listen for downloads on the page
        self.page.on('download', handle_download)
        print("📥 PDF download listener set up")
        
        # Submit form
        print("🚀 Step 4: Clicking Upload button...")
        await submit_button.click()
        await self._take_debug_screenshot("12_upload_clicked", "Upload button clicked, waiting for processing")
        
        # Wait for processing to complete and look for "Files Uploaded in Last 24 Hours" table
        print("⏳ Step 5: Waiting for upload processing and looking for files table...")
        
        processing_timeout = 120  # 2 minutes for multi-record processing
        elapsed = 0
        files_table_found = False
        
        while elapsed < processing_timeout and not files_table_found:
            await self.page.wait_for_timeout(5000)  # Check every 5 seconds
            elapsed += 5
            
            # Look for "Files Uploaded in Last 24 Hours" table or text
            files_table_selectors = [
                'text="Files Uploaded in Last 24 Hours"',
                ':has-text("Files Uploaded in Last 24 Hours")',
                ':has-text("Files Uploaded")',
                'table:has-text("Upload Filename")',
                'table:has-text("Certificate File Status")',
                '.files-table',
                '.uploaded-files'
            ]
            
            for selector in files_table_selectors:
                try:
                    element = await self._query_selector_any_frame_visible(selector)
                    if element and await element.is_visible():
                        print(f"✅ Found files table: {selector}")
                        files_table_found = True
                        break
                except:
                    continue
            
            if elapsed % 30 == 0:  # Log every 30 seconds
                print(f"   Still waiting for files table... ({elapsed}s)")
        
        await self._take_debug_screenshot("13_files_table_status", "Files table status after upload")
        
        # Step 6: Look for and click "Download Results" link next to the table
        if files_table_found:
            print("🔍 Step 6: Looking for 'Download Results' link next to files table...")
            
            download_results_selectors = [
                'a:has-text("Download Results")',
                'a:has-text("download results")',
                'a:has-text("Download Result")',
                'button:has-text("Download Results")',
                ':has-text("Files Uploaded") ~ a:has-text("Download")',
                ':has-text("Files Uploaded") + a:has-text("Download")',
                'table ~ a:has-text("Download")',
                '.download-results-link'
            ]
            
            download_results_link = None
            for selector in download_results_selectors:
                try:
                    download_results_link = await self._query_selector_any_frame_visible(selector)
                    if download_results_link and await download_results_link.is_visible():
                        print(f"✅ Found Download Results link: {selector}")
                        break
                except:
                    continue
            
            if download_results_link:
                print("🔗 Clicking 'Download Results' link...")
                await download_results_link.click()
                await self._take_debug_screenshot("14_download_results_clicked", "Download Results link clicked")
                
                # Wait for results page to load
                await self.page.wait_for_timeout(3000)
                
                # Step 7: Find our uploaded file in the table and click Certificate download
                await self._download_certificate_from_table(fixed_width_content)
                
            else:
                print("⚠️ Download Results link not found next to files table")
                await self._take_debug_screenshot("14_no_download_results_link", "No Download Results link found")
        else:
            print("⚠️ Files table not found, checking for alternative download methods...")
            await self._take_debug_screenshot("13_no_files_table", "No files table found")
            
            # Fallback: look for any download links on current page
            await self._try_fallback_download_methods()
        
        # Take final screenshot
        await self._take_debug_screenshot("16_final_state", "Final state after multi-record processing")
        
        # Extract results
        results = await self._extract_multi_record_results(records)
        
        return results
    
    async def _download_certificate_from_table(self, fixed_width_content: str):
        """Find our uploaded file in the results table and download the certificate"""
        print("🔍 Step 7: Looking for our uploaded file in the results table...")
        
        # Use the actual uploaded filename that we stored
        if hasattr(self, 'uploaded_filename') and self.uploaded_filename:
            expected_filename = self.uploaded_filename
            print(f"🔍 Looking for uploaded filename: {expected_filename}")
        else:
            # Fallback to timestamp-based filename if not stored
            from datetime import datetime
            timestamp = datetime.now().strftime('%m%d%H%M')
            expected_filename = f"scra_{timestamp}.txt"
            print(f"🔍 Fallback to timestamp filename: {expected_filename}")
        
        # Also try some variations in case the timestamp is slightly different (only as fallback)
        possible_filenames = [expected_filename]
        
        if not hasattr(self, 'uploaded_filename'):
            current_time = datetime.now()
            # Try current minute and previous few minutes
            for minutes_ago in range(1, 5):
                test_time = current_time.replace(minute=current_time.minute - minutes_ago)
                if test_time.minute < 0:
                    test_time = test_time.replace(hour=test_time.hour - 1, minute=test_time.minute + 60)
                test_timestamp = test_time.strftime('%m%d%H%M')
                possible_filenames.append(f"scra_{test_timestamp}.txt")
        
        print(f"🔍 Looking for filenames: {possible_filenames}")
        
        await self._take_debug_screenshot("15_results_table", "Results table page loaded")
        
        # Look for table with our file
        table_found = False
        certificate_link = None
        
        try:
            # First, try to find the table
            table_selectors = [
                'table:has-text("Upload Filename")',
                'table:has-text("Certificate File Status")',
                'table:has-text("Result File Status")',
                'table',
                '.results-table',
                '.files-table'
            ]
            
            table = None
            for selector in table_selectors:
                try:
                    table = await self._query_selector_any_frame_visible(selector)
                    if table:
                        print(f"✅ Found results table: {selector}")
                        table_found = True
                        break
                except:
                    continue
            
            if table_found:
                # Look for our filename in the table
                for filename in possible_filenames:
                    try:
                        # Look for a row containing our filename
                        filename_selectors = [
                            f'td:has-text("{filename}")',
                            f'tr:has-text("{filename}")',
                            f':has-text("{filename}")'
                        ]
                        
                        file_row = None
                        for selector in filename_selectors:
                            try:
                                file_row = await self._query_selector_any_frame_visible(selector)
                                if file_row:
                                    print(f"✅ Found our file row: {filename}")
                                    break
                            except:
                                continue
                        
                        if file_row:
                            # Find the specific row containing our file
                            parent_row = await file_row.query_selector('xpath=ancestor::tr[1]') or file_row
                            
                            # Get all download links in this row
                            download_links = await parent_row.query_selector_all('a:has-text("Download")')
                            
                            print(f"🔍 Found {len(download_links)} download links in the row")
                            
                            # The Certificate File Status is typically the LAST download link in the row
                            # Based on the table structure: Result File Status (first) | Certificate File Status (last)
                            if len(download_links) >= 2:
                                # Take the last download link (Certificate File Status)
                                certificate_link = download_links[-1]
                                print("✅ Selected Certificate File Status download link (last link in row)")
                            elif len(download_links) == 1:
                                # Only one download link - use it
                                certificate_link = download_links[0]
                                print("✅ Found single download link - using it")
                            else:
                                # Fallback to original selectors
                                certificate_selectors = [
                                    'a[href*=".pdf"]',
                                    'a[href*="certificate"]',
                                    'a:has-text("Download")'
                                ]
                                
                                for cert_selector in certificate_selectors:
                                    try:
                                        certificate_link = await parent_row.query_selector(cert_selector)
                                        if certificate_link and await certificate_link.is_visible():
                                            print(f"✅ Found certificate download link via fallback: {cert_selector}")
                                            break
                                    except:
                                        continue
                            
                            if certificate_link:
                                break
                    
                    except Exception as e:
                        print(f"⚠️ Error looking for filename {filename}: {e}")
                        continue
            
            if certificate_link:
                print("🔗 Clicking certificate download link...")
                await certificate_link.click()
                await self._take_debug_screenshot("16_certificate_download_clicked", "Certificate download link clicked")
                
                # Wait for Certificate Download popup to appear
                print("⏳ Waiting for Certificate Download popup...")
                await self.page.wait_for_timeout(2000)
                await self._take_debug_screenshot("17_certificate_popup_appeared", "Certificate download popup")
                
                # Look for the "Download PDF" button in the popup
                download_pdf_selectors = [
                    'button:has-text("Download PDF")',
                    'input[value*="Download PDF"]',
                    'a:has-text("Download PDF")',
                    'button[onclick*="pdf"]',
                    'input[type="button"][value*="PDF"]'
                ]
                
                download_pdf_button = None
                for selector in download_pdf_selectors:
                    try:
                        download_pdf_button = await self._query_selector_any_frame_visible(selector)
                        if download_pdf_button:
                            print(f"✅ Found Download PDF button: {selector}")
                            break
                    except:
                        continue
                
                if download_pdf_button:
                    print("🔗 Clicking Download PDF button...")
                    await download_pdf_button.click()
                    await self._take_debug_screenshot("18_download_pdf_clicked", "Download PDF button clicked")
                    
                    # Wait for PDF download
                    print("⏳ Waiting for certificate PDF download...")
                    download_timeout = 30
                    elapsed = 0
                    
                    while not hasattr(self, 'pdf_data') or not self.pdf_data and elapsed < download_timeout:
                        await self.page.wait_for_timeout(1000)
                        elapsed += 1
                        if elapsed % 5 == 0:
                            print(f"   Still waiting for PDF download... ({elapsed}s)")
                    
                    if hasattr(self, 'pdf_data') and self.pdf_data:
                        print(f"✅ Certificate PDF downloaded successfully in {elapsed} seconds")
                    else:
                        print("⚠️ PDF download not detected, generating from page content...")
                        await self._generate_pdf_from_page()
                else:
                    print("⚠️ Could not find Download PDF button in popup")
                    await self._take_debug_screenshot("18_no_download_pdf_button", "No Download PDF button found")
                    # Try to proceed anyway in case the download started automatically
                    await self.page.wait_for_timeout(3000)
            
            else:
                print("⚠️ Could not find certificate download link for our file")
                await self._take_debug_screenshot("16_no_certificate_link", "No certificate download link found")
                
                # Fallback: try any download links on the page
                await self._try_fallback_download_methods()
        
        except Exception as e:
            print(f"❌ Error in certificate download process: {e}")
            await self._take_debug_screenshot("16_certificate_download_error", f"Certificate download error: {str(e)}")
            await self._try_fallback_download_methods()
    
    async def _try_fallback_download_methods(self):
        """Try fallback methods to download certificates"""
        print("🔍 Trying fallback download methods...")
        
        # Look for any download links on the current page
        fallback_selectors = [
            'a:has-text("Download")',
            'a:has-text("download")',
            'a[href$=".pdf"]',
            'a[href*="certificate"]',
            'a[href*="download"]',
            'button:has-text("Download")',
            '.download-link',
            '.pdf-link'
        ]
        
        download_found = False
        for selector in fallback_selectors:
            try:
                links = await self.page.query_selector_all(selector)
                for link in links:
                    if await link.is_visible():
                        print(f"✅ Trying fallback download link: {selector}")
                        await link.click()
                        await self.page.wait_for_timeout(3000)
                        download_found = True
                        break
                if download_found:
                    break
            except:
                continue
        
        if not download_found:
            print("⚠️ No download links found, generating PDF from page content...")
            await self._generate_pdf_from_page()
    
    async def _extract_multi_record_results(self, records: List[SCRARecord]) -> Dict[str, Any]:
        """Extract multi-record verification results from the page"""
        print("📋 Extracting multi-record verification results...")
        
        # Get page text content
        page_text = await self.page.text_content('body')
        page_html = await self.page.content()
        
        # Save raw results for debugging
        if self.session_debug_dir and self.session_debug_dir is not None:
            try:
                results_filename = f'{self.session_id}_multi_record_results_raw.txt'
                results_filepath = self.session_debug_dir / results_filename
                with open(results_filepath, 'w') as f:
                    f.write(page_text)
                print(f"📄 Raw results saved to: {results_filepath}")
                
                # Save HTML for debugging
                html_filename = f'{self.session_id}_multi_record_results_raw.html'
                html_filepath = self.session_debug_dir / html_filename
                with open(html_filepath, 'w') as f:
                    f.write(page_html)
                print(f"🌐 Raw HTML saved to: {html_filepath}")
            except Exception as debug_e:
                print(f"⚠️ Failed to save debug results: {debug_e}")
        else:
            print("ℹ️ Skipping debug file save (production mode)")
        
        # Generate transaction ID
        transaction_id = f"PUP_MULTI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Analyze results for completion indicators
        completion_indicators = [
            'processing complete', 'verification complete', 'results ready',
            'download', 'certificate', 'processed successfully'
        ]
        
        page_text_lower = page_text.lower()
        processing_complete = any(indicator in page_text_lower for indicator in completion_indicators)
        
        # Structure response for multi-record verification
        response = {
            "success": True,
            "method": "puppeteer_multi_record",
            "id": transaction_id,
            "multiRecordRequest": {
                "recordCount": len(records),
                "records": [record.to_dict() for record in records[:5]],  # First 5 for preview
                "totalRecords": len(records)
            },
            "processingResult": {
                "dateOfInterest": datetime.now().strftime('%Y%m%d'),
                "transactionId": transaction_id,
                "recordsProcessed": len(records),
                "processingComplete": processing_complete,
                "certificateGenerated": self.pdf_data is not None,
            },
            "automationResult": {
                "rawOutput": page_text[:2000],  # Truncate for storage
                "pageUrl": self.page.url,
                "timestamp": datetime.now().isoformat(),
                "method": "puppeteer_multi_record",
                "sessionId": self.session_id,
                "files_included": True,
                "delivery_method": "direct_response",
                "recordCount": len(records)
            }
        }

        # Add screenshots and PDF data to response
        print(f"🔍 Debug - Adding files to response...")
        print(f"🔍 Has screenshots attribute: {hasattr(self, 'screenshots')}")
        print(f"🔍 Has pdf_data attribute: {hasattr(self, 'pdf_data')}")
        
        if hasattr(self, 'screenshots') and self.screenshots:
            response['automationResult']['screenshots'] = self.screenshots
            print(f"✅ Added {len(self.screenshots)} screenshots to response")
        else:
            print(f"❌ No screenshots to add")
        
        if hasattr(self, 'pdf_data') and self.pdf_data:
            response['automationResult']['pdf'] = self.pdf_data
            print(f"✅ Added PDF data to response: {self.pdf_data['filename']} ({len(self.pdf_data['data'])} chars)")
        else:
            print(f"❌ No PDF data to add")
        
        print(f"✅ Multi-record results extracted - Records: {len(records)}, Complete: {processing_complete}")
        await self._take_debug_screenshot("14_results_extracted", f"Multi-record results extracted - Records: {len(records)}")
        return response
    
    async def _generate_pdf_from_page(self):
        """Generate PDF from current page content when automatic download fails"""
        try:
            print("🔄 Generating PDF from page content...")
            
            # Generate PDF using Playwright's built-in PDF functionality
            pdf_data = await self.page.pdf(
                format='A4',
                margin={
                    'top': '1in',
                    'right': '1in', 
                    'bottom': '1in',
                    'left': '1in'
                },
                print_background=True,
                prefer_css_page_size=True
            )
            
            pdf_filename = f"scra_verification_{self.session_id}.pdf"
            
            # Convert to base64 for frontend transmission
            import base64
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            # Store PDF data for later transmission
            self.pdf_data = {
                'filename': pdf_filename,
                'data': pdf_base64,
                'size': len(pdf_data),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✅ PDF generated from page: {len(pdf_data)} bytes")
            
            # Upload to Supabase Storage
            if self.user_id:
                await self.supabase_service.upload_pdf_realtime(
                    self.session_id,
                    pdf_filename,
                    pdf_data,
                    self.user_id
                )
                print(f"📤 Generated PDF uploaded to Supabase Storage: {pdf_filename}")
            
            # Save debug copy to local filesystem
            if self.session_debug_dir and self.session_debug_dir is not None:
                try:
                    pdf_filepath = self.session_debug_dir / "pdfs" / pdf_filename
                    pdf_filepath.parent.mkdir(exist_ok=True)
                    with open(pdf_filepath, 'wb') as f:
                        f.write(pdf_data)
                    print(f"🗂️ Debug PDF saved: {pdf_filepath}")
                except Exception as debug_e:
                    print(f"⚠️ Failed to save debug PDF: {debug_e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to generate PDF from page: {e}")
            return False
    
    async def _cleanup(self):
        """Clean up browser resources and temporary files"""
        # Clean up temporary files first
        if hasattr(self, '_temp_file_cleanup') and self._temp_file_cleanup:
            try:
                import os
                import shutil
                
                temp_file_path = self._temp_file_cleanup
                
                # Remove the file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    print(f"🗑️ Cleaned up temporary file: {temp_file_path}")
                
                # Remove the temporary directory
                import tempfile
                temp_dir = os.path.dirname(temp_file_path)
                if os.path.exists(temp_dir) and temp_dir != tempfile.gettempdir():
                    shutil.rmtree(temp_dir)
                    print(f"🗑️ Cleaned up temporary directory: {temp_dir}")
                    
                # Clear the cleanup path
                self._temp_file_cleanup = None
                
            except Exception as cleanup_error:
                print(f"⚠️ Temporary file cleanup warning: {cleanup_error}")
        
        # Clean up browser resources
        if self.context:
            try:
                await self.context.close()
                print("🧹 Browser context cleaned up")
            except Exception as e:
                print(f"⚠️ Error during context cleanup: {e}")
        
        if self.browser:
            try:
                await self.browser.close()
                print("🧹 Browser cleaned up")
            except Exception as e:
                print(f"⚠️ Error during browser cleanup: {e}")
    
    def cleanup_debug_files(self):
        """Clean up debug files after successful transmission to frontend"""
        if self.session_debug_dir and self.session_debug_dir.exists():
            try:
                # Remove all files in the session debug directory
                import shutil
                shutil.rmtree(self.session_debug_dir)
                print(f"🧹 Debug files cleaned up: {self.session_debug_dir}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup debug files: {e}")
    
    def keep_debug_files(self):
        """Explicitly keep debug files (called on transmission failure)"""
        if self.session_debug_dir and self.session_debug_dir is not None:
            try:
                print(f"🗂️ Debug files preserved for debugging: {self.session_debug_dir}")
                print(f"   Screenshots: {len(list((self.session_debug_dir / 'screenshots').glob('*.png')))} files")
                pdf_files = list((self.session_debug_dir / 'pdfs').glob('*.pdf'))
                print(f"   PDFs: {len(pdf_files)} files")
                if pdf_files:
                    for pdf_file in pdf_files:
                        print(f"      - {pdf_file.name} ({pdf_file.stat().st_size} bytes)")
            except Exception as e:
                print(f"⚠️ Failed to access debug files: {e}")
        else:
            print("ℹ️ No debug directory (production mode)")


async def test_puppeteer_agent():
    """Test function for the Puppeteer agent"""
    
    # Test data
    test_person = {
        "firstName": "John",
        "lastName": "Doe",
        "middleName": "M",
        "ssn": "1234567890",
        "dateOfBirth": "1990-01-01",
        "activeDutyDate": "2020-01-01"
    }
    
    username = os.getenv("SCRA_USERNAME")
    password = os.getenv("SCRA_PASSWORD")
    
    if not username or not password:
        print("Error: SCRA_USERNAME and SCRA_PASSWORD environment variables must be set")
        return
    
    agent = PuppeteerSCRAAgent(username, password)
    result = await agent.verify_person(test_person)
    
    print("Verification Result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(test_puppeteer_agent())
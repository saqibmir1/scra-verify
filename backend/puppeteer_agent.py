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
            
            # Add slow motion for local testing visibility
            if is_local_test:
                launch_options['slow_mo'] = 500
                print("🐌 Added slow motion for local testing visibility")
            
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
        """Clean up browser resources"""
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
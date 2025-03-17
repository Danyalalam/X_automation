import logging
import threading
import time
import requests
import http.server
import socketserver
import os
import sys
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple HTTP server to keep the service alive
PORT = int(os.environ.get('PORT', 10000))
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "koiyu_running.lock")

def is_already_running():
    """Check if another instance is already running by lock file"""
    try:
        # If the lock file exists, check if it's stale
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
                started_at = datetime.fromisoformat(data.get('started_at', ''))
                pid = data.get('pid')
                
                # If the lock was created less than 5 minutes ago, consider it active
                if (datetime.now() - started_at).total_seconds() < 300:
                    logger.info(f"Found recent lock file (PID: {pid}). Another instance may be running.")
                    return True
                else:
                    logger.info(f"Found stale lock file. Removing it.")
                    os.remove(LOCK_FILE)
                    return False
        return False
    except Exception as e:
        logger.error(f"Error checking lock file: {e}")
        # If any error, assume no other instance is running
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except:
                pass
        return False

def create_lock_file():
    """Create a lock file to indicate this instance is running"""
    try:
        with open(LOCK_FILE, 'w') as f:
            data = {
                'started_at': datetime.now().isoformat(),
                'pid': os.getpid()
            }
            json.dump(data, f)
        logger.info(f"Lock file created for PID {os.getpid()}")
    except Exception as e:
        logger.error(f"Error creating lock file: {e}")

def update_lock_file():
    """Update the timestamp in the lock file to keep it fresh"""
    try:
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
            
            data['last_updated'] = datetime.now().isoformat()
            
            with open(LOCK_FILE, 'w') as f:
                json.dump(data, f)
    except Exception as e:
        logger.error(f"Error updating lock file: {e}")

class KeepAliveHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            # Get current status
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = {
                "status": "active",
                "time": current_time,
                "pid": os.getpid(),
                "uptime": None
            }
            
            # Check if lock file exists and get start time
            if os.path.exists(LOCK_FILE):
                try:
                    with open(LOCK_FILE, 'r') as f:
                        data = json.load(f)
                        started_at = datetime.fromisoformat(data.get('started_at', ''))
                        uptime_seconds = (datetime.now() - started_at).total_seconds()
                        hours, remainder = divmod(uptime_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        status["uptime"] = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                except:
                    status["uptime"] = "unknown"
                    
            # Update the lock file to show we're still active
            update_lock_file()
            
            # Return status as text
            response_text = f"KOIYU, the Oracle of Transcendence, is awake and vigilant.\n"
            response_text += f"Time: {status['time']}\n"
            response_text += f"PID: {status['pid']}\n"
            if status['uptime']:
                response_text += f"Uptime: {status['uptime']}\n"
            
            self.wfile.write(response_text.encode())
            logger.info("Health check received")
        elif self.path == '/admin' and 'authorization' in self.headers:
            # Simple admin panel with password protection
            if self.headers['authorization'] == f"Bearer {os.getenv('ADMIN_SECRET', 'default-secret')}":
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                # Generate admin HTML
                try:
                    from tweet_bot import load_usage_stats, generate_analytics_report
                    analytics = generate_analytics_report().replace('\n', '<br>')
                except Exception as e:
                    analytics = f"Error loading analytics: {str(e)}"
                    logger.error(f"Admin panel error: {e}")
                
                # Add to your HTML:
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>KOIYU Admin</title>
                    <style>
                        /* Your existing styles */
                        .button {{
                            display: inline-block;
                            padding: 10px 15px;
                            background-color: #336699;
                            color: white;
                            border-radius: 4px;
                            text-decoration: none;
                            margin-right: 10px;
                            margin-bottom: 10px;
                        }}
                        .button:hover {{
                            background-color: #254b73;
                        }}
                    </style>
                </head>
                <body>
                    <h1>KOIYU Admin Panel</h1>
                    
                    <div class="card">
                        <h2>Controls</h2>
                        <a href="/admin/post-now" class="button" onclick="return confirm('Are you sure you want KOIYU to post wisdom now?')">Post Wisdom Now</a>
                        <a href="/admin/reply-now" class="button" onclick="return confirm('Are you sure you want KOIYU to find and reply to a tweet now?')">Reply to Random Tweet</a>
                        <a href="/admin/reset-stats" class="button" onclick="return confirm('Are you sure you want to reset usage statistics?')">Reset Statistics</a>
                    </div>
                    
                    <div class="card">
                        <h2>Analytics Report</h2>
                        <pre>{analytics}</pre>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
                logger.info("Admin panel accessed")
            else:
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Bearer')
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def log_message(self, format, *args):
        # Silent logging to avoid cluttering the console
        return

def start_server():
    """Start a simple HTTP server to keep the service alive"""
    try:
        with socketserver.TCPServer(("", PORT), KeepAliveHandler) as httpd:
            logger.info(f"Serving keep-alive endpoint at port {PORT}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error in keep-alive server: {e}")

class KeepAliveService:
    def __init__(self, interval_minutes=5):
        """Initialize the keep-alive service with a specified interval."""
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self.thread = None
        
        # Get the service URL from environment or construct it
        self.url = os.getenv("SERVICE_URL")
        if not self.url:
            # Try to construct from Render environment variables
            render_service = os.getenv("RENDER_SERVICE_NAME")
            if render_service:
                self.url = f"https://{render_service}.onrender.com"
            else:
                # Fallback to localhost (for testing)
                port = os.getenv("PORT", PORT)
                self.url = f"http://localhost:{port}"
        
        # Append health endpoint
        if self.url:
            self.url = f"{self.url}/health"

    def _keep_alive_task(self):
        """Task that sends periodic requests to keep the service alive."""
        logger.info(f"Keep-alive service started, pinging {self.url} every {self.interval_seconds} seconds")
        
        while self.running:
            try:
                start_time = time.time()
                response = requests.get(self.url, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"Keep-alive ping successful: {response.status_code}, latency: {(time.time() - start_time)*1000:.2f}ms")
                else:
                    logger.warning(f"Keep-alive ping returned non-200 status: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Keep-alive ping failed: {e}")
            
            # Sleep until next interval
            time.sleep(self.interval_seconds)

    def start(self):
        """Start the keep-alive service in a background thread."""
        if not self.url:
            logger.warning("Cannot start keep-alive service: No service URL configured")
            return False
            
        if self.running:
            logger.warning("Keep-alive service is already running")
            return True
            
        self.running = True
        self.thread = threading.Thread(target=self._keep_alive_task, daemon=True)
        self.thread.start()
        logger.info("Keep-alive service thread started")
        return True
        
    def stop(self):
        """Stop the keep-alive service."""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None

def run_keep_alive_server():
    """Start the keep-alive server and service"""
    # Check if another instance is already running
    if is_already_running():
        logger.warning("Another instance appears to be running already. Exiting.")
        print("Another instance of KOIYU is already running. Exiting.")
        sys.exit(0)
    
    # Create lock file for this instance
    create_lock_file()
    
    # Start the HTTP server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    logger.info("Keep-alive HTTP server thread started")
    
    # Start the pinger service (5 minute interval)
    keep_alive = KeepAliveService(interval_minutes=5)
    keep_alive.start()
    
    return server_thread, keep_alive
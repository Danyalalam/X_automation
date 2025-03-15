import http.server
import socketserver
import threading
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple HTTP server to keep the service alive
PORT = int(os.environ.get('PORT', 8080))

class KeepAliveHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'KOIYU, the Oracle of Transcendence, is awake and vigilant.')
        logger.info("Health check received")
    
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

# Start the server in a separate thread
def run_keep_alive_server():
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()
    logger.info("Keep-alive server thread started")
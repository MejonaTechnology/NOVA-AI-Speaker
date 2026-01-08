"""
Fire TV Bridge Service for NOVA AI
Runs locally on your home network to bridge OCI backend to Fire TV via ADB

Usage:
    python firestick_bridge.py

The bridge exposes HTTP endpoints that the OCI backend calls to control Fire TV.
"""

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from firestick_controller import firestick_controller, execute_firestick_command

# Configuration
BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", 8585))
API_KEY = os.environ.get("FIRESTICK_BRIDGE_KEY", "nova-firestick-2024")  # Change this!

print(f"""
╔══════════════════════════════════════════════════════════════╗
║          🔥 NOVA Fire TV Bridge Service 🔥                  ║
╠══════════════════════════════════════════════════════════════╣
║  Port: {BRIDGE_PORT}                                                   ║
║  Fire TV IP: {firestick_controller.firestick_ip}                          ║
╚══════════════════════════════════════════════════════════════╝
""")


class BridgeHandler(BaseHTTPRequestHandler):
    """Handle incoming HTTP requests from OCI backend"""
    
    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[BRIDGE] {args[0]}")
    
    def send_json(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def check_auth(self):
        """Check API key authentication"""
        api_key = self.headers.get("X-API-Key", "")
        if api_key != API_KEY:
            self.send_json(401, {"error": "Invalid API key"})
            return False
        return True
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key")
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/ping":
            # Health check - no auth required
            self.send_json(200, {"status": "ok", "service": "firestick-bridge"})
        
        elif self.path == "/status":
            if not self.check_auth():
                return
            # Check Fire TV connection status
            connected = firestick_controller.connect()
            self.send_json(200, {
                "connected": connected,
                "firestick_ip": firestick_controller.firestick_ip,
                "firestick_port": firestick_controller.adb_port
            })
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path == "/command":
            if not self.check_auth():
                return
            
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            
            try:
                data = json.loads(body)
                command = data.get("command", "").lower().strip()
                
                if not command:
                    self.send_json(400, {"error": "Missing 'command' field"})
                    return
                
                print(f"[BRIDGE] Executing command: {command}")
                
                # Execute the command
                success = execute_firestick_command(command)
                
                if success:
                    print(f"[BRIDGE] ✅ Command '{command}' executed successfully")
                    self.send_json(200, {"status": "success", "command": command})
                else:
                    print(f"[BRIDGE] ❌ Command '{command}' failed")
                    self.send_json(500, {"status": "failed", "command": command})
                    
            except json.JSONDecodeError:
                self.send_json(400, {"error": "Invalid JSON"})
            except Exception as e:
                print(f"[BRIDGE] Error: {e}")
                self.send_json(500, {"error": str(e)})
        
        else:
            self.send_json(404, {"error": "Not found"})


def run_bridge():
    """Start the bridge HTTP server"""
    server = HTTPServer(("0.0.0.0", BRIDGE_PORT), BridgeHandler)
    print(f"[BRIDGE] Starting server on port {BRIDGE_PORT}...")
    print(f"[BRIDGE] API Key: {API_KEY[:4]}...{API_KEY[-4:]}")
    print(f"[BRIDGE] Endpoints:")
    print(f"         GET  /ping    - Health check")
    print(f"         GET  /status  - Fire TV connection status")
    print(f"         POST /command - Execute Fire TV command")
    print(f"\n[BRIDGE] Ready! Waiting for commands from OCI backend...\n")
    
    # Test Fire TV connection on startup
    print("[BRIDGE] Testing Fire TV connection...")
    if firestick_controller.connect():
        print("[BRIDGE] ✅ Fire TV connected successfully!")
    else:
        print("[BRIDGE] ⚠️  Could not connect to Fire TV. Commands will retry on demand.")
    
    print("\n" + "="*60)
    print("Press Ctrl+C to stop the bridge")
    print("="*60 + "\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Shutting down...")
        firestick_controller.disconnect()
        server.shutdown()


if __name__ == "__main__":
    run_bridge()

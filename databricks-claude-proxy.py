from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests
from requests.auth import HTTPBasicAuth
import os
import argparse
from dotenv import load_dotenv

# Parse command line arguments
parser = argparse.ArgumentParser(description='Databricks Claude Proxy Server')
parser.add_argument('--debug', action='store_true', help='Enable debug mode to print incoming requests')
parser.add_argument('--port', type=int, default=8800, help='Port to run the proxy server on (overrides PROXY_PORT env variable)')
args = parser.parse_args()

# Load environment variables from .env file
load_dotenv()

# Configuration from environment variables
DATABRICKS_HOST = os.getenv('DATABRICKS_HOST', "https://adb-7891337736584897.17.azuredatabricks.net")

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the request from the client
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # Print request details if debug mode is enabled
        if args.debug:
            print(f"\n--- Incoming Request ---")
            print(f"URI: {self.path}")
            print(f"Headers: {self.headers}")
            print(f"Payload: {post_data.decode('utf-8')}")
            print("----------------------\n")

        try:
            claude_payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Invalid JSON payload")
            return

        # 2. Transform the request for Databricks
        databricks_payload = self.transform_request(claude_payload)
        # 3. Forward the request to Databricks
        serving_endpoint = claude_payload["model"]
        databricks_url = f"{DATABRICKS_HOST}/serving-endpoints/{serving_endpoint}/invocations"
        databricks_token = self.headers["authorization"].split()[1]

        try:
            response = requests.post(
                databricks_url,
                headers={
                    "Content-Type": "application/json",
                },
                auth=HTTPBasicAuth("token", databricks_token),
                json=databricks_payload,
                stream=True  # Enable streaming mode
            )
            response.raise_for_status() # Check for HTTP errors like 4xx/5xx

            # Check if the response content type indicates a stream
            content_type = response.headers.get('Content-Type', '')
            if 'event-stream' not in content_type:
                # If not a stream, read the whole response and send it back
                self.send_response(response.status_code)
                for header, value in response.headers.items():
                     # Avoid forwarding chunked encoding header as the server will handle it
                    if header.lower() != 'transfer-encoding':
                        self.send_header(header, value)
                self.end_headers()
                self.wfile.write(response.content)
                return

            # --- Handle SSE stream ---
            self.send_response(200) # Assuming success if streaming starts
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            # Potentially forward other relevant headers from Databricks response?
            self.end_headers()

            # Stream the Databricks response back to the client chunk by chunk
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    self.wfile.write(chunk)
                    # Flush the buffer to ensure data is sent immediately (important for streaming)
                    self.wfile.flush()

        except requests.exceptions.RequestException as e:
            # Try to get error details from response if available
            error_message = f"Error communicating with Databricks: {e}"
            try:
                # If the request failed but we got a response object
                if 'response' in locals() and response is not None:
                     error_detail = response.text
                     error_message += f"\nDatabricks Response: {error_detail}"
                     self.send_response(response.status_code)
                else:
                     self.send_response(502) # Bad Gateway

            except Exception: # Fallback if reading response fails
                 self.send_response(502) # Bad Gateway

            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(error_message.encode('utf-8'))
            print(f"Error: {error_message}") # Log the error server-side too
            return
        except Exception as e: # Catch unexpected errors during streaming/writing
             print(f"Unexpected error during streaming: {e}")
             # If headers haven't been sent, send an error response
             if not self.headers_sent:
                 self.send_response(500)
                 self.send_header('Content-type', 'text/plain')
                 self.end_headers()
                 self.wfile.write(f"Internal Server Error: {e}".encode('utf-8'))
             # Otherwise, we can't send a new status code, just log it. The connection might be broken.
             return

    def transform_request(self, claude_payload):
        # Example: Remove a field not supported by Databricks
        # This field caused issues with the Databricks endpoint
        if "stream_options" in claude_payload:
             del claude_payload["stream_options"]
        # Add any other necessary transformations here
        return claude_payload

if __name__ == '__main__':
    server_address = ('', args.port)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"Starting Databricks Claude proxy server on port {args.port}")
    if args.debug:
        print("Debug mode enabled - all incoming requests will be printed")
    httpd.serve_forever()

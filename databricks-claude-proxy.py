from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import requests
import os

# Configuration
DATABRICKS_HOST = "<YOUR_DATABRICKS_HOST>"  # e.g., "https://your-workspace.cloud.databricks.com"
DATABRICKS_TOKEN = "<YOUR_DATABRICKS_TOKEN>"
SERVING_ENDPOINT = "<YOUR_SERVING_ENDPOINT_NAME>"
PROXY_PORT = 8000

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the request from the client
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
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
        databricks_url = f"{DATABRICKS_HOST}/serving-endpoints/{SERVING_ENDPOINT}/invocations"
        
        try:
            response = requests.post(
                databricks_url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
                    "Accept": "text/event-stream",
                },
                json=databricks_payload,
                stream=True
            )
            response.raise_for_status()

            # Set headers for SSE streaming
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()

            # Stream the Databricks response back to the client
            for line in response.iter_lines():
                if line:
                    self.wfile.write(line + b'\n')

        except requests.exceptions.RequestException as e:
            self.send_response(502)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error communicating with Databricks: {e}".encode('utf-8'))
            return

    def transform_request(self, claude_payload):
        """
        Transform Claude API format to Databricks format
        Claude format:
        {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        Databricks format:
        {
            "dataframe_records": [
                {
                    "messages": [...],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
            ]
        }
        """
        # Extract the parameters from Claude payload
        messages = claude_payload.get("messages", [])
        max_tokens = claude_payload.get("max_tokens", 1000)
        temperature = claude_payload.get("temperature", 0.7)

        # Create the Databricks format
        databricks_payload = {
            "dataframe_records": [{
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }]
        }

        return databricks_payload

if __name__ == '__main__':
    server_address = ('', PROXY_PORT)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"Starting Databricks Claude proxy server on port {PROXY_PORT}")
    httpd.serve_forever() 
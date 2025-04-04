from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import requests
import re

from dotenv import load_dotenv

load_dotenv()

#Azure OpenAI Configuration
AZURE_API_ENDPOINT = os.getenv("AZURE_API_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION")
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
PROXY_PORT = int(os.getenv("OPENAI_PROXY_PORT"))

class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the request from Zed
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            zed_payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Invalid JSON from Zed")
            return

        # 2. Transform the request for Azure OpenAI
        azure_payload = self.transform_request(zed_payload)

        # 3. Forward the request to Azure OpenAI (streaming)
        azure_url = f"{AZURE_API_ENDPOINT}/chat/completions?api-version={AZURE_API_VERSION}"

        try:
            response = requests.post(
                azure_url,
                headers={
                    "Content-Type": "application/json",
                    "api-key": AZURE_API_KEY,
                    "Accept": "text/event-stream",  # Important: request SSE
                    "user-agent": "Zed/0.178.5"
                },
                json=azure_payload,
                stream=True  # Enable streaming
            )
            response.raise_for_status()

            # Set headers for SSE streaming to Zed
            self.send_response(200)
            self.send_header('Content-type', 'text/event-stream')  #Important for SSE.
            self.send_header('Cache-Control', 'no-cache')  # Disable caching
            self.end_headers()

            # Directly stream the Azure OpenAI response to Zed
            for line in response.iter_lines():
                if line:
                    self.wfile.write(line + b'\n')  # Add newline for SSE

        except requests.exceptions.RequestException as e:
            self.send_response(502)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error communicating with Azure OpenAI: {e}".encode('utf-8'))
            return

    def transform_request(self, zed_payload):
        # Define your system prompt.
        # ********************************************************************
        # *** THIS IS NECESSARY TO HAVE CODE HIGHLIGHTING IN THE RESPONSES ***
        # ********************************************************************
        system_message = {
            "role": "system",
            "content": "You must always respond in markdown format."
        }

        if 'prompt' in zed_payload:
            # Build the messages array so that system prompt comes first.
            messages = [
                system_message,
                {"role": "user", "content": zed_payload['prompt']}
            ]
            azure_payload = {
                "messages": messages,
                "temperature": zed_payload.get("temperature", 0.7),
                "max_tokens": zed_payload.get("max_tokens", 200),
                "stream": True
            }
            zed_payload.pop("prompt")
            # If there are extra parameters in zed_payload, update them now.
            azure_payload.update(zed_payload)
        else:
            azure_payload = zed_payload
            azure_payload["stream"] = True
            # Optionally add system message if not included already.
            if "messages" in azure_payload:
                azure_payload["messages"] = [system_message] + azure_payload["messages"]
            else:
                azure_payload["messages"] = [system_message]
        return azure_payload


if __name__ == '__main__':
    server_address = ('', PROXY_PORT)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"Starting Azure OpenAI proxy server on port {PROXY_PORT}")
    httpd.serve_forever()
from flask import Flask, request, jsonify
import requests
import time
import uuid
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Environment variables
DATABRICKS_BASE_URL = os.getenv("DATABRICKS_BASE_URL", "https://<your-databricks-workspace>.cloud.databricks.com")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")  # Optional separate token

if not DATABRICKS_BASE_URL:
    raise ValueError("DATABRICKS_BASE_URL must be set in environment variables")

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        # Extract API token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({
                "error": {
                    "message": "Missing or invalid Authorization header",
                    "type": "invalid_request_error"
                }
            }), 401
        token = auth_header.split(" ")[1]
        # Use Databricks token if provided, else fall back to OpenAI token
        auth_token = DATABRICKS_TOKEN if DATABRICKS_TOKEN else token

        data = request.json
        model_name = data.get("model")
        if not model_name:
            return jsonify({
                "error": {
                    "message": "Model name not specified in request body",
                    "type": "invalid_request_error"
                }
            }), 400

        # Construct Databricks request
        databricks_url = f"{DATABRICKS_BASE_URL}/serving-endpoints/{model_name}/invocations"
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        payload = {k: v for k, v in data.items() if k != "model"}

        app.logger.info(f"Forwarding request to Databricks: {databricks_url}")
        response = requests.post(databricks_url, json=payload, headers=headers)

        if response.status_code == 200:
            databricks_data = response.json()
            # Explicitly transform response to OpenAI format
            choices = databricks_data.get("choices", [{"text": databricks_data.get("text", "")}])
            openai_choices = [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": choice.get("text", "")},
                    "finish_reason": "stop"
                } for choice in choices
            ]
            openai_data = {
                "id": f"chatcmpl-{uuid.uuid4()}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_name,
                "choices": openai_choices,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}  # Placeholder
            }
            return jsonify(openai_data), 200
        else:
            try:
                error_data = response.json()
                error_message = error_data.get("message", "Unknown error from Databricks")
            except ValueError:
                error_message = "Invalid response from Databricks"
            return jsonify({
                "error": {
                    "message": error_message,
                    "type": "server_error" if response.status_code >= 500 else "invalid_request_error"
                }
            }), response.status_code

    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify({
            "error": {
                "message": "Internal server error",
                "type": "server_error"
            }
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)  # No SSL for simplicity; add if needed

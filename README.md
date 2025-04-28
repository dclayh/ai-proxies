Repo containing various scripts for connecting coding tools to AI models via local proxy servers.

# `databricks-claude-proxy.py`

To use this proxy, run
`poetry install`
`poetry run python databricks-claude-proxy.py`

Optionally add the `--debug` flag to see all incoming requests, and `--port` to set the serving port (default 8800).

In your IDE tool of choice, select the "OpenAI Compatible" option.
Put `http://localhost:<port>` as the base URL, your Databricks PAT as the API key,
and `databricks-claude-3-7-sonnet` (or whatever other Databricks model you want) as the model ID.
Et voilà!
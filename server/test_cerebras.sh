#!/bin/bash

# Start server in background
PYTHONPATH=. .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

echo "Waiting for server to start..."
sleep 5

echo "--- Health Check ---"
curl -s http://localhost:8000/moca/health | grep -i cerebras

echo -e "\n\n--- Ask Request ---"
curl -s -X POST http://localhost:8000/moca/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Who are you?", "session_id": "test-cerebras-001"}'

echo -e "\n\n--- Stopping server ---"
kill $SERVER_PID

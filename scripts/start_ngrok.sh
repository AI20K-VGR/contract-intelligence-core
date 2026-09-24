#!/bin/bash
echo "Starting Ngrok tunnels for FastAPI (8000) and Keycloak (8080)..."
ngrok start --all --config=ngrok.yml

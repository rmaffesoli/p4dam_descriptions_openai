#!/bin/bash

# Stop and remove the existing container if it exists
echo "Stopping existing container if any"
docker stop openai-descriptions-webhook || true
docker rm openai-descriptions-webhook || true

echo "Starting new container"
# Start the new container
docker run -d \
  --name openai-descriptions-webhook \
  --restart unless-stopped \
  -p 8800:8800 \
  -e DAM_SERVER_ADDRESS="http://10.0.0.1" \ # Change this to the private IP address of DAM
  -e DAM_ACCOUNT_KEY="your_account_key_here" \
  -e OPENAI_API_KEY="your_api_key_here" \
  -e P4PORT="your_p4_port_here" \
  -e P4USER="your_p4_user_here"
  openai-descriptions-webhook

echo "Container started"
echo "You can tail logs with this command: docker logs -f openai-descriptions-webhook"
#!/bin/bash

echo "Starting deployment..."

# Navigate to project directory (Adjust this path on VPS)
cd /root/SSCHelp

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart services (Assuming we use systemd)
systemctl restart discord-bot
systemctl restart discord-manager

echo "Deployment complete!"

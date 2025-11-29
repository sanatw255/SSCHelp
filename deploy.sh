#!/bin/bash

echo "Starting deployment..."

# Navigate to project directory (Adjust this path on VPS)
cd /root/SSCHelp

# Pull latest changes
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart services using PM2
pm2 restart ecosystem.config.js --update-env

echo "Deployment complete!"

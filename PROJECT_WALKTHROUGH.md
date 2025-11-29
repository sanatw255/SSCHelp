# Project Walkthrough: Discord Scheduler Bot

## Accomplishments

We successfully set up a complete CI/CD pipeline for your Discord Bot ecosystem.

### 1. Source Control (GitHub)

- **Repository:** [https://github.com/sanatw255/SSCHelp](https://github.com/sanatw255/SSCHelp)
- **Structure:**
  - `main.py`: The core scheduler (User Bot).
  - `bot.py`: The management interface (Discord Bot).
  - `webhook_server.py`: Listens for GitHub updates.
  - `ecosystem.config.js`: PM2 configuration.
  - `deploy.sh`: Auto-update script.

### 2. VPS Deployment

- **Server:** 45.137.70.56
- **Process Manager:** PM2
- **Processes:**
  - `ssch-scheduler`: Runs `main.py`
  - `ssch-manager`: Runs `bot.py`
  - `ssch-webhook`: Runs `webhook_server.py`

### 3. Auto-Deployment Workflow

1.  **Push:** You push code to GitHub (`git push origin main`).
2.  **Trigger:** GitHub sends a webhook to your VPS.
3.  **Update:** `ssch-webhook` receives the signal and runs `deploy.sh`.
4.  **Deploy:** `deploy.sh` pulls the code, installs requirements, and restarts the bots via PM2.

## How to Manage

- **Check Status:** `pm2 list`
- **View Logs:** `pm2 logs`
- **Manual Restart:** `pm2 restart ecosystem.config.js`

## Next Steps

- You can now develop locally in VS Code.
- Simply commit and push changes to update the live bot!

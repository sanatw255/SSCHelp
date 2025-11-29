# Discord Scheduler Bot

## Overview

This project consists of two distinct components that work together to manage Discord channel permissions and economy features:

1.  **Scheduler (`main.py`)**: The core "worker" script. It uses a **User Token** to automate actions like locking/unlocking channels, distributing cash, and sending messages. It mimics a real client.
2.  **Manager Bot (`bot.py`)**: A standard Discord Bot (Slash Commands) used to manage the configuration file (`config.json`) easily from within Discord.

## Prerequisites

- Python 3.8 or higher
- A Discord Account (for the User Token)
- A Discord Bot Application (for the Bot Token)

## Installation

### 1. Set up the Environment

Open your terminal in the project folder and run the following commands:

**Create a Virtual Environment:**

```powershell
python -m venv venv
```

**Activate the Virtual Environment:**

```powershell
.\venv\Scripts\activate
```

- _Note:_ If you see an error about scripts being disabled, run this command:
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Install Dependencies:**

```powershell
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Create a file named `.env` in the root directory and add your credentials:

```env
TOKEN=your_user_account_token
BOT_TOKEN=your_bot_application_token
ADMIN_IDS=your_discord_user_id
```

- **TOKEN**: The token of the user account that will perform the actions (locking channels, etc.).
- **BOT_TOKEN**: The token from the Discord Developer Portal for the management bot.
- **ADMIN_IDS**: Your Discord User ID (allows you to use the slash commands).

## Usage

### Running the Scheduler (Required)

This script must be running for any automation to happen.

```powershell
python main.py
```

- It checks for tasks every minute.
- It handles channel locking, unlocking, and auto-cash distribution.

### Running the Manager Bot (Optional)

Run this in a **separate terminal** if you want to manage tasks via Discord commands.

```powershell
python bot.py
```

## Features & Commands (Manager Bot)

- `/tasks`: List all currently scheduled tasks.
- `/add-lock-task`: Schedule a new channel lock event.
- `/add-unlock-task`: Schedule a new channel unlock event.
- `/update-task-time`: Change the time of an existing task.
- `/autocash-config`: Configure the daily auto-cash distribution.
- `/set-opening-message`: Set the message sent when a channel unlocks.

## Important Note

**Self-Botting Policy**: This project uses a User Token (`main.py`) to automate actions. Automating user accounts ("self-botting") is technically a violation of Discord's Terms of Service. This script attempts to mimic a real client (using specific headers and user agents), but **use it at your own risk**.

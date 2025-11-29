module.exports = {
  apps: [
    {
      name: "ssch-scheduler",
      script: "main.py",
      interpreter: "venv/bin/python", // Use the virtual env python
      autorestart: true,
      watch: false,
    },
    {
      name: "ssch-manager",
      script: "bot.py",
      interpreter: "venv/bin/python",
      autorestart: true,
      watch: false,
    },
    {
      name: "ssch-webhook",
      script: "webhook_server.py",
      interpreter: "venv/bin/python",
      autorestart: true,
      watch: false,
    },
  ],
};

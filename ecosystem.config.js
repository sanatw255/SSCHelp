module.exports = {
  apps: [
    {
      name: "ssc-scheduler",
      script: "main.py",
      interpreter: "venv/bin/python", // Use the virtual env python
      autorestart: true,
      watch: false,
    },
    {
      name: "ssc-manager",
      script: "bot.py",
      interpreter: "venv/bin/python",
      autorestart: true,
      watch: false,
    },
    {
      name: "ssc-webhook",
      script: "webhook_server.py",
      interpreter: "venv/bin/python",
      autorestart: true,
      watch: false,
    },
  ],
};

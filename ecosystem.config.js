module.exports = {
  apps: [
    {
      name: 'yeirin-ai',
      script: '.venv/bin/uvicorn',
      args: 'yeirin_ai.main:app --host 0.0.0.0 --port 8001',
      interpreter: 'none',
      cwd: '/home/ec2-user/app/yeirin-ai',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        PATH: '/home/ec2-user/.local/bin:/usr/local/bin:/usr/bin:/bin',
      },
    },
  ],
};

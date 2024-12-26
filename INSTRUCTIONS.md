# Monarch Agents Automation Setup Guide

This guide explains how to set up and manage the Monarch Agents automation on an EC2 instance.

## Initial Setup on EC2

1. **Connect to EC2**
```bash
ssh ec2-user@your-ec2-ip
```

2. **Setup Project**
```bash
# Clone repository
cd ~
git clone your-repo monarch-agents
cd monarch-agents

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
nano .env  # Edit with your actual values
```

3. **Setup Log Directory**
```bash
mkdir -p ~/logs
```

## Setting up Cron Job

1. **Prepare the Automation Script**
```bash
# Make script executable
chmod +x ~/monarch-agents/run_automation.sh

# Test run the script manually
cd ~/monarch-agents
./run_automation.sh
```

2. **Configure Cron Job**
```bash
# Edit crontab
crontab -e

# Add this line (runs every 6 hours)
0 */6 * * * /home/ec2-user/monarch-agents/run_automation.sh >> /home/ec2-user/logs/automation.log 2>&1
```

3. **Verify Cron Setup**
```bash
# Check if cron daemon is running
sudo systemctl status crond

# View your cron jobs
crontab -l
```

## Watching Logs

1. **Monitor Cron System Logs**
```bash
# View cron system logs
tail -f /var/log/cron
```

2. **Monitor Application Logs**
```bash
# View application output
tail -f ~/logs/automation.log
```

3. **Monitor Both Logs (using tmux)**
```bash
# Install tmux if not installed
sudo yum install tmux

# Start new session
tmux new -s monitor

# Split window
Ctrl+b %

# In left pane:
tail -f /var/log/cron

# Switch to right pane (Ctrl+b arrow-right)
tail -f ~/logs/automation.log

# Detach from session: Ctrl+b d
# Reattach to session: tmux attach -t monitor
```

## Starting / Stopping the Cron Job

1. **Temporarily Stop Cron Jobs**
```bash
# Comment out the job in crontab
crontab -e
# Add # at the start of the line
```

2. **Permanently Remove Cron Job**
```bash
# Remove the line from crontab
crontab -e
```

3. **Change Schedule**
```bash
crontab -e

# Common schedules:
# Every minute (for testing)
* * * * * /home/ec2-user/monarch-agents/run_automation.sh >> /home/ec2-user/logs/automation.log 2>&1

# Every 5 minutes (for testing)
*/5 * * * * /home/ec2-user/monarch-agents/run_automation.sh >> /home/ec2-user/logs/automation.log 2>&1

# Every 6 hours (production)
0 */6 * * * /home/ec2-user/monarch-agents/run_automation.sh >> /home/ec2-user/logs/automation.log 2>&1
```

## Troubleshooting

1. **Check Script Permissions**
```bash
ls -l ~/monarch-agents/run_automation.sh
# Should show: -rwxr-xr-x
```

2. **Check Log Permissions**
```bash
ls -l ~/logs
# Create if missing: mkdir -p ~/logs
# Fix permissions: chmod 755 ~/logs
```

3. **Verify Python Environment**
```bash
# Activate venv manually and test
cd ~/monarch-agents
source venv/bin/activate
python main.py
```

4. **Common Issues**
- If script not found: Verify paths in crontab match your actual directory structure
- If venv not found: Ensure venv is created and paths in run_automation.sh are correct
- If logs not writing: Check permissions on log directory and file
- If no notifications: Check .env configuration for Telegram tokens

## Maintenance

1. **Updating the Code**
```bash
cd ~/monarch-agents
git pull
source venv/bin/activate
pip install -r requirements.txt
```

2. **Rotating Logs**
```bash
# Manually rotate logs if they get too large
cd ~/logs
mv automation.log automation.log.old
gzip automation.log.old
```

3. **Backup Cron Configuration**
```bash
crontab -l > ~/crontab-backup.txt
```

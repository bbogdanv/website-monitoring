FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY targets.yml ./

# Create directories for data persistence
RUN mkdir -p /app/data

# Make monitor.py executable
RUN chmod +x monitor.py

# Create cron job script with full PATH
# Note: .env file will be mounted at runtime, python-dotenv will load it
RUN printf '#!/bin/bash\nPATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin\nexport PATH\ncd /app\nflock -n /tmp/mini-monitor.lock bash -c "/usr/local/bin/python3 monitor.py" >> /app/data/monitor.log 2>&1\n' > /app/run-monitor.sh && \
    chmod +x /app/run-monitor.sh

# Create cron job with environment variables
# Note: cron doesn't inherit environment, so we need to pass them via the script
RUN echo "* * * * * /app/run-monitor.sh" | crontab -

# Create daily reminder script
RUN printf '#!/bin/bash\nPATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin\nexport PATH\ncd /app\n/usr/local/bin/python3 daily_reminder.py >> /app/data/reminder.log 2>&1\n' > /app/run-reminder.sh && \
    chmod +x /app/run-reminder.sh

# Add daily reminder cron jobs (12:00 and 18:00)
RUN (crontab -l 2>/dev/null; echo "0 12 * * * /app/run-reminder.sh") | crontab -
RUN (crontab -l 2>/dev/null; echo "0 18 * * * /app/run-reminder.sh") | crontab -

# Set environment variables
ENV CONFIG_PATH=/app/targets.yml
ENV DB_PATH=/app/data/monitor.db
ENV PYTHONUNBUFFERED=1

# Volume for persistent data
VOLUME ["/app/data"]

# Default command: start cron in foreground
CMD ["cron", "-f"]


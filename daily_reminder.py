#!/usr/bin/env python3
"""Daily reminder script for DOWN sites."""
import os
import sys
from dotenv import load_dotenv
from config import Config
from db import Database
from alerts import AlertManager


def main():
    """Send daily reminder about DOWN sites."""
    # Load environment variables
    env_path = '/app/.env' if os.path.exists('/app/.env') else '.env'
    load_dotenv(env_path)
    
    # Load configuration
    config_path = os.getenv('CONFIG_PATH', '/app/targets.yml')
    try:
        config = Config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize database
    db_path = os.getenv('DB_PATH', '/app/data/monitor.db')
    if not os.path.isabs(db_path):
        db_path = os.path.join('/app/data', db_path)
    
    db = Database(db_path)
    
    # Create alert manager
    alert_manager = AlertManager(db, config)
    
    # Send reminder
    alert_manager.send_daily_reminder()
    
    db.close()


if __name__ == '__main__':
    main()


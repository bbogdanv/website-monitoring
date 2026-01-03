"""Telegram bot for status queries."""
import os
import sys
import time
import requests
from typing import Optional
from dotenv import load_dotenv
from config import Config
from db import Database


class TelegramBot:
    """Telegram bot for handling commands."""
    
    def __init__(self, bot_token: str, db: Database, config: Config):
        """Initialize Telegram bot."""
        self.bot_token = bot_token
        self.db = db
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.last_update_id = 0
    
    def get_updates(self) -> list:
        """Get new updates from Telegram."""
        url = f"{self.base_url}/getUpdates"
        params = {
            'offset': self.last_update_id + 1,
            'timeout': 10,
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            result = response.json()
            
            if result.get('ok'):
                return result.get('result', [])
            return []
        except Exception as e:
            print(f"Error getting updates: {e}", file=sys.stderr)
            return []
    
    def send_message(self, chat_id: str, text: str) -> bool:
        """Send message to chat."""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('ok', False)
        except Exception as e:
            print(f"Error sending message: {e}", file=sys.stderr)
            return False
    
    def get_status_message(self) -> str:
        """Get current status of all sites."""
        # Get latest check for each page
        statuses = []
        
        for page in self.config.pages:
            last_check = self.db.get_last_check(page.target_id)
            
            if last_check:
                # Determine emoji based on state
                if last_check.state == 'OK':
                    emoji = '🟢'
                elif last_check.state == 'SLOW':
                    emoji = '🟠'
                else:
                    emoji = '🔴'
                
                # Build status line: emoji + URL + HTTP + TTFB + Total + Error
                status_line = f"{emoji} {last_check.url}"
                
                if last_check.http_code:
                    status_line += f" HTTP: {last_check.http_code}"
                
                if last_check.ttfb is not None:
                    status_line += f" TTFB: {last_check.ttfb:.3f}s"
                
                if last_check.total is not None:
                    status_line += f" Total: {last_check.total:.3f}s"
                
                if last_check.error:
                    status_line += f" Error: {last_check.error}"
                
                statuses.append(status_line)
            else:
                # No check yet
                statuses.append(f"⚪ {page.url} Не проверялся")
        
        # Build message
        message = "📊 <b>Статус мониторинга</b>\n\n"
        message += "\n".join(statuses)
        
        # Add summary
        if statuses:
            ok_count = sum(1 for s in statuses if '🟢' in s)
            slow_count = sum(1 for s in statuses if '🟠' in s)
            down_count = sum(1 for s in statuses if '🔴' in s)
            
            message += f"\n\n<b>Итого:</b> 🟢 {ok_count} | 🟠 {slow_count} | 🔴 {down_count}"
        
        return message
    
    def process_updates(self):
        """Process incoming updates."""
        updates = self.get_updates()
        
        for update in updates:
            self.last_update_id = update.get('update_id', 0)
            
            if 'message' in update:
                message = update['message']
                chat_id = str(message['chat']['id'])
                text = message.get('text', '')
                
                if text.startswith('/check'):
                    status_msg = self.get_status_message()
                    self.send_message(chat_id, status_msg)
                elif text.startswith('/start') or text.startswith('/help'):
                    help_msg = (
                        "🤖 <b>Website Monitoring Bot</b>\n\n"
                        "Доступные команды:\n"
                        "/check - показать текущий статус всех сайтов\n"
                        "/help - показать эту справку"
                    )
                    self.send_message(chat_id, help_msg)
    
    def run(self):
        """Run bot in polling mode."""
        print("Telegram bot started. Waiting for commands...")
        
        while True:
            try:
                self.process_updates()
                time.sleep(1)  # Small delay to avoid rate limiting
            except KeyboardInterrupt:
                print("\nBot stopped.")
                break
            except Exception as e:
                print(f"Error in bot loop: {e}", file=sys.stderr)
                time.sleep(5)


def main():
    """Main entry point for bot."""
    # Load environment variables
    env_path = '/app/.env' if os.path.exists('/app/.env') else '.env'
    load_dotenv(env_path)
    
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("ERROR: BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    
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
    
    # Create and run bot
    bot = TelegramBot(bot_token, db, config)
    bot.run()


if __name__ == '__main__':
    main()


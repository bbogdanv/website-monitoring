"""Alerting system with Telegram notifications and anti-spam logic."""
import os
import sys
import time
import requests
from typing import Optional
from config import AlertProfile, Config
from db import AlertState, Database


class AlertManager:
    """Manages alerts with anti-spam and hysteresis logic."""
    
    def __init__(self, db: Database, config: Optional[Config] = None):
        """Initialize alert manager."""
        self.db = db
        self.config = config
        self.bot_token = os.getenv('BOT_TOKEN')
        self.chat_id = os.getenv('CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            print("WARNING: BOT_TOKEN or CHAT_ID not set. Alerts will not be sent.")
    
    def process_check_result(
        self,
        target_id: str,
        new_state: str,
        alert_profile: AlertProfile,
        metrics: Optional[dict] = None,
    ) -> bool:
        """
        Process check result and send alert if needed.
        
        Returns:
            True if alert was sent, False otherwise.
        """
        now = time.time()
        current_state = self.db.get_alert_state(target_id)
        
        if not current_state:
            # First check - initialize state
            is_bad = new_state in ('SLOW', 'DOWN')
            self.db.update_alert_state(
                target_id=target_id,
                new_state=new_state,
                bad_since_ts=now if is_bad else None,
                consecutive_failures=1 if is_bad else 0,
                consecutive_successes=0 if is_bad else 1,
            )
            return False
        
        # Update consecutive counters
        is_bad = new_state in ('SLOW', 'DOWN')
        is_good = new_state == 'OK'
        
        if is_bad:
            new_failures = current_state.consecutive_failures + 1
            new_successes = 0
        elif is_good:
            new_failures = 0
            new_successes = current_state.consecutive_successes + 1
        else:
            new_failures = current_state.consecutive_failures
            new_successes = current_state.consecutive_successes
        
        # Determine if we should send alert
        should_alert = False
        alert_type = None
        
        old_state = current_state.last_state
        
        # State transition: OK -> SLOW/DOWN
        if old_state == 'OK' and new_state in ('SLOW', 'DOWN'):
            if new_failures >= alert_profile.fail_count_to_alert:
                should_alert = True
                alert_type = 'DOWN' if new_state == 'DOWN' else 'SLOW'
        
        # State transition: SLOW/DOWN -> OK
        elif old_state in ('SLOW', 'DOWN') and new_state == 'OK':
            if new_successes >= alert_profile.recover_count:
                should_alert = True
                alert_type = 'RECOVERED'
        
        # State transition: SLOW -> DOWN
        elif old_state == 'SLOW' and new_state == 'DOWN':
            if new_failures >= alert_profile.fail_count_to_alert:
                should_alert = True
                alert_type = 'DOWN'
        
        # State transition: DOWN -> SLOW
        elif old_state == 'DOWN' and new_state == 'SLOW':
            # SLOW is still a problem, but notify about change
            should_alert = True
            alert_type = 'SLOW'
        
        # First alert for persistent problem (page was DOWN from the start)
        elif new_state in ('SLOW', 'DOWN') and old_state in ('SLOW', 'DOWN'):
            # Only send if never sent before and have enough failures
            if new_failures >= alert_profile.fail_count_to_alert and not current_state.last_sent_ts:
                should_alert = True
                alert_type = 'DOWN' if new_state == 'DOWN' else 'SLOW'
        
        # Send alert if needed
        if should_alert:
            success = self._send_alert(target_id, alert_type, new_state, metrics)
            
            bad_since = current_state.bad_since_ts
            if new_state in ('SLOW', 'DOWN') and not bad_since:
                bad_since = now
            
            self.db.update_alert_state(
                target_id=target_id,
                new_state=new_state,
                bad_since_ts=bad_since if new_state in ('SLOW', 'DOWN') else None,
                last_sent_ts=now if success else current_state.last_sent_ts,
                consecutive_failures=new_failures,
                consecutive_successes=new_successes,
            )
            
            return success
        
        # Update state without sending alert
        bad_since = current_state.bad_since_ts
        if new_state in ('SLOW', 'DOWN') and not bad_since:
            bad_since = now
        elif new_state == 'OK':
            bad_since = None
        
        self.db.update_alert_state(
            target_id=target_id,
            new_state=new_state,
            bad_since_ts=bad_since,
            last_sent_ts=current_state.last_sent_ts,
            consecutive_failures=new_failures,
            consecutive_successes=new_successes,
        )
        
        return False
    
    def _send_alert(
        self,
        target_id: str,
        alert_type: str,
        state: str,
        metrics: Optional[dict] = None,
    ) -> bool:
        """Send alert to Telegram."""
        if not self.bot_token or not self.chat_id:
            return False
        
        # Build message
        site_name, page_name = target_id.split(':', 1)
        
        if alert_type == 'DOWN':
            emoji = '🔴'
            title = 'DOWN'
        elif alert_type == 'SLOW':
            emoji = '🟠'
            title = 'SLOW'
        elif alert_type == 'RECOVERED':
            emoji = '🟢'
            title = 'RECOVERED'
        else:
            emoji = '⚠️'
            title = alert_type
        
        message = f"{emoji} {title}\n"
        message += f"Site: {site_name}\n"
        message += f"Page: {page_name}\n"
        message += f"State: {state}\n"
        
        if metrics:
            if metrics.get('url'):
                message += f"URL: {metrics['url']}\n"
            if metrics.get('http_code'):
                message += f"HTTP: {metrics['http_code']}\n"
            if metrics.get('ttfb') is not None:
                message += f"TTFB: {metrics['ttfb']:.3f}s\n"
            if metrics.get('total') is not None:
                message += f"Total: {metrics['total']:.3f}s\n"
            if metrics.get('error'):
                message += f"Error: {metrics['error']}\n"
        
        # Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            'chat_id': self.chat_id,
            'text': message,
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            if not result.get('ok'):
                print(f"Telegram API error: {result}", file=sys.stderr)
                return False
            return True
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}", file=sys.stderr)
            return False
    
    def send_daily_reminder(self) -> bool:
        """
        Send daily reminder about DOWN sites at 12:00 and 18:00.
        Returns True if reminder was sent, False otherwise.
        """
        if not self.bot_token or not self.chat_id:
            return False
        
        if not self.config:
            return False
        
        # Get all DOWN sites
        down_sites = []
        for page in self.config.pages:
            alert_state = self.db.get_alert_state(page.target_id)
            if alert_state and alert_state.last_state == 'DOWN':
                last_check = self.db.get_last_check(page.target_id)
                if last_check:
                    down_sites.append((page.target_id, page.url, last_check))
        
        if not down_sites:
            return False
        
        # Build reminder message
        message = "⏰ <b>Напоминание: Сайты в статусе DOWN</b>\n\n"
        
        for target_id, url, check in down_sites:
            emoji = '🔴'
            message += f"{emoji} {url}"
            if check.http_code:
                message += f" HTTP: {check.http_code}"
            if check.error:
                message += f" Error: {check.error}"
            message += "\n"
        
        message += f"\n<b>Всего:</b> {len(down_sites)} сайт(ов) в статусе DOWN"
        
        # Send via Telegram Bot API
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML',
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            return result.get('ok', False)
        except Exception as e:
            print(f"Failed to send daily reminder: {e}", file=sys.stderr)
            return False


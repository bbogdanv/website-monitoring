"""Alerting system with Telegram notifications and anti-spam logic."""
import os
import sys
import time
import requests
from typing import Optional
from config import AlertProfile
from db import AlertState, Database


class AlertManager:
    """Manages alerts with anti-spam and hysteresis logic."""
    
    def __init__(self, db: Database):
        """Initialize alert manager."""
        self.db = db
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
        
        # State transition: OK -> SLOW/DOWN
        if current_state.last_state == 'OK' and new_state in ('SLOW', 'DOWN'):
            if new_failures >= alert_profile.fail_count_to_alert:
                should_alert = True
                alert_type = 'DOWN' if new_state == 'DOWN' else 'SLOW'
        
        # State transition: SLOW/DOWN -> OK
        elif current_state.last_state in ('SLOW', 'DOWN') and new_state == 'OK':
            if new_successes >= alert_profile.recover_count:
                should_alert = True
                alert_type = 'RECOVERED'
        
        # First alert for persistent problem (page was DOWN from the start)
        elif new_state in ('SLOW', 'DOWN') and current_state.last_state in ('SLOW', 'DOWN'):
            # If we have enough consecutive failures and never sent alert
            if new_failures >= alert_profile.fail_count_to_alert and not current_state.last_sent_ts:
                should_alert = True
                alert_type = 'DOWN' if new_state == 'DOWN' else 'SLOW'
            # Reminder: problem persists (already sent before)
            elif current_state.last_sent_ts:
                time_since_last = now - current_state.last_sent_ts
                if time_since_last >= alert_profile.remind_every_sec:
                    # Check cooldown
                    if time_since_last >= alert_profile.cooldown_sec:
                        should_alert = True
                        alert_type = 'DOWN' if new_state == 'DOWN' else 'SLOW'
        
        # Check cooldown for any alert
        if should_alert and current_state.last_sent_ts:
            time_since_last = now - current_state.last_sent_ts
            if time_since_last < alert_profile.cooldown_sec:
                should_alert = False
        
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


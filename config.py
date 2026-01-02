"""Configuration loader for mini-monitor system."""
import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class AlertProfile:
    """Alert profile configuration."""
    warn_ttfb_sec: float
    crit_ttfb_sec: float
    fail_count_to_alert: int
    recover_count: int
    remind_every_sec: int
    cooldown_sec: int


@dataclass
class PageConfig:
    """Page monitoring configuration."""
    name: str
    path: str
    every_sec: int
    token: str
    expect_http: List[int]
    alert_profile: str
    site_name: str
    base_url: str

    @property
    def url(self) -> str:
        """Full URL for the page."""
        return f"{self.base_url.rstrip('/')}{self.path}"

    @property
    def target_id(self) -> str:
        """Unique identifier for this target."""
        return f"{self.site_name}:{self.name}"


@dataclass
class Defaults:
    """Default configuration values."""
    timeout_sec: int = 20
    user_agent: str = "mini-monitor/1.0"
    follow_redirects: bool = True
    compressed: bool = True
    retention_days: int = 14
    max_workers: int = 6
    max_checks_per_run: int = 10


class Config:
    """Main configuration class."""
    
    def __init__(self, config_path: str = "targets.yml"):
        """Load configuration from YAML file."""
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Load defaults
        defaults_data = data.get('defaults', {})
        self.defaults = Defaults(
            timeout_sec=defaults_data.get('timeout_sec', 20),
            user_agent=defaults_data.get('user_agent', 'mini-monitor/1.0'),
            follow_redirects=defaults_data.get('follow_redirects', True),
            compressed=defaults_data.get('compressed', True),
            retention_days=defaults_data.get('retention_days', 14),
            max_workers=defaults_data.get('max_workers', 6),
            max_checks_per_run=defaults_data.get('max_checks_per_run', 10),
        )
        
        # Load alert profiles
        self.alert_profiles: Dict[str, AlertProfile] = {}
        for name, profile_data in data.get('alert_profiles', {}).items():
            self.alert_profiles[name] = AlertProfile(
                warn_ttfb_sec=float(profile_data.get('warn_ttfb_sec', 1.5)),
                crit_ttfb_sec=float(profile_data.get('crit_ttfb_sec', 3.0)),
                fail_count_to_alert=int(profile_data.get('fail_count_to_alert', 2)),
                recover_count=int(profile_data.get('recover_count', 2)),
                remind_every_sec=int(profile_data.get('remind_every_sec', 3600)),
                cooldown_sec=int(profile_data.get('cooldown_sec', 300)),
            )
        
        # Load sites and pages
        self.pages: List[PageConfig] = []
        for site_data in data.get('sites', []):
            site_name = site_data['name']
            base_url = site_data['base']
            
            for page_data in site_data.get('pages', []):
                page = PageConfig(
                    name=page_data['name'],
                    path=page_data['path'],
                    every_sec=int(page_data['every_sec']),
                    token=page_data['token'],
                    expect_http=page_data.get('expect_http', [200]),
                    alert_profile=page_data.get('alert_profile', 'default'),
                    site_name=site_name,
                    base_url=base_url,
                )
                self.pages.append(page)
        
        # Validate alert profiles
        for page in self.pages:
            if page.alert_profile not in self.alert_profiles:
                raise ValueError(
                    f"Alert profile '{page.alert_profile}' not found for page "
                    f"{page.target_id}"
                )
    
    def get_alert_profile(self, profile_name: str) -> AlertProfile:
        """Get alert profile by name."""
        return self.alert_profiles[profile_name]
    
    def get_telegram_config(self) -> Dict[str, Optional[str]]:
        """Get Telegram configuration from environment."""
        return {
            'bot_token': os.getenv('BOT_TOKEN'),
            'chat_id': os.getenv('CHAT_ID'),
        }


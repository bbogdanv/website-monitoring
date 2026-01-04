#!/usr/bin/env python3
"""Main runner script for mini-monitor system."""
import os
import sys
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
from dotenv import load_dotenv

from config import Config, PageConfig
from db import Database, CheckResult
from checker import PageChecker
from alerts import AlertManager


def stable_hash(text: str) -> int:
    """Generate stable hash for consistent offset calculation."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def should_check_page(page: PageConfig, db: Database, now: float) -> bool:
    """
    Determine if a page should be checked now.
    
    Uses hash-based offset for even distribution.
    """
    last_check = db.get_last_check_time(page.target_id)
    
    if last_check is None:
        # First check - apply offset
        offset = stable_hash(page.target_id) % page.every_sec
        last_check = now - offset
    
    time_since_last = now - last_check
    return time_since_last >= page.every_sec


def check_page(
    page: PageConfig,
    config: Config,
    db: Database,
    alert_manager: AlertManager,
) -> CheckResult:
    """Check a single page and save result."""
    alert_profile = config.get_alert_profile(page.alert_profile)
    checker = PageChecker(page, config.defaults, alert_profile)
    ok, state, metrics = checker.check()
    
    now = time.time()
    
    # Create check result
    result = CheckResult(
        timestamp=now,
        target_id=page.target_id,
        site_name=page.site_name,
        page_name=page.name,
        url=page.url,
        ok=ok,
        state=state,
        http_code=metrics.http_code,
        dns=metrics.dns,
        connect=metrics.connect,
        tls=metrics.tls,
        ttfb=metrics.ttfb,
        total=metrics.total,
        size=metrics.size,
        error=metrics.error,
    )
    
    # Save to database
    db.save_check(result)
    
    # Process alerts
    alert_profile = config.get_alert_profile(page.alert_profile)
    metrics_dict = {
        'url': page.url,
        'http_code': metrics.http_code,
        'ttfb': metrics.ttfb,
        'total': metrics.total,
        'error': metrics.error,
    }
    alert_manager.process_check_result(
        page.target_id,
        state,
        alert_profile,
        metrics_dict,
    )
    
    return result


def main():
    """Main entry point."""
    # Load environment variables
    # Try to load from explicit path first (for Docker), then fallback to default
    env_path = '/app/.env' if os.path.exists('/app/.env') else '.env'
    load_dotenv(env_path)
    
    # Load configuration
    config_path = os.getenv('CONFIG_PATH', 'targets.yml')
    try:
        config = Config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize database
    db_path = os.getenv('DB_PATH', '/app/data/monitor.db')
    if not os.path.isabs(db_path):
        # If relative path, make it absolute relative to /app/data
        db_path = os.path.join('/app/data', db_path)
    db = Database(db_path)
    
    # Initialize alert manager
    alert_manager = AlertManager(db, config)
    
    # Get current time
    now = time.time()
    
    # Determine which pages need checking
    pages_to_check: List[PageConfig] = []
    for page in config.pages:
        if should_check_page(page, db, now):
            pages_to_check.append(page)
    
    # Limit number of checks per run
    if len(pages_to_check) > config.defaults.max_checks_per_run:
        pages_to_check = pages_to_check[:config.defaults.max_checks_per_run]
    
    if not pages_to_check:
        # Debug: show why no pages to check
        total_pages = len(config.pages)
        ready_count = sum(1 for p in config.pages if should_check_page(p, db, now))
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] No pages to check (ready: {ready_count}/{total_pages}, max_per_run: {config.defaults.max_checks_per_run})")
        # Still do cleanup
        deleted = db.cleanup_old_checks(config.defaults.retention_days)
        if deleted > 0:
            print(f"Cleaned up {deleted} old check records")
        db.close()
        return
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking {len(pages_to_check)} pages...")
    
    # Run checks in parallel
    results: List[CheckResult] = []
    with ThreadPoolExecutor(max_workers=config.defaults.max_workers) as executor:
        futures = {
            executor.submit(check_page, page, config, db, alert_manager): page
            for page in pages_to_check
        }
        
        for future in as_completed(futures):
            page = futures[future]
            try:
                result = future.result()
                results.append(result)
                status_emoji = {
                    'OK': '🟢',
                    'SLOW': '🟠',
                    'DOWN': '🔴',
                }.get(result.state, '❓')
                print(
                    f"  {status_emoji} {result.target_id}: {result.state} "
                    f"(TTFB: {result.ttfb:.3f}s, Total: {result.total:.3f}s)"
                    if result.ttfb and result.total
                    else f"  {status_emoji} {result.target_id}: {result.state}"
                )
            except Exception as e:
                print(f"  ❌ {page.target_id}: Error - {e}", file=sys.stderr)
    
    # Cleanup old checks
    deleted = db.cleanup_old_checks(config.defaults.retention_days)
    if deleted > 0:
        print(f"Cleaned up {deleted} old check records")
    
    # Close database
    db.close()
    
    print(f"Completed {len(results)} checks")


if __name__ == '__main__':
    main()


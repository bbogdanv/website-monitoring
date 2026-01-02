"""Database operations for mini-monitor system."""
import sqlite3
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CheckResult:
    """Result of a single check."""
    timestamp: float
    target_id: str
    site_name: str
    page_name: str
    url: str
    ok: bool
    state: str  # OK, SLOW, DOWN
    http_code: Optional[int]
    dns: Optional[float]
    connect: Optional[float]
    tls: Optional[float]
    ttfb: Optional[float]
    total: Optional[float]
    size: Optional[int]
    error: Optional[str]


@dataclass
class AlertState:
    """Current alert state for a target."""
    target_id: str
    last_state: str
    bad_since_ts: Optional[float]
    last_sent_ts: Optional[float]
    consecutive_failures: int
    consecutive_successes: int


class Database:
    """Database manager for SQLite."""
    
    def __init__(self, db_path: str = "monitor.db"):
        """Initialize database connection and create tables."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Table for check results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                timestamp REAL NOT NULL,
                target_id TEXT NOT NULL,
                site_name TEXT NOT NULL,
                page_name TEXT NOT NULL,
                url TEXT NOT NULL,
                ok INTEGER NOT NULL,
                state TEXT NOT NULL,
                http_code INTEGER,
                dns REAL,
                connect REAL,
                tls REAL,
                ttfb REAL,
                total REAL,
                size INTEGER,
                error TEXT
            )
        """)
        
        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_checks_target_timestamp 
            ON checks(target_id, timestamp DESC)
        """)
        
        # Table for alert states
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_state (
                target_id TEXT PRIMARY KEY,
                last_state TEXT NOT NULL,
                bad_since_ts REAL,
                last_sent_ts REAL,
                consecutive_failures INTEGER DEFAULT 0,
                consecutive_successes INTEGER DEFAULT 0
            )
        """)
        
        self.conn.commit()
    
    def get_last_check_time(self, target_id: str) -> Optional[float]:
        """Get timestamp of last check for a target."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(timestamp) as last_ts
            FROM checks
            WHERE target_id = ?
        """, (target_id,))
        row = cursor.fetchone()
        return row['last_ts'] if row and row['last_ts'] else None
    
    def save_check(self, result: CheckResult):
        """Save a check result to the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO checks (
                timestamp, target_id, site_name, page_name, url,
                ok, state, http_code, dns, connect, tls, ttfb, total, size, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.timestamp,
            result.target_id,
            result.site_name,
            result.page_name,
            result.url,
            1 if result.ok else 0,
            result.state,
            result.http_code,
            result.dns,
            result.connect,
            result.tls,
            result.ttfb,
            result.total,
            result.size,
            result.error,
        ))
        self.conn.commit()
    
    def get_alert_state(self, target_id: str) -> Optional[AlertState]:
        """Get current alert state for a target."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM alert_state WHERE target_id = ?
        """, (target_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return AlertState(
            target_id=row['target_id'],
            last_state=row['last_state'],
            bad_since_ts=row['bad_since_ts'],
            last_sent_ts=row['last_sent_ts'],
            consecutive_failures=row['consecutive_failures'],
            consecutive_successes=row['consecutive_successes'],
        )
    
    def update_alert_state(
        self,
        target_id: str,
        new_state: str,
        bad_since_ts: Optional[float] = None,
        last_sent_ts: Optional[float] = None,
        consecutive_failures: int = 0,
        consecutive_successes: int = 0,
    ):
        """Update alert state for a target."""
        cursor = self.conn.cursor()
        
        # Get current state
        current = self.get_alert_state(target_id)
        
        if current:
            # Update existing
            cursor.execute("""
                UPDATE alert_state
                SET last_state = ?,
                    bad_since_ts = ?,
                    last_sent_ts = ?,
                    consecutive_failures = ?,
                    consecutive_successes = ?
                WHERE target_id = ?
            """, (
                new_state,
                bad_since_ts if bad_since_ts is not None else current.bad_since_ts,
                last_sent_ts if last_sent_ts is not None else current.last_sent_ts,
                consecutive_failures,
                consecutive_successes,
                target_id,
            ))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO alert_state (
                    target_id, last_state, bad_since_ts, last_sent_ts,
                    consecutive_failures, consecutive_successes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                target_id,
                new_state,
                bad_since_ts,
                last_sent_ts,
                consecutive_failures,
                consecutive_successes,
            ))
        
        self.conn.commit()
    
    def cleanup_old_checks(self, retention_days: int):
        """Delete checks older than retention_days."""
        cursor = self.conn.cursor()
        cutoff = time.time() - (retention_days * 24 * 3600)
        cursor.execute("""
            DELETE FROM checks WHERE timestamp < ?
        """, (cutoff,))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted
    
    def get_recent_checks(self, target_id: str, limit: int = 10) -> List[CheckResult]:
        """Get recent check results for a target."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM checks
            WHERE target_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (target_id, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append(CheckResult(
                timestamp=row['timestamp'],
                target_id=row['target_id'],
                site_name=row['site_name'],
                page_name=row['page_name'],
                url=row['url'],
                ok=bool(row['ok']),
                state=row['state'],
                http_code=row['http_code'],
                dns=row['dns'],
                connect=row['connect'],
                tls=row['tls'],
                ttfb=row['ttfb'],
                total=row['total'],
                size=row['size'],
                error=row['error'],
            ))
        
        return results
    
    def close(self):
        """Close database connection."""
        self.conn.close()


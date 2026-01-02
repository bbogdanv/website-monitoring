"""Page checker using curl with metrics extraction."""
import subprocess
from typing import Optional
from dataclasses import dataclass
from config import PageConfig, Defaults, AlertProfile


@dataclass
class CheckMetrics:
    """Metrics from curl check."""
    http_code: Optional[int] = None
    dns: Optional[float] = None
    connect: Optional[float] = None
    tls: Optional[float] = None
    ttfb: Optional[float] = None
    total: Optional[float] = None
    size: Optional[int] = None
    error: Optional[str] = None
    body: Optional[str] = None


class PageChecker:
    """Checks a page using curl and validates response."""
    
    def __init__(self, page: PageConfig, defaults: Defaults, alert_profile: AlertProfile):
        """Initialize checker for a page."""
        self.page = page
        self.defaults = defaults
        self.alert_profile = alert_profile
    
    def check(self) -> tuple[bool, str, CheckMetrics]:
        """
        Perform check and return (ok, state, metrics).
        
        Returns:
            (ok, state, metrics) where:
            - ok: True if page loaded successfully
            - state: 'OK', 'SLOW', or 'DOWN'
            - metrics: CheckMetrics object
        """
        metrics = self._run_curl()
        
        if metrics.error:
            return False, 'DOWN', metrics
        
        # Check HTTP code
        if metrics.http_code not in self.page.expect_http:
            metrics.error = f"HTTP {metrics.http_code} not in allowed list {self.page.expect_http}"
            return False, 'DOWN', metrics
        
        # Check HTML marker
        if not metrics.body or self.page.token not in metrics.body:
            metrics.error = "HTML marker not found"
            return False, 'DOWN', metrics
        
        # Determine state based on TTFB
        if metrics.ttfb is None:
            metrics.error = "TTFB not available"
            return False, 'DOWN', metrics
        
        if metrics.ttfb >= self.alert_profile.crit_ttfb_sec:
            return True, 'SLOW', metrics
        elif metrics.ttfb >= self.alert_profile.warn_ttfb_sec:
            return True, 'SLOW', metrics
        else:
            return True, 'OK', metrics
    
    def _run_curl(self) -> CheckMetrics:
        """Run curl and extract metrics."""
        metrics = CheckMetrics()
        
        # Build curl command with format string for metrics
        # Format: http_code|time_namelookup|time_connect|time_appconnect|time_starttransfer|time_total|size_download
        format_string = (
            '\n'
            '%{http_code}|'
            '%{time_namelookup}|'
            '%{time_connect}|'
            '%{time_appconnect}|'
            '%{time_starttransfer}|'
            '%{time_total}|'
            '%{size_download}'
            '\n'
        )
        
        cmd = [
            'curl',
            '-s',  # silent
            '-S',  # show errors
            '-L',  # follow redirects
            '--compressed',  # accept compressed
            '-w', format_string,
            '--max-time', str(self.defaults.timeout_sec),
            '--connect-timeout', str(self.defaults.timeout_sec),
            '-H', f'User-Agent: {self.defaults.user_agent}',
            self.page.url,
        ]
        
        if not self.defaults.follow_redirects:
            cmd.remove('-L')
        
        if not self.defaults.compressed:
            cmd.remove('--compressed')
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.defaults.timeout_sec + 5,
            )
            
            # Parse output
            # curl outputs: body\nmetrics_line\n
            output = result.stdout
            lines = output.rstrip().split('\n')
            
            if not lines:
                metrics.error = "Empty response from curl"
                return metrics
            
            # Last non-empty line should be metrics
            metrics_line = None
            for line in reversed(lines):
                if line.strip() and '|' in line:
                    metrics_line = line
                    break
            
            if not metrics_line:
                metrics.error = "Failed to extract metrics from curl output"
                if result.stderr:
                    metrics.error += f": {result.stderr}"
                return metrics
            
            # Body is everything before the metrics line
            metrics_idx = lines.index(metrics_line) if metrics_line in lines else len(lines) - 1
            body = '\n'.join(lines[:metrics_idx]) if metrics_idx > 0 else ''
            
            # Parse metrics: http_code|dns|connect|tls|ttfb|total|size
            parts = metrics_line.split('|')
            if len(parts) >= 7:
                try:
                    metrics.http_code = int(parts[0]) if parts[0] else None
                    metrics.dns = float(parts[1]) if parts[1] else None
                    metrics.connect = float(parts[2]) if parts[2] else None
                    metrics.tls = float(parts[3]) if parts[3] else None
                    metrics.ttfb = float(parts[4]) if parts[4] else None
                    metrics.total = float(parts[5]) if parts[5] else None
                    metrics.size = int(parts[6]) if parts[6] else None
                except (ValueError, IndexError) as e:
                    metrics.error = f"Failed to parse metrics: {e}"
                    return metrics
            else:
                metrics.error = f"Invalid metrics format: {metrics_line}"
                return metrics
            
            metrics.body = body
            
            # Check for curl errors
            if result.returncode != 0:
                metrics.error = f"curl exit code {result.returncode}"
                if result.stderr:
                    metrics.error += f": {result.stderr}"
            
        except subprocess.TimeoutExpired:
            metrics.error = f"Timeout after {self.defaults.timeout_sec}s"
        except FileNotFoundError:
            metrics.error = "curl not found in PATH"
        except Exception as e:
            metrics.error = f"Unexpected error: {str(e)}"
        
        return metrics


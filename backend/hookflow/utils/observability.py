"""Enhanced observability utilities for webhook monitoring.

Provides histogram-based metrics, gauges, and health scoring
for webhook delivery infrastructure.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Summary


class DestinationHealth(Enum):
    """Destination health status."""
    HEALTHY = "healthy"       # Success rate > 95%
    DEGRADED = "degraded"     # Success rate 80-95%
    UNHEALTHY = "unhealthy"   # Success rate < 80%
    UNKNOWN = "unknown"       # Insufficient data


@dataclass
class MetricValue:
    """A single metric value with timestamp."""
    value: float
    timestamp: float = field(default_factory=time.time)

    def age_seconds(self) -> float:
        """Get age of this metric in seconds."""
        return time.time() - self.timestamp


@dataclass
class TimeSeries:
    """A simple time series for storing recent values."""
    max_size: int = 1000
    values: list[MetricValue] = field(default_factory=list)

    def add(self, value: float) -> None:
        """Add a value to the time series."""
        self.values.append(MetricValue(value))
        # Trim to max size
        if len(self.values) > self.max_size:
            self.values.pop(0)

    def get_recent(self, seconds: float = 60) -> list[float]:
        """Get values from the last N seconds."""
        cutoff = time.time() - seconds
        return [v.value for v in self.values if v.timestamp >= cutoff]

    def percentile(self, p: float) -> float | None:
        """Calculate percentile of values.

        Args:
            p: Percentile to calculate (0-100)

        Returns:
            Percentile value or None if no data
        """
        if not self.values:
            return None
        sorted_values = sorted(v.value for v in self.values)
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(sorted_values):
            return sorted_values[-1]
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def avg(self) -> float | None:
        """Calculate average of values."""
        if not self.values:
            return None
        return sum(v.value for v in self.values) / len(self.values)

    def count(self, seconds: float | None = None) -> int:
        """Count values, optionally within a time window.

        Args:
            seconds: If provided, only count values from last N seconds

        Returns:
            Number of values
        """
        if seconds is None:
            return len(self.values)

        cutoff = time.time() - seconds
        return sum(1 for v in self.values if v.timestamp >= cutoff)


class WebhookMetrics:
    """Metrics collector for webhook delivery observations.

    Tracks response times, success/failure rates, and per-destination health.
    Uses Prometheus metrics for external monitoring.
    """

    # Prometheus metrics
    webhook_deliveries_total = Counter(
        "hookflow_webhook_deliveries_total",
        "Total number of webhook delivery attempts",
        ["app_id", "destination_id", "status"]
    )

    webhook_delivery_duration_seconds = Histogram(
        "hookflow_webhook_delivery_duration_seconds",
        "Webhook delivery duration in seconds",
        ["app_id", "destination_id"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )

    webhook_delivery_success_rate = Gauge(
        "hookflow_webhook_delivery_success_rate",
        "Webhook delivery success rate (0-1)",
        ["app_id", "destination_id"]
    )

    destination_health_status = Gauge(
        "hookflow_destination_health_status",
        "Destination health status (0=unknown, 1=healthy, 2=degraded, 3=unhealthy)",
        ["app_id", "destination_id"]
    )

    circuit_breaker_state = Gauge(
        "hookflow_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=open, 2=half_open)",
        ["destination_id"]
    )

    active_destinations = Gauge(
        "hookflow_active_destinations",
        "Number of active destinations per app",
        ["app_id"]
    )

    def __init__(self):
        """Initialize metrics collector."""
        # In-memory time series for percentiles
        self._response_times: dict[str, TimeSeries] = defaultdict(lambda: TimeSeries())
        self._delivery_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failure": 0})

    def record_delivery(
        self,
        app_id: str,
        destination_id: str,
        status: str,
        duration_ms: float,
    ) -> None:
        """Record a webhook delivery attempt.

        Args:
            app_id: Application ID
            destination_id: Destination ID
            status: Delivery status (success, failed, retrying)
            duration_ms: Response time in milliseconds
        """
        # Record Prometheus metrics
        self.webhook_deliveries_total.labels(
            app_id=app_id,
            destination_id=destination_id,
            status=status
        ).inc()

        duration_seconds = duration_ms / 1000.0
        self.webhook_delivery_duration_seconds.labels(
            app_id=app_id,
            destination_id=destination_id
        ).observe(duration_seconds)

        # Store for percentile calculation
        key = f"{app_id}:{destination_id}"
        self._response_times[key].add(duration_seconds)

        # Update success/failure counts
        if status == "success":
            self._delivery_counts[key]["success"] += 1
        elif status in ("failed", "retrying"):
            self._delivery_counts[key]["failure"] += 1

        # Update derived metrics
        self._update_success_rate(app_id, destination_id)
        self._update_health_status(app_id, destination_id)

    def get_response_time_percentiles(
        self,
        app_id: str,
        destination_id: str,
        window_seconds: float = 300,
    ) -> dict[str, float | None]:
        """Get response time percentiles for a destination.

        Args:
            app_id: Application ID
            destination_id: Destination ID
            window_seconds: Time window in seconds (default: 5 minutes)

        Returns:
            Dictionary with p50, p95, p99, avg percentiles
        """
        key = f"{app_id}:{destination_id}"
        series = self._response_times[key]

        # Filter by time window
        cutoff = time.time() - window_seconds
        recent_values = [v.value for v in series.values if v.timestamp >= cutoff]

        if not recent_values:
            return {"p50": None, "p95": None, "p99": None, "avg": None}

        sorted_values = sorted(recent_values)
        n = len(sorted_values)

        def percentile(p: float) -> float:
            k = (n - 1) * p / 100
            f = int(k)
            c = min(f + 1, n - 1)
            return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

        return {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99),
            "avg": sum(sorted_values) / n,
        }

    def get_success_rate(
        self,
        app_id: str,
        destination_id: str,
        window_seconds: float = 300,
    ) -> float | None:
        """Get success rate for a destination.

        Args:
            app_id: Application ID
            destination_id: Destination ID
            window_seconds: Time window in seconds (default: 5 minutes)

        Returns:
            Success rate as float 0-1, or None if no data
        """
        key = f"{app_id}:{destination_id}"
        counts = self._delivery_counts.get(key)
        if not counts:
            return None

        # For simplicity, return all-time rate
        # In production, would need time-windowed counters
        total = counts["success"] + counts["failure"]
        if total == 0:
            return None
        return counts["success"] / total

    def get_health_status(
        self,
        app_id: str,
        destination_id: str,
    ) -> DestinationHealth:
        """Get health status for a destination.

        Args:
            app_id: Application ID
            destination_id: Destination ID

        Returns:
            DestinationHealth enum value
        """
        success_rate = self.get_success_rate(app_id, destination_id)

        if success_rate is None:
            return DestinationHealth.UNKNOWN
        elif success_rate >= 0.95:
            return DestinationHealth.HEALTHY
        elif success_rate >= 0.80:
            return DestinationHealth.DEGRADED
        else:
            return DestinationHealth.UNHEALTHY

    def get_destination_stats(
        self,
        app_id: str,
        destination_id: str,
    ) -> dict[str, Any]:
        """Get comprehensive stats for a destination.

        Args:
            app_id: Application ID
            destination_id: Destination ID

        Returns:
            Dictionary with all metrics for the destination
        """
        percentiles = self.get_response_time_percentiles(app_id, destination_id)
        success_rate = self.get_success_rate(app_id, destination_id)
        health = self.get_health_status(app_id, destination_id)

        key = f"{app_id}:{destination_id}"
        counts = self._delivery_counts.get(key, {"success": 0, "failure": 0})

        return {
            "app_id": app_id,
            "destination_id": destination_id,
            "success_rate": success_rate,
            "health_status": health.value,
            "total_success": counts["success"],
            "total_failure": counts["failure"],
            "total_deliveries": counts["success"] + counts["failure"],
            "response_time_ms": {
                "p50": percentiles["p50"],
                "p95": percentiles["p95"],
                "p99": percentiles["p99"],
                "avg": percentiles["avg"],
            },
        }

    def _update_success_rate(self, app_id: str, destination_id: str) -> None:
        """Update success rate gauge."""
        rate = self.get_success_rate(app_id, destination_id)
        if rate is not None:
            self.webhook_delivery_success_rate.labels(
                app_id=app_id,
                destination_id=destination_id
            ).set(rate)

    def _update_health_status(self, app_id: str, destination_id: str) -> None:
        """Update health status gauge."""
        health = self.get_health_status(app_id, destination_id)

        # Map enum to numeric value
        health_values = {
            DestinationHealth.UNKNOWN: 0,
            DestinationHealth.HEALTHY: 1,
            DestinationHealth.DEGRADED: 2,
            DestinationHealth.UNHEALTHY: 3,
        }

        self.destination_health_status.labels(
            app_id=app_id,
            destination_id=destination_id
        ).set(health_values[health])

    def reset_metrics(self, app_id: str | None = None, destination_id: str | None = None) -> None:
        """Reset metrics for an app or destination.

        Args:
            app_id: Application ID, or None for all apps
            destination_id: Destination ID, or None for all destinations
        """
        if app_id is None and destination_id is None:
            # Reset all
            self._response_times.clear()
            self._delivery_counts.clear()
        else:
            # Reset specific
            if destination_id and app_id:
                key = f"{app_id}:{destination_id}"
                self._response_times.pop(key, None)
                self._delivery_counts.pop(key, None)
            elif app_id:
                # Reset all for app
                prefix = f"{app_id}:"
                for k in list(self._response_times.keys()):
                    if k.startswith(prefix):
                        self._response_times.pop(k)
                for k in list(self._delivery_counts.keys()):
                    if k.startswith(prefix):
                        self._delivery_counts.pop(k)


# Global metrics instance
_metrics_instance: WebhookMetrics | None = None


def get_metrics() -> WebhookMetrics:
    """Get the global metrics instance.

    Returns:
        WebhookMetrics singleton instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = WebhookMetrics()
    return _metrics_instance

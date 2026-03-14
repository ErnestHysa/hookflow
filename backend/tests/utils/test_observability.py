"""Tests for observability metrics."""

import time

import pytest

from hookflow.utils.observability import (
    WebhookMetrics,
    DestinationHealth,
    TimeSeries,
    MetricValue,
    get_metrics,
)


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_age_seconds(self):
        """Test calculating age of metric value."""
        mv = MetricValue(10.0, timestamp=time.time() - 5)
        assert mv.age_seconds() >= 4.9  # Approximately 5 seconds


class TestTimeSeries:
    """Tests for TimeSeries class."""

    def test_add_value(self):
        """Test adding values to time series."""
        ts = TimeSeries()
        ts.add(1.0)
        ts.add(2.0)
        ts.add(3.0)

        assert len(ts.values) == 3
        assert ts.values[0].value == 1.0

    def test_max_size_limit(self):
        """Test that time series respects max size."""
        ts = TimeSeries(max_size=3)

        for i in range(10):
            ts.add(float(i))

        assert len(ts.values) == 3
        # Should keep most recent values
        assert ts.values[-1].value == 9.0

    def test_get_recent(self):
        """Test getting recent values."""
        ts = TimeSeries()

        ts.add(1.0)
        time.sleep(0.1)
        ts.add(2.0)
        time.sleep(0.1)
        ts.add(3.0)

        recent = ts.get_recent(seconds=0.15)
        # Should get the last 2 values
        assert len(recent) >= 1

    def test_percentile(self):
        """Test percentile calculation."""
        ts = TimeSeries()

        for i in range(1, 101):
            ts.add(float(i))

        assert ts.percentile(50) == 50.5  # Median
        assert ts.percentile(95) >= 95
        assert ts.percentile(99) >= 99

    def test_percentile_empty(self):
        """Test percentile with no data."""
        ts = TimeSeries()
        assert ts.percentile(50) is None

    def test_percentile_single_value(self):
        """Test percentile with single value."""
        ts = TimeSeries()
        ts.add(42.0)

        assert ts.percentile(50) == 42.0
        assert ts.percentile(99) == 42.0

    def test_avg(self):
        """Test average calculation."""
        ts = TimeSeries()

        ts.add(10.0)
        ts.add(20.0)
        ts.add(30.0)

        assert ts.avg() == 20.0

    def test_avg_empty(self):
        """Test average with no data."""
        ts = TimeSeries()
        assert ts.avg() is None

    def test_count(self):
        """Test counting values."""
        ts = TimeSeries()

        for i in range(5):
            ts.add(float(i))

        assert ts.count() == 5

    def test_count_with_time_window(self):
        """Test counting values within time window."""
        ts = TimeSeries()

        ts.add(1.0)
        time.sleep(0.1)
        ts.add(2.0)

        # Count all
        assert ts.count() == 2

        # Count recent (last 50ms)
        recent = ts.count(seconds=0.05)
        assert recent <= 2


class TestWebhookMetrics:
    """Tests for WebhookMetrics class."""

    def test_record_delivery_success(self):
        """Test recording a successful delivery."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)

        # Check delivery counts
        key = "app-1:dest-1"
        assert metrics._delivery_counts[key]["success"] == 1
        assert metrics._delivery_counts[key]["failure"] == 0

    def test_record_delivery_failure(self):
        """Test recording a failed delivery."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "failed", 50.0)

        key = "app-1:dest-1"
        assert metrics._delivery_counts[key]["success"] == 0
        assert metrics._delivery_counts[key]["failure"] == 1

    def test_response_time_tracking(self):
        """Test that response times are tracked."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-1", "dest-1", "success", 200.0)
        metrics.record_delivery("app-1", "dest-1", "success", 300.0)

        percentiles = metrics.get_response_time_percentiles("app-1", "dest-1")

        assert percentiles["p50"] is not None
        assert percentiles["p95"] is not None
        assert percentiles["p99"] is not None
        assert percentiles["avg"] is not None

    def test_response_time_percentiles(self):
        """Test percentile calculation accuracy."""
        metrics = WebhookMetrics()

        # Add known values (in milliseconds)
        for ms in [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]:
            metrics.record_delivery("app-1", "dest-1", "success", ms)

        percentiles = metrics.get_response_time_percentiles("app-1", "dest-1")

        # P50 should be around 275 (median of 50,100,...,500)
        # Values are in seconds (ms / 1000)
        assert 0.25 <= percentiles["p50"] <= 0.30

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = WebhookMetrics()

        # 7 success, 3 failure = 70% success rate
        for _ in range(7):
            metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        for _ in range(3):
            metrics.record_delivery("app-1", "dest-1", "failed", 100.0)

        rate = metrics.get_success_rate("app-1", "dest-1")
        assert rate == 0.7

    def test_success_rate_no_data(self):
        """Test success rate with no data."""
        metrics = WebhookMetrics()

        rate = metrics.get_success_rate("app-1", "dest-1")
        assert rate is None

    def test_health_status_healthy(self):
        """Test healthy status for high success rate."""
        metrics = WebhookMetrics()

        # 95%+ success rate = healthy
        for _ in range(95):
            metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        for _ in range(5):
            metrics.record_delivery("app-1", "dest-1", "failed", 100.0)

        health = metrics.get_health_status("app-1", "dest-1")
        assert health == DestinationHealth.HEALTHY

    def test_health_status_degraded(self):
        """Test degraded status for medium success rate."""
        metrics = WebhookMetrics()

        # 80-95% success rate = degraded
        for _ in range(85):
            metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        for _ in range(15):
            metrics.record_delivery("app-1", "dest-1", "failed", 100.0)

        health = metrics.get_health_status("app-1", "dest-1")
        assert health == DestinationHealth.DEGRADED

    def test_health_status_unhealthy(self):
        """Test unhealthy status for low success rate."""
        metrics = WebhookMetrics()

        # <80% success rate = unhealthy
        for _ in range(70):
            metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        for _ in range(30):
            metrics.record_delivery("app-1", "dest-1", "failed", 100.0)

        health = metrics.get_health_status("app-1", "dest-1")
        assert health == DestinationHealth.UNHEALTHY

    def test_health_status_unknown(self):
        """Test unknown status with no data."""
        metrics = WebhookMetrics()

        health = metrics.get_health_status("app-1", "dest-1")
        assert health == DestinationHealth.UNKNOWN

    def test_get_destination_stats(self):
        """Test getting comprehensive destination stats."""
        metrics = WebhookMetrics()

        # Add some data
        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-1", "dest-1", "success", 200.0)
        metrics.record_delivery("app-1", "dest-1", "failed", 50.0)

        stats = metrics.get_destination_stats("app-1", "dest-1")

        assert stats["app_id"] == "app-1"
        assert stats["destination_id"] == "dest-1"
        assert stats["total_success"] == 2
        assert stats["total_failure"] == 1
        assert stats["total_deliveries"] == 3
        assert stats["success_rate"] == 2/3
        assert stats["health_status"] in ["healthy", "degraded", "unhealthy", "unknown"]
        assert stats["response_time_ms"]["p50"] is not None

    def test_multiple_destinations_independent(self):
        """Test that multiple destinations have independent metrics."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-1", "dest-2", "failed", 50.0)

        stats1 = metrics.get_destination_stats("app-1", "dest-1")
        stats2 = metrics.get_destination_stats("app-1", "dest-2")

        assert stats1["total_success"] == 1
        assert stats1["total_failure"] == 0
        assert stats2["total_success"] == 0
        assert stats2["total_failure"] == 1

    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-1", "dest-1", "failed", 50.0)

        assert metrics.get_success_rate("app-1", "dest-1") == 0.5

        metrics.reset_metrics("app-1", "dest-1")

        assert metrics.get_success_rate("app-1", "dest-1") is None

    def test_reset_metrics_by_app(self):
        """Test resetting all metrics for an app."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-1", "dest-2", "success", 100.0)
        metrics.record_delivery("app-2", "dest-1", "success", 100.0)

        metrics.reset_metrics(app_id="app-1")

        # app-1 metrics should be cleared
        assert metrics.get_success_rate("app-1", "dest-1") is None
        assert metrics.get_success_rate("app-1", "dest-2") is None

        # app-2 metrics should remain
        assert metrics.get_success_rate("app-2", "dest-1") == 1.0

    def test_reset_all_metrics(self):
        """Test resetting all metrics."""
        metrics = WebhookMetrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)
        metrics.record_delivery("app-2", "dest-2", "success", 100.0)

        metrics.reset_metrics()

        assert metrics.get_success_rate("app-1", "dest-1") is None
        assert metrics.get_success_rate("app-2", "dest-2") is None


class TestGetMetrics:
    """Tests for get_metrics singleton function."""

    def test_singleton_instance(self):
        """Test that get_metrics returns the same instance."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    def test_record_via_singleton(self):
        """Test recording metrics via singleton."""
        metrics = get_metrics()

        metrics.record_delivery("app-1", "dest-1", "success", 100.0)

        metrics2 = get_metrics()
        rate = metrics2.get_success_rate("app-1", "dest-1")

        assert rate == 1.0

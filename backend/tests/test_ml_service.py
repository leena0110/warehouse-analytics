"""
test_ml_service.py — Tests for ML forecasting and recommendation engine.
"""

import pytest
from app.services.ml_service import (
    forecast_utilization,
    generate_recommendations,
    analyze_operational_insights,
    _compute_risk,
)


# ── Risk level tests ──────────────────────────────────────────────────────────

def test_compute_risk_low():
    assert _compute_risk(30.0) == "LOW"

def test_compute_risk_medium():
    assert _compute_risk(65.0) == "MEDIUM"

def test_compute_risk_high():
    assert _compute_risk(80.0) == "HIGH"

def test_compute_risk_critical():
    assert _compute_risk(95.0) == "CRITICAL"


# ── Forecast tests ────────────────────────────────────────────────────────────

def test_forecast_with_sufficient_history():
    """LinearRegression should be used when >= 5 history points."""
    history = [50.0, 55.0, 58.0, 62.0, 65.0, 68.0]
    stats = {"utilization_pct": 70.0, "blocked_pct": 5.0, "zone_stats": {}}
    result = forecast_utilization(history, stats)
    assert result["method"] == "LinearRegression"
    assert len(result["forecast_days"]) == 7
    assert 0 <= result["peak_forecast"] <= 100
    assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_forecast_with_insufficient_history():
    """Heuristic fallback used when < 5 history points."""
    history = [60.0, 62.0]
    stats = {"utilization_pct": 62.0, "blocked_pct": 3.0, "zone_stats": {}}
    result = forecast_utilization(history, stats)
    assert result["method"] == "ExponentialHeuristic"
    assert len(result["forecast_days"]) == 7


def test_forecast_no_history():
    """Works with empty history (0 historical points)."""
    stats = {"utilization_pct": 45.0, "blocked_pct": 2.0, "zone_stats": {}}
    result = forecast_utilization([], stats)
    assert result["forecast_days"] is not None
    assert result["current_utilization"] == 45.0


def test_forecast_predictions_clipped():
    """Predicted values should always be in [0, 100]."""
    history = [90.0, 92.0, 94.0, 96.0, 98.0, 100.0]
    stats = {"utilization_pct": 100.0, "blocked_pct": 0.0, "zone_stats": {}}
    result = forecast_utilization(history, stats)
    for day in result["forecast_days"]:
        assert 0 <= day["predicted_utilization"] <= 100


# ── Recommendation tests ──────────────────────────────────────────────────────

def make_forecast(util): return {"peak_forecast": util, "risk_level": _compute_risk(util)}

def test_recommendation_critical():
    stats = {"utilization_pct": 93.0, "blocked_pct": 2.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(93.0))
    types = [r["type"] for r in recs]
    assert "CRITICAL" in types


def test_recommendation_warning():
    stats = {"utilization_pct": 78.0, "blocked_pct": 3.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(78.0))
    types = [r["type"] for r in recs]
    assert "WARNING" in types


def test_recommendation_underutilized():
    stats = {"utilization_pct": 25.0, "blocked_pct": 5.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(25.0))
    types = [r["type"] for r in recs]
    assert "INFO" in types


def test_recommendation_high_blocked():
    stats = {"utilization_pct": 50.0, "blocked_pct": 15.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(50.0))
    types = [r["type"] for r in recs]
    assert "WARNING" in types


def test_recommendation_ok_state():
    """Healthy warehouse should return OK recommendation."""
    stats = {"utilization_pct": 55.0, "blocked_pct": 2.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(55.0))
    assert any(r["type"] == "OK" for r in recs)


def test_recommendations_sorted_by_priority():
    """Recommendations should be sorted P1 > P2 > P3 > P4."""
    stats = {"utilization_pct": 95.0, "blocked_pct": 15.0, "zone_stats": {}}
    recs = generate_recommendations(stats, make_forecast(95.0))
    priorities = [r["priority"] for r in recs]
    # P1 must appear before P2, etc.
    assert priorities == sorted(priorities)


# ── Operational insights tests ────────────────────────────────────────────────

def test_insights_empty_reports():
    result = analyze_operational_insights([])
    assert result["total_reports"] == 0
    assert result["category_breakdown"] == {}


def test_insights_keyword_detection():
    reports = [
        {"title": "Forklift issue", "content": "Forklift broke down in zone B", "category": "EQUIPMENT", "severity": "HIGH"},
        {"title": "Aisle blocked", "content": "Block in main aisle near entry", "category": "BLOCKAGE", "severity": "MEDIUM"},
    ]
    result = analyze_operational_insights(reports)
    assert result["total_reports"] == 2
    assert "EQUIPMENT" in result["category_breakdown"]
    assert "BLOCKAGE" in result["category_breakdown"]
    # Should detect keywords like 'forklift', 'block', 'aisle'
    assert any(kw in result["common_issues"] for kw in ["forklift", "block", "aisle"])


def test_insights_method_label():
    """Insights method must clearly state it is local classification."""
    result = analyze_operational_insights([
        {"title": "test", "content": "test content", "category": "GENERAL", "severity": "LOW"}
    ])
    assert "local" in result["method"].lower() or "keyword" in result["method"].lower()


def test_insights_empty_has_risk_level():
    """Empty reports should return risk_level LOW, not None."""
    result = analyze_operational_insights([])
    assert "risk_level" in result
    assert result["risk_level"] == "LOW"


def test_insights_risk_level_derives_from_highest_severity():
    """risk_level should reflect the highest severity seen in reports."""
    reports = [
        {"title": "Minor", "content": "small issue", "category": "GENERAL", "severity": "LOW"},
        {"title": "Critical!", "content": "fire hazard found", "category": "SAFETY", "severity": "CRITICAL"},
        {"title": "Medium", "content": "some congestion", "category": "CONGESTION", "severity": "MEDIUM"},
    ]
    result = analyze_operational_insights(reports)
    assert result["risk_level"] == "CRITICAL"


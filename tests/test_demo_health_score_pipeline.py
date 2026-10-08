from __future__ import annotations

from io import StringIO

from scripts.demo_health_score_pipeline import run_demo


def test_health_score_demo_reaches_sustained_alarm() -> None:
    stream = StringIO()

    summary = run_demo(interval=0, stream=stream)

    assert summary.sample_count == 10
    assert summary.initial_health_score > summary.final_health_score
    assert summary.final_health_score == 35
    assert summary.peak_anomaly_probability >= 0.9
    assert summary.final_sustained_minutes == 30
    assert summary.intelligent_alarm_triggered is True
    assert summary.alarm_message is not None
    assert "已触发" in stream.getvalue()


def test_health_score_demo_supports_json_lines() -> None:
    stream = StringIO()

    summary = run_demo(interval=0, json_lines=True, stream=stream)

    output_lines = stream.getvalue().splitlines()
    assert len(output_lines) == summary.sample_count + 1
    assert '"phase": "触发告警"' in output_lines[-2]
    assert '"type": "summary"' in output_lines[-1]

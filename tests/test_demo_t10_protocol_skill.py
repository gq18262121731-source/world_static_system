from __future__ import annotations

import pytest

from scripts.demo_t10_protocol_skill import (
    RECORDED_RESPONSE_FRAMES,
    T10SkillPipeline,
    realtime_url_from_ingest,
)


DEVICE_MAC = "54:10:26:01:00:DF"


def test_recorded_a_b_frames_become_complete_standard_object() -> None:
    pipeline = T10SkillPipeline()

    first = pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[0],
        fallback_mac=DEVICE_MAC,
        frame_origin="offline",
    )
    second = pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[1],
        fallback_mac=DEVICE_MAC,
        frame_origin="offline",
    )

    assert first.packet_kind == "response_a"
    assert first.normalized is not None
    assert first.normalized["heart_rate"] == 72
    assert first.normalized["spo2"] == 98
    assert first.normalized["temperature"] == 36.58
    assert first.normalized["quality"]["status"] == "partial"
    assert first.normalized["quality"]["accepted_for_platform"] is False

    assert second.packet_kind == "response_b"
    assert second.normalized is not None
    assert second.normalized["heart_rate"] == 72
    assert second.normalized["spo2"] == 98
    assert second.normalized["temperature"] == 36.63
    assert second.normalized["blood_pressure"] == "120/78"
    assert second.normalized["quality"]["status"] == "complete"
    assert second.normalized["quality"]["source_packets"] == ["response_a", "response_b"]
    assert second.normalized["quality"]["accepted_for_platform"] is True


def test_b_only_frame_marks_missing_values_without_fabricating_them() -> None:
    pipeline = T10SkillPipeline()

    result = pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[1],
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )

    assert result.normalized is not None
    assert result.normalized["heart_rate"] is None
    assert result.normalized["spo2"] is None
    assert result.normalized["temperature"] == 36.63
    assert result.normalized["quality"]["status"] == "partial"
    assert result.normalized["quality"]["accepted_for_platform"] is False
    assert result.normalized["quality"]["missing_fields"] == ["heart_rate", "spo2"]
    assert "missing_values_are_null_not_fabricated" in result.normalized["quality"]["notes"]


def test_platform_mapping_preserves_existing_contract() -> None:
    pipeline = T10SkillPipeline()
    pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[0],
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )
    result = pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[1],
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )

    assert result.normalized is not None
    payload = pipeline.to_platform_payload(result.normalized)

    assert payload["source"] == "serial"
    assert payload["blood_oxygen"] == 98
    assert payload["packet_type"] == "response_ab"
    assert "spo2" not in payload
    assert "quality" not in payload


def test_out_of_sensor_range_value_is_flagged_and_not_pushed() -> None:
    pipeline = T10SkillPipeline()
    pipeline.process_raw_line(
        RECORDED_RESPONSE_FRAMES[0],
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )

    result = pipeline.process_raw_line(
        "BA5410260100DF160318784E1388",  # 0x1388 / 100 = 50.0 C
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )

    assert result.normalized is not None
    assert result.normalized["temperature"] == 50.0
    assert result.normalized["quality"]["status"] == "invalid"
    assert result.normalized["quality"]["accepted_for_platform"] is False
    assert result.normalized["quality"]["invalid_fields"] == {
        "temperature": "outside_sensor_range_30_45",
    }


def test_non_packet_line_is_rejected_before_parsing() -> None:
    pipeline = T10SkillPipeline()

    result = pipeline.process_raw_line(
        "OK",
        fallback_mac=DEVICE_MAC,
        frame_origin="serial",
    )

    assert result.packet_kind == "unknown"
    assert result.normalized is None
    assert result.error == "no_ble_payload"


def test_realtime_url_requires_the_documented_ingest_endpoint() -> None:
    assert realtime_url_from_ingest(
        "http://127.0.0.1:8000/api/v1/health/ingest",
        DEVICE_MAC,
    ) == "http://127.0.0.1:8000/api/v1/health/realtime/54%3A10%3A26%3A01%3A00%3ADF"

    with pytest.raises(RuntimeError, match="push_url_must_end"):
        realtime_url_from_ingest("http://127.0.0.1:8000/api/v1/ingest", DEVICE_MAC)

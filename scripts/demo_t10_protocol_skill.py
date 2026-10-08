from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.health_model import HealthSample, IngestionSource
from iot.parser import PacketKind, T10PacketParser
from iot.serial_reader import SerialGatewayReader


# 备用录制帧只用于现场硬件异常时演示同一解析函数。
# 数值对应：HR=72、SpO2=98、A包表面温度=36.58、B包体温=36.63、BP=120/78。
RECORDED_RESPONSE_FRAMES = (
    "BA5410260100DF16180309E65A0E4A004800625410260100DF04D2",
    "BA5410260100DF160318784E0E4F",
)

SOURCE_LABELS = {
    "serial": "实时串口帧",
    "offline": "备用录制帧（非实时）",
}

COLLECTOR_DETECTION_KEYWORDS = [
    "cp210",
    "ch9102",
    "wch",
    "usb serial",
    "silicon labs",
]


@dataclass(frozen=True, slots=True)
class FrameResult:
    raw_line: str
    payload_hex: str | None
    packet_kind: str
    normalized: dict[str, Any] | None
    error: str | None = None


class T10SkillPipeline:
    """Small stage adapter around the production T10 parser.

    It intentionally keeps ``quality`` outside ``HealthSample`` so the existing
    REST/WebSocket contract remains unchanged during the competition demo.
    """

    def __init__(self, *, merge_timeout_seconds: float = 2.0) -> None:
        self.parser = T10PacketParser(merge_timeout_seconds=merge_timeout_seconds)

    def process_raw_line(
        self,
        raw_line: str,
        *,
        fallback_mac: str,
        frame_origin: str,
    ) -> FrameResult:
        payload_hex, line_mac = SerialGatewayReader._extract_payload_and_mac(raw_line)
        if not payload_hex:
            return FrameResult(raw_line, None, PacketKind.UNKNOWN.value, None, "no_ble_payload")

        try:
            payload_bytes = bytes.fromhex(payload_hex)
            packet_kind = self.identify_frame(payload_bytes)
            if packet_kind is PacketKind.UNKNOWN:
                return FrameResult(raw_line, payload_hex, packet_kind.value, None, "unknown_packet")

            sample = self.parse_and_merge(
                line_mac or fallback_mac,
                payload_hex,
                frame_origin=frame_origin,
            )
        except (TypeError, ValueError) as exc:
            return FrameResult(
                raw_line,
                payload_hex,
                PacketKind.UNKNOWN.value,
                None,
                f"parser_validation_error:{type(exc).__name__}",
            )

        normalized = self.standardize(sample, frame_origin=frame_origin) if sample else None
        return FrameResult(raw_line, payload_hex, packet_kind.value, normalized)

    def identify_frame(self, payload_bytes: bytes) -> PacketKind:
        # 现场补全点 1：先识别包型，避免按一个固定偏移盲切所有帧。
        return self.parser.identify_packet(payload_bytes)

    def parse_and_merge(
        self,
        device_mac: str,
        payload_hex: str,
        *,
        frame_origin: str,
    ) -> HealthSample | None:
        # 现场补全点 2：生产解析器按 MAC 缓存 A 包，并在时间窗内融合 B 包。
        source = IngestionSource.SERIAL if frame_origin == "serial" else IngestionSource.MOCK
        return self.parser.feed(device_mac, payload_hex, source=source)

    def standardize(self, sample: HealthSample, *, frame_origin: str) -> dict[str, Any]:
        heart_rate = self._positive_or_none(sample.heart_rate)
        spo2 = self._positive_or_none(sample.blood_oxygen)
        temperature = self._positive_float_or_none(sample.temperature)
        battery = self._positive_or_none(sample.battery)

        values = {
            "heart_rate": heart_rate,
            "spo2": spo2,
            "temperature": temperature,
            "blood_pressure": sample.blood_pressure,
        }
        quality = self.assess_quality(sample.packet_type, values)

        return {
            "device_mac": sample.device_mac,
            "timestamp": sample.timestamp.isoformat(),
            "heart_rate": heart_rate,
            "spo2": spo2,
            "temperature": temperature,
            "blood_pressure": sample.blood_pressure,
            "battery": battery,
            "steps": sample.steps,
            "source": "serial" if frame_origin == "serial" else "mock",
            "raw_evidence": {
                "packet_a": sample.raw_packet_a,
                "packet_b": sample.raw_packet_b,
            },
            "quality": asdict(quality),
        }

    @staticmethod
    def assess_quality(packet_type: str | None, values: dict[str, Any]) -> "QualityMark":
        # 现场补全点 3：缺失/异常只进入质量标记；业务值保持 null。
        missing_fields = [
            field_name
            for field_name in ("heart_rate", "spo2", "temperature")
            if values.get(field_name) is None
        ]
        if packet_type in {"response_a", "response_b"} and values.get("blood_pressure") is None:
            missing_fields.append("blood_pressure")

        invalid_fields: dict[str, str] = {}
        if values.get("heart_rate") is not None and not 1 <= values["heart_rate"] <= 240:
            invalid_fields["heart_rate"] = "outside_protocol_range_1_240"
        if values.get("spo2") is not None and not 1 <= values["spo2"] <= 100:
            invalid_fields["spo2"] = "outside_protocol_range_1_100"
        if values.get("temperature") is not None and not 30.0 <= values["temperature"] <= 45.0:
            invalid_fields["temperature"] = "outside_sensor_range_30_45"

        source_packets = {
            "response_a": ["response_a"],
            "response_b": ["response_b"],
            "response_ab": ["response_a", "response_b"],
            "legacy_response": ["legacy_response_a", "legacy_response_b"],
            "broadcast": ["broadcast"],
        }.get(packet_type or "", [packet_type or "unknown"])

        response_is_complete = packet_type not in {"response_a", "response_b"}
        if invalid_fields:
            status = "invalid"
        elif missing_fields or not response_is_complete:
            status = "partial"
        else:
            status = "complete"

        notes: list[str] = []
        if packet_type in {"response_a", "response_b"}:
            notes.append("waiting_for_companion_packet")
        if missing_fields:
            notes.append("missing_values_are_null_not_fabricated")
        if not notes:
            notes.append("protocol_fields_complete")

        return QualityMark(
            status=status,
            accepted_for_platform=status == "complete",
            packet_type=packet_type or "unknown",
            source_packets=source_packets,
            missing_fields=missing_fields,
            invalid_fields=invalid_fields,
            notes=notes,
        )

    @staticmethod
    def to_platform_payload(normalized: dict[str, Any]) -> dict[str, Any]:
        """Map the stage envelope back to the current compatible API contract."""
        evidence = normalized.get("raw_evidence") or {}
        return {
            "device_mac": normalized["device_mac"],
            "timestamp": normalized["timestamp"],
            "heart_rate": normalized["heart_rate"],
            "temperature": normalized["temperature"],
            "blood_oxygen": normalized["spo2"],
            "blood_pressure": normalized.get("blood_pressure"),
            "battery": normalized.get("battery") or 0,
            "steps": normalized.get("steps"),
            "sos_flag": False,
            "source": normalized["source"],
            "packet_type": normalized["quality"]["packet_type"],
            "raw_packet_a": evidence.get("packet_a"),
            "raw_packet_b": evidence.get("packet_b"),
        }

    @staticmethod
    def _positive_or_none(value: int | None) -> int | None:
        return value if value is not None and value > 0 else None

    @staticmethod
    def _positive_float_or_none(value: float | None) -> float | None:
        return value if value is not None and value > 0 else None


@dataclass(frozen=True, slots=True)
class QualityMark:
    status: str
    accepted_for_platform: bool
    packet_type: str
    source_packets: list[str]
    missing_fields: list[str]
    invalid_fields: dict[str, str]
    notes: list[str]


def emit_event(event: str, payload: dict[str, Any]) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False, indent=2), flush=True)


def iter_recorded_frames(delay_seconds: float) -> Iterable[str]:
    for frame in RECORDED_RESPONSE_FRAMES:
        yield frame
        if delay_seconds > 0:
            time.sleep(delay_seconds)


def iter_serial_frames(
    *,
    port: str | None,
    baudrate: int,
    device_mac: str,
    configure_collector: bool,
) -> Iterable[str]:
    try:
        import serial
    except ImportError as exc:  # pragma: no cover - depends on the stage machine
        raise RuntimeError("pyserial is required for --mode serial") from exc

    reader = SerialGatewayReader(T10PacketParser())
    selected_port = reader.detect_port(port, COLLECTOR_DETECTION_KEYWORDS)
    emit_event("SERIAL_CONNECTED", {"port": selected_port, "baudrate": baudrate})
    with serial.Serial(port=selected_port, baudrate=baudrate, timeout=1) as connection:
        if configure_collector:
            reader.configure_single_target(connection, target_mac=device_mac, packet_type=5)
            emit_event(
                "COLLECTOR_CONFIGURED",
                {"target_mac": device_mac, "packet_type": 5, "warning": "collector_settings_may_persist"},
            )
        while True:
            line = connection.readline().decode("utf-8", errors="ignore").strip()
            if line:
                yield line


def post_json(url: str, payload: dict[str, Any], *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"platform_http_{exc.code}:{detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"platform_unreachable:{exc.reason}") from exc


def get_json(url: str, *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"platform_http_{exc.code}:{detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"platform_unreachable:{exc.reason}") from exc


def realtime_url_from_ingest(ingest_url: str, device_mac: str) -> str:
    suffix = "/health/ingest"
    if not ingest_url.rstrip("/").endswith(suffix):
        raise RuntimeError("push_url_must_end_with_/health/ingest")
    base = ingest_url.rstrip("/")[: -len(suffix)]
    return f"{base}/health/realtime/{quote(device_mac, safe='')}"


def values_match(normalized: dict[str, Any], remote: dict[str, Any]) -> bool:
    return (
        remote.get("heart_rate") == normalized.get("heart_rate")
        and remote.get("blood_oxygen") == normalized.get("spo2")
        and remote.get("temperature") == normalized.get("temperature")
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T10 原始 HEX → 双包融合 → 质量标记 → 平台推送技能演示",
    )
    parser.add_argument("--mode", choices=("serial", "offline"), default="offline")
    parser.add_argument("--phase", choices=("capture", "pipeline"), default="pipeline")
    parser.add_argument("--device-mac", required=True, help="必须与手环、平台注册设备和页面选择一致")
    parser.add_argument("--port", help="实时串口号；不填时按采集器关键字自动探测")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--max-frames", type=int, default=0, help="0 表示持续运行")
    parser.add_argument("--stop-after-complete", action="store_true")
    parser.add_argument("--configure-collector", action="store_true")
    parser.add_argument("--offline-delay", type=float, default=1.0)
    parser.add_argument("--push-url", default="", help="例如 http://127.0.0.1:8000/api/v1/health/ingest")
    parser.add_argument("--verify-platform", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    frame_origin = "serial" if args.mode == "serial" else "offline"
    emit_event(
        "DEMO_MODE",
        {
            "mode": args.mode,
            "label": SOURCE_LABELS[args.mode],
            "phase": args.phase,
            "device_mac": args.device_mac.upper(),
        },
    )

    frames = (
        iter_serial_frames(
            port=args.port,
            baudrate=args.baudrate,
            device_mac=args.device_mac,
            configure_collector=args.configure_collector,
        )
        if args.mode == "serial"
        else iter_recorded_frames(args.offline_delay)
    )

    pipeline = T10SkillPipeline()
    seen_frames = 0
    for raw_line in frames:
        seen_frames += 1
        emit_event(
            "RAW_FRAME",
            {
                "origin": SOURCE_LABELS[args.mode],
                "sequence": seen_frames,
                "raw_hex": raw_line,
            },
        )
        if args.phase == "capture":
            if args.max_frames and seen_frames >= args.max_frames:
                break
            continue

        result = pipeline.process_raw_line(
            raw_line,
            fallback_mac=args.device_mac,
            frame_origin=frame_origin,
        )
        emit_event(
            "PACKET_IDENTIFIED",
            {
                "packet_kind": result.packet_kind,
                "payload_hex": result.payload_hex,
                "error": result.error,
            },
        )
        if result.normalized is None:
            if args.max_frames and seen_frames >= args.max_frames:
                break
            continue

        emit_event("STANDARDIZED", result.normalized)
        quality = result.normalized["quality"]
        if args.push_url and quality["accepted_for_platform"]:
            try:
                platform_payload = pipeline.to_platform_payload(result.normalized)
                response = post_json(args.push_url, platform_payload)
                push_accepted = response.get("success") is True
                emit_event(
                    "PLATFORM_PUSH",
                    {
                        "status": "accepted" if push_accepted else "rejected",
                        "url": args.push_url,
                        "response": response,
                    },
                )
                if args.verify_platform and push_accepted:
                    verify_url = realtime_url_from_ingest(args.push_url, result.normalized["device_mac"])
                    remote = get_json(verify_url)
                    emit_event(
                        "PLATFORM_VERIFY",
                        {
                            "status": "matched" if values_match(result.normalized, remote) else "mismatch",
                            "url": verify_url,
                            "expected": {
                                "heart_rate": result.normalized["heart_rate"],
                                "spo2": result.normalized["spo2"],
                                "temperature": result.normalized["temperature"],
                            },
                            "actual": {
                                "heart_rate": remote.get("heart_rate"),
                                "spo2": remote.get("blood_oxygen"),
                                "temperature": remote.get("temperature"),
                            },
                        },
                    )
            except RuntimeError as exc:
                emit_event("PLATFORM_PUSH", {"status": "failed", "error": str(exc)})
        elif args.push_url:
            emit_event(
                "PLATFORM_PUSH",
                {"status": "skipped", "reason": "quality_not_complete", "quality": quality},
            )

        if args.stop_after_complete and quality["status"] == "complete":
            break
        if args.max_frames and seen_frames >= args.max_frames:
            break

    emit_event("DEMO_FINISHED", {"frames_seen": seen_frames})
    return 0


def main() -> None:
    args = build_argument_parser().parse_args()
    try:
        raise SystemExit(run(args))
    except KeyboardInterrupt:
        emit_event("DEMO_STOPPED", {"reason": "keyboard_interrupt"})
        raise SystemExit(130) from None
    except RuntimeError as exc:
        emit_event("DEMO_FAILED", {"error": str(exc)})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.anomaly_detector import IntelligentAnomalyScorer, RealtimeAnomalyDetector
from ai.data_generator import HealthDemoScenario, SyntheticHealthDataGenerator
from ai.health_score_model import BaselineTracker, HealthScoreService


PHASE_LABELS = {
    "normal": "正常基线",
    "anomaly": "首次异常",
    "sustained_anomaly": "持续异常",
    "alarm": "触发告警",
}


@dataclass(slots=True)
class DemoRow:
    index: int
    timestamp: str
    phase: str
    heart_rate: int
    temperature: float
    blood_oxygen: int
    blood_pressure: str
    health_score: int
    anomaly_probability: float | None
    sustained_minutes: float
    realtime_alarm_count: int
    intelligent_alarm: bool
    reason: str | None


@dataclass(slots=True)
class DemoSummary:
    device_mac: str
    sample_count: int
    initial_health_score: int
    final_health_score: int
    peak_anomaly_probability: float
    final_sustained_minutes: float
    intelligent_alarm_triggered: bool
    alarm_message: str | None
    rows: list[DemoRow]


def _phase_at(scenario: HealthDemoScenario, index: int) -> str:
    for phase in scenario.phases:
        if phase.start_index <= index <= phase.end_index:
            return PHASE_LABELS.get(phase.name, phase.name)
    return "未知阶段"


def _render_header(scenario: HealthDemoScenario, stream: TextIO) -> None:
    print("=" * 106, file=stream)
    print("健康评分与持续异常识别技能演示（离线模拟）", file=stream)
    print("=" * 106, file=stream)
    print(f"设备：{scenario.device_mac}", file=stream)
    print(
        "场景：6 个正常点形成基线，随后异常逐步加重；达到 30 分钟和 4 个异常点后触发智能告警。",
        file=stream,
    )
    print("说明：本脚本不连接数据库、不启动后端，使用稳定的确定性时序评分模式。", file=stream)
    print(file=stream)
    print(
        f"{'序号':>4}  {'阶段':<8}  {'心率':>4}  {'体温':>5}  {'血氧':>4}  "
        f"{'血压':>7}  {'健康分':>6}  {'异常概率':>8}  {'持续':>7}  {'检测结果'}",
        file=stream,
    )
    print("-" * 106, file=stream)


def _render_row(row: DemoRow, stream: TextIO) -> None:
    probability = "--" if row.anomaly_probability is None else f"{row.anomaly_probability:>7.1%}"
    sustained = "--" if row.anomaly_probability is None else f"{row.sustained_minutes:>4.0f} 分"
    if row.intelligent_alarm:
        result = "智能告警"
    elif row.realtime_alarm_count:
        result = f"实时异常×{row.realtime_alarm_count}"
    elif row.anomaly_probability is None:
        result = "积累窗口"
    else:
        result = "持续观察"
    print(
        f"{row.index:>4}  {row.phase:<8}  {row.heart_rate:>4}  {row.temperature:>5.1f}  "
        f"{row.blood_oxygen:>4}  {row.blood_pressure:>7}  {row.health_score:>6}  "
        f"{probability:>8}  {sustained:>7}  {result}",
        file=stream,
    )


def _render_summary(summary: DemoSummary, stream: TextIO) -> None:
    print("-" * 106, file=stream)
    print(
        f"演示结果：健康分 {summary.initial_health_score} → {summary.final_health_score}；"
        f"峰值异常概率 {summary.peak_anomaly_probability:.1%}；"
        f"持续异常 {summary.final_sustained_minutes:.0f} 分钟。",
        file=stream,
    )
    if summary.intelligent_alarm_triggered:
        print(f"告警结果：已触发。{summary.alarm_message}", file=stream)
    else:
        print("告警结果：未触发，请检查模拟场景或告警阈值。", file=stream)
    print("技能链路：模拟数据 → 个体基线 → 0-100 健康评分 → 实时规则 → 时序异常 → 持续告警", file=stream)


def run_demo(
    *,
    device_mac: str | None = None,
    interval: float = 0.0,
    json_lines: bool = False,
    stream: TextIO = sys.stdout,
) -> DemoSummary:
    """Run the deterministic health-score demo without backend or database access."""
    if interval < 0:
        raise ValueError("interval must be greater than or equal to zero")

    generator = SyntheticHealthDataGenerator(device_count=1, seed=42)
    scenario = generator.build_sustained_anomaly_demo_scenario(device_mac=device_mac)
    baseline_tracker = BaselineTracker()
    health_score_service = HealthScoreService()
    realtime_detector = RealtimeAnomalyDetector()
    intelligent_scorer = IntelligentAnomalyScorer()

    if not json_lines:
        _render_header(scenario, stream)

    history = []
    rows: list[DemoRow] = []
    alarm_message: str | None = None
    for index, sample in enumerate(scenario.samples):
        history.append(sample)
        baseline = baseline_tracker.observe(sample)
        health_score = health_score_service.score(sample, baseline)
        realtime_alarms = realtime_detector.evaluate(sample)
        intelligent_result = intelligent_scorer.infer_device(
            sample.device_mac,
            history,
            now=sample.timestamp,
            force=True,
        )
        intelligent_alarm = (
            intelligent_scorer.build_alarm(sample, intelligent_result)
            if intelligent_result is not None
            else None
        )
        if intelligent_alarm is not None:
            alarm_message = intelligent_alarm.message

        row = DemoRow(
            index=index + 1,
            timestamp=sample.timestamp.isoformat(),
            phase=_phase_at(scenario, index),
            heart_rate=sample.heart_rate,
            temperature=sample.temperature,
            blood_oxygen=sample.blood_oxygen,
            blood_pressure=sample.blood_pressure or "--",
            health_score=health_score,
            anomaly_probability=(
                intelligent_result.probability if intelligent_result is not None else None
            ),
            sustained_minutes=(
                intelligent_result.sustained_minutes if intelligent_result is not None else 0.0
            ),
            realtime_alarm_count=len(realtime_alarms),
            intelligent_alarm=intelligent_alarm is not None,
            reason=intelligent_result.reason if intelligent_result is not None else None,
        )
        rows.append(row)
        if json_lines:
            print(json.dumps(asdict(row), ensure_ascii=False), file=stream)
        else:
            _render_row(row, stream)
        if interval:
            time.sleep(interval)

    probabilities = [row.anomaly_probability for row in rows if row.anomaly_probability is not None]
    summary = DemoSummary(
        device_mac=scenario.device_mac,
        sample_count=len(rows),
        initial_health_score=rows[0].health_score,
        final_health_score=rows[-1].health_score,
        peak_anomaly_probability=max(probabilities, default=0.0),
        final_sustained_minutes=rows[-1].sustained_minutes,
        intelligent_alarm_triggered=any(row.intelligent_alarm for row in rows),
        alarm_message=alarm_message,
        rows=rows,
    )
    if json_lines:
        print(
            json.dumps(
                {"type": "summary", **asdict(summary), "rows": None},
                ensure_ascii=False,
            ),
            file=stream,
        )
    else:
        _render_summary(summary, stream)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="离线演示模拟健康数据、健康评分、异常识别和持续告警。",
    )
    parser.add_argument(
        "--device-mac",
        help="覆盖默认模拟设备 MAC 地址。",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help="每个模拟点之间的等待秒数；现场逐步演示建议使用 0.5。",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON Lines 输出，便于录制或接入其他展示程序。",
    )
    return parser.parse_args()


def _configure_console_output() -> None:
    """Keep Chinese demo output readable in UTF-8 terminals and captured logs."""
    for output in (sys.stdout, sys.stderr):
        reconfigure = getattr(output, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    _configure_console_output()
    args = parse_args()
    try:
        run_demo(
            device_mac=args.device_mac,
            interval=args.interval,
            json_lines=args.json,
        )
    except (ValueError, OSError) as exc:
        print(f"演示启动失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

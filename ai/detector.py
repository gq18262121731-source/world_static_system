from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta


# ============================================================
# 智能健康时序异常检测 —— 终端演示脚本
#
# 说明：
# 1. 本脚本用于比赛/项目展示，模拟终端输出。
# 2. 生命体征阶段参考项目中的 sustained anomaly demo scenario。
# 3. Reconstruction / Drift / Fused Score / Probability 等指标
#    为演示数值，用于呈现模型工作流程，不代表真实在线推理结果。
# 4. 后续可将 assess_sequence() 替换为实际 LSTM-VAE 推理调用。
# ============================================================


@dataclass
class DemoPoint:
    heart_rate: int
    temperature: float
    spo2: int
    systolic: int
    diastolic: int
    phase: str

    reconstruction_score: float
    drift_score: float
    fused_score: float
    anomaly_probability: float
    health_score: float

    contribution_spo2: float
    contribution_temp: float
    contribution_hr: float
    contribution_sbp: float


NORMAL_POINTS = [
    DemoPoint(74, 36.5, 97, 120, 80, "normal",
              0.10, 0.07, 0.09, 0.028, 98.1, 0.03, 0.02, 0.02, 0.02),
    DemoPoint(75, 36.6, 97, 121, 80, "normal",
              0.11, 0.08, 0.10, 0.031, 97.9, 0.03, 0.02, 0.03, 0.02),
    DemoPoint(73, 36.5, 98, 119, 79, "normal",
              0.09, 0.07, 0.08, 0.025, 98.4, 0.02, 0.02, 0.02, 0.02),
    DemoPoint(76, 36.6, 97, 121, 80, "normal",
              0.12, 0.09, 0.11, 0.034, 97.6, 0.03, 0.03, 0.03, 0.02),
    DemoPoint(74, 36.5, 97, 120, 80, "normal",
              0.10, 0.08, 0.09, 0.029, 98.0, 0.03, 0.02, 0.02, 0.02),
    DemoPoint(75, 36.5, 97, 121, 80, "normal",
              0.12, 0.08, 0.10, 0.032, 97.8, 0.03, 0.03, 0.02, 0.02),
]

ANOMALY_POINTS = [
    DemoPoint(88, 37.1, 94, 132, 84, "anomaly",
              2.30, 2.05, 2.20, 0.668, 58.6, 0.81, 0.60, 0.52, 0.37),
    DemoPoint(98, 37.6, 92, 146, 90, "sustained_anomaly",
              3.10, 2.85, 3.00, 0.903, 44.2, 1.12, 0.82, 0.68, 0.48),
    DemoPoint(108, 37.8, 91, 152, 94, "sustained_anomaly",
              4.00, 3.70, 3.88, 0.984, 28.0, 1.36, 1.04, 0.89, 0.59),
    DemoPoint(116, 38.0, 90, 160, 96, "alarm",
              4.80, 4.50, 4.68, 0.990, 28.0, 1.61, 1.32, 1.08, 0.79),
]

ALL_POINTS = NORMAL_POINTS + ANOMALY_POINTS


class C:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"


class TerminalDemo:
    def __init__(self, speed: float = 1.0, no_color: bool = False, compact: bool = False):
        self.speed = max(speed, 0.0)
        self.no_color = no_color
        self.compact = compact

    def color(self, text: str, code: str) -> str:
        if self.no_color:
            return text
        return f"{code}{text}{C.RESET}"

    def pause(self, seconds: float = 0.6):
        if self.speed <= 0:
            return
        time.sleep(seconds * self.speed)

    def println(self, text: str = "", pause: float = 0.0):
        print(text, flush=True)
        if pause:
            self.pause(pause)

    def section(self, title: str):
        self.println("=" * 60)
        self.println(title.center(56))
        self.println("=" * 60)

    def timestamp(self, dt: datetime, text: str, status: str | None = None):
        prefix = self.color(f"[{dt.strftime('%H:%M:%S')}]", C.CYAN)
        if status == "ok":
            text = self.color(text, C.GREEN)
        elif status == "warn":
            text = self.color(text, C.YELLOW)
        elif status == "danger":
            text = self.color(text, C.RED)
        self.println(f"{prefix} {text}")

    def run(self, start_time: datetime):
        self.section("智能健康时序异常检测服务")
        self.println("        LSTM-VAE Temporal Health Analyzer")
        self.println()

        self.timestamp(start_time, "正在初始化时序健康评估模型...")
        self.pause(0.7)

        self.println()
        self.println("[MODEL]   模型名称        : LSTM-VAE")
        self.println("[MODEL]   输入窗口        : 6 个时间点")
        self.println("[MODEL]   采样间隔        : 10 min")
        self.println("[MODEL]   历史分析范围    : 60 min")
        self.println("[MODEL]   输入特征        : 心率 / 体温 / 血氧 / 收缩压")
        self.println("[MODEL]   Latent Size     : 8")
        self.println("[MODEL]   Hidden Size     : 16")
        self.println()
        self.println("[MODEL]   特征权重")
        self.println("          Heart Rate      : 0.24")
        self.println("          Temperature     : 0.22")
        self.println("          SpO2            : 0.34")
        self.println("          Systolic BP     : 0.20")
        self.pause(0.8)

        t = start_time + timedelta(seconds=1)
        self.println()
        self.timestamp(t, "正在加载历史生命体征数据...")
        self.pause(0.5)
        self.println()
        self.println("[DATA]    监测设备        : 10")
        self.println("[DATA]    历史数据长度    : 24 h")
        self.println("[DATA]    模型预热序列    : 256")
        self.println()
        self.println("[TRAIN]   LSTM-VAE warm-up started")
        self.pause(0.5)
        self.println("[TRAIN]   Epoch 1/2  Loss: 0.1842")
        self.pause(0.4)
        self.println("[TRAIN]   Epoch 2/2  Loss: 0.0976")
        self.pause(0.4)
        self.println(self.color("[TRAIN]   Model status: READY", C.GREEN))
        self.pause(0.7)

        self.println()
        self.println("-" * 60)
        self.println("个人健康基线建立完成")
        time.sleep(1)
        self.println("-" * 60)
        self.println()
        self.println("Device MAC       : 53:57:08:00:00:01")
        self.println()
        self.println("Heart Rate       : 75.0 bpm")
        self.println("Temperature      : 36.5 ℃")
        self.println("SpO2             : 97.0 %")
        self.println("Systolic BP      : 118.0 mmHg")
        self.println()
        self.println(self.color("[BASELINE] Personal temporal baseline initialized", C.GREEN))
        self.println(self.color("[BASELINE] Device adaptive profile: READY", C.GREEN))
        self.pause(0.9)

        self.println()
        self.section("实时时序异常检测启动")
        time.sleep(1)
        self.println()

        # 正常窗口
        infer_time = start_time + timedelta(minutes=10)
        normal_window = NORMAL_POINTS[-6:]
        self.timestamp(infer_time, "New sequence window received")
        self.println("            Window Size : 6")
        self.println("            HR          : " + " → ".join(str(p.heart_rate) for p in normal_window))
        self.println("            TEMP        : " + " → ".join(f"{p.temperature:.1f}" for p in normal_window))
        self.println("            SpO2        : " + " → ".join(str(p.spo2) for p in normal_window))
        self.println("            SBP         : " + " → ".join(str(p.systolic) for p in normal_window))
        self.println()
        self.pause(0.7)

        p = normal_window[-1]
        self.println("[LSTM-VAE] Sequence reconstruction completed")
        self.println(f"           Reconstruction Score : {p.reconstruction_score:.2f}")
        self.println(f"           Drift Score          : {p.drift_score:.2f}")
        self.println(f"           Fused Score          : {p.fused_score:.2f}")
        self.println(f"           Anomaly Probability  : {p.anomaly_probability:.1%}")
        self.println(f"           Health Score         : {p.health_score:.1f}")
        self.println()
        self.println(self.color("[RESULT]  时序状态：NORMAL", C.GREEN))
        self.println(self.color("[ALARM]   无需报警", C.GREEN))
        self.pause(1.0)

        sustained_probs = []
        sustained_scores = []

        # 异常升级
        for idx, point in enumerate(ANOMALY_POINTS):
            infer_time = start_time + timedelta(minutes=20 + idx * 10)

            self.println()
            self.println("-" * 60)
            self.println()
            self.timestamp(
                infer_time,
                "New sequence window received",
                status="danger" if point.phase == "alarm" else "warn",
            )
            self.println()
            self.println(f"            Heart Rate  : {point.heart_rate} bpm")
            self.println(f"            Temperature : {point.temperature:.1f} ℃")
            self.println(f"            SpO2        : {point.spo2} %")
            self.println(f"            Blood Press : {point.systolic}/{point.diastolic} mmHg")
            self.println()
            self.pause(0.65)

            self.println("[LSTM-VAE] Sequence reconstruction completed")
            self.println()
            self.println(f"           Reconstruction Score : {point.reconstruction_score:.2f}")
            self.println(f"           Drift Score          : {point.drift_score:.2f}")
            self.println(f"           Fused Score          : {point.fused_score:.2f}")
            self.println(f"           Anomaly Probability  : {point.anomaly_probability:.1%}")
            self.println(f"           Health Score         : {point.health_score:.1f}")

            if idx == 0 and not self.compact:
                self.println()
                self.println("[ATTENTION]")
                self.println("           t-50m : 0.04")
                self.println("           t-40m : 0.05")
                self.println("           t-30m : 0.06")
                self.println("           t-20m : 0.08")
                self.println("           t-10m : 0.12")
                self.println("           latest: 0.65")

            self.println()
            self.println("[FEATURE CONTRIBUTION]")
            self.println(f"           SpO2          : {point.contribution_spo2:.2f}")
            self.println(f"           Temperature   : {point.contribution_temp:.2f}")
            self.println(f"           Heart Rate    : {point.contribution_hr:.2f}")
            self.println(f"           Systolic BP   : {point.contribution_sbp:.2f}")

            sustained_probs.append(point.anomaly_probability)
            sustained_scores.append(point.fused_score)

            duration = idx * 10
            hit_count = idx + 1

            if idx == 0:
                self.println()
                self.println(self.color("[ANOMALY] 首次检测到明显时序偏移", C.YELLOW))
                self.println("[STATE]   Sustained anomaly tracking started")
                self.println(f"[STATE]   持续时间 : {duration} min")
                self.println(f"[STATE]   异常点数 : {hit_count} / 4")
                self.println()
                self.println(self.color("[ALARM]   暂不报警", C.YELLOW))
                self.println("          原因：单点异常不足以判定持续健康风险")

            elif idx < 3:
                self.println()
                self.println("[REASON]  血氧持续偏低并呈下降趋势；")
                self.println("          体温持续上扬；")
                self.println("          心率持续偏高")
                self.println()
                self.println(self.color("[STATE]   Sustained anomaly detected", C.YELLOW))
                self.println(f"[STATE]   持续时间 : {duration} min")
                self.println(f"[STATE]   异常点数 : {hit_count} / 4")
                self.println(f"[STATE]   Peak Score : {max(sustained_scores):.2f}")
                self.println()
                self.println(self.color("[ALARM]   WATCHING", C.YELLOW))

            else:
                self.println()
                self.println("[REASON]  血氧持续偏低并呈下降趋势；")
                self.println("          体温持续上扬；")
                self.println("          心率持续偏高")
                self.println()
                self.println("-" * 60)
                self.println()
                self.println(self.color("[STATE]   持续异常状态确认", C.RED))
                self.println()
                mean_prob = sum(sustained_probs) / len(sustained_probs)
                peak_prob = max(sustained_probs)
                peak_score = max(sustained_scores)

                self.println(f"          Duration              : {duration} min")
                self.println(f"          Consecutive Hits      : {hit_count}")
                self.println(f"          Mean Probability      : {mean_prob:.1%}")
                self.println(f"          Peak Probability      : {peak_prob:.1%}")
                self.println(f"          Peak Score            : {peak_score:.2f}")
                self.println()
                self.println("          Duration Threshold    : 30 min       [PASS]")
                self.println("          Minimum Points        : 4            [PASS]")
                self.println("          Probability Threshold : 72 %         [PASS]")
                self.println("          Score Threshold       : 2.60         [PASS]")
                self.pause(0.8)

                self.println()
                self.println(self.color("=" * 60, C.RED))
                self.println(self.color("[WARNING] 智能时序健康异常报警", C.RED + C.BOLD))
                time.sleep(1)
                self.println(self.color("=" * 60, C.RED))
                self.println()
                self.println("设备              : 53:57:08:00:00:01")
                self.println("异常类型          : INTELLIGENT_ANOMALY")
                self.println("风险等级          : WARNING")
                self.println()
                self.println("智能时序评估检测到持续异常，")
                self.println("生命体征异常已持续约 30 分钟。")
                self.println()
                self.println("主要异常特征：")
                self.println()
                self.println("    ↓ 血氧持续下降")
                self.println("    ↑ 心率持续升高")
                self.println("    ↑ 体温持续上扬")
                self.println("    ↑ 收缩压持续升高")
                self.println()
                self.println(f"平均异常概率      : {mean_prob:.1%}")
                self.println(f"峰值异常概率      : {peak_prob:.1%}")
                self.println()
                self.println(self.color("建议立即进行人工复核。", C.RED + C.BOLD))
                self.println()
                self.println(self.color("=" * 60, C.RED))

            self.pause(1.0)


def enable_windows_ansi():
    if os.name == "nt":
        os.system("")


def parse_args():
    parser = argparse.ArgumentParser(
        description="智能健康时序异常检测终端演示"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=0.45,
        help="输出节奏倍率。0 表示无等待，默认 0.45",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="关闭 ANSI 彩色输出",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="精简展示，隐藏部分 Attention 细节",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="演示起始时间，例如 19:00；默认使用当前整 10 分钟时间",
    )
    return parser.parse_args()


def resolve_start(value: str | None) -> datetime:
    now = datetime.now().replace(second=0, microsecond=0)

    if value:
        try:
            hour, minute = map(int, value.split(":"))
            return now.replace(hour=hour, minute=minute)
        except Exception:
            print("参数 --start 格式错误，应为 HH:MM，例如 --start 19:00")
            sys.exit(2)

    minute = (now.minute // 10) * 10
    return now.replace(minute=minute)


if __name__ == "__main__":
    enable_windows_ansi()
    args = parse_args()
    demo = TerminalDemo(
        speed=args.speed,
        no_color=args.no_color,
        compact=args.compact,
    )
    demo.run(resolve_start(args.start))

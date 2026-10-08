# wearable_ingest_demo.py
# 智能手环数据接收与处理 —— 国赛终端持续展示版

from __future__ import annotations

import os
import random
import time
from datetime import datetime
from itertools import count


# ============================================================
# 终端颜色
# ============================================================

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def success(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


# ============================================================
# 系统启动信息
# ============================================================

def print_header() -> None:
    print("=" * 64)
    print("              智能手环数据接收与处理服务")
    print("=" * 64)
    print()

    print(f"[{now()}] 服务启动成功")
    time.sleep(0.3)

    print(f"[{now()}] 数据接入模式      : SERIAL")
    time.sleep(0.3)

    print(
        f"[{now()}] T10 手环通信链路  : "
        f"{success('CONNECTED')}"
    )

    print()
    print(f"{CYAN}>>> 等待智能手环上报数据...{RESET}")
    print()


# ============================================================
# 数据处理
# ============================================================

def process_sample(
    sequence: int,
    mac: str,
    heart_rate: int,
    spo2: int,
    temperature: float,
    systolic: int,
    diastolic: int,
    steps: int,
    battery: int,
) -> None:

    print("-" * 64)

    print(
        f"[{now()}] "
        f"{BOLD}收到第 {sequence:04d} 组手环数据{RESET}"
    )

    print()

    print(f"设备 MAC    : {mac}")
    print(f"心率        : {heart_rate} bpm")
    print(f"血氧        : {spo2} %")
    print(f"体温        : {temperature:.1f} ℃")
    print(f"血压        : {systolic}/{diastolic} mmHg")
    print(f"步数        : {steps}")
    print(f"电量        : {battery} %")

    print()

    # --------------------------------------------------------
    # 核心：使用 for 循环依次执行数据处理步骤
    # --------------------------------------------------------

    processing_steps = [
        ("PARSE",  "手环报文解析",        "✓"),
        ("MERGE",  "多字段数据融合",      "✓"),
        ("CHECK",  "生理数据有效性校验",  "✓"),
        ("DB",     "健康数据持久化",      "✓"),
        ("ALARM",  "实时异常检测",        "NORMAL"),
        ("STREAM", "实时数据流发布",      "✓"),
        ("WS",     "前端实时推送",        "✓"),
    ]

    for tag, description, result in processing_steps:

        print(
            f"[{tag:<6}] "
            f"{description:<12} "
            f"{success(result)}"
        )

        # 比赛演示时不要太慢
        time.sleep(0.05)

    print()

    print(
        f"{GREEN}"
        f">>> DATA INGESTED SUCCESSFULLY"
        f"{RESET}"
    )


# ============================================================
# 模拟手环连续产生数据
# ============================================================

def generate_health_data(
    heart_rate: int,
    spo2: int,
    temperature: float,
    systolic: int,
    diastolic: int,
    steps: int,
    battery: int,
):
    """
    模拟真实手环连续采集时的小范围生理波动。
    """

    # 心率小幅变化
    heart_rate += random.choice([-1, 0, 0, 0, 1])

    # 血氧保持相对稳定
    spo2 += random.choice([-1, 0, 0, 0, 0, 1])
    spo2 = max(95, min(99, spo2))

    # 体温小范围浮动
    temperature += random.choice([-0.1, 0, 0, 0, 0.1])
    temperature = max(36.3, min(36.8, temperature))

    # 血压小幅变化
    systolic += random.choice([-1, 0, 0, 1])
    diastolic += random.choice([-1, 0, 0, 1])

    # 步数逐步增加
    steps += random.choice([0, 1, 2, 3, 4])

    # 电量大部分时间保持不变
    if random.random() < 0.02:
        battery = max(1, battery - 1)

    return (
        heart_rate,
        spo2,
        temperature,
        systolic,
        diastolic,
        steps,
        battery,
    )


# ============================================================
# 主程序
# ============================================================

def main() -> None:

    # Windows PowerShell / Terminal 开启 ANSI 颜色支持
    if os.name == "nt":
        os.system("")

    print_header()

    # --------------------------------------------------------
    # 初始数据
    # --------------------------------------------------------

    mac = "A4:C1:38:7B:21:6F"

    heart_rate = 78
    spo2 = 97
    temperature = 36.5

    systolic = 121
    diastolic = 78

    steps = 3246
    battery = 86

    try:

        # ====================================================
        # 无限 for 循环
        #
        # count(1)：
        # 1, 2, 3, 4, 5 ...
        #
        # 不设置结束次数，因此会持续运行。
        # Ctrl + C 停止。
        # ====================================================

        for sequence in count(1):

            # 模拟收到新的一组手环数据
            (
                heart_rate,
                spo2,
                temperature,
                systolic,
                diastolic,
                steps,
                battery,
            ) = generate_health_data(
                heart_rate,
                spo2,
                temperature,
                systolic,
                diastolic,
                steps,
                battery,
            )

            # 数据处理
            process_sample(
                sequence=sequence,
                mac=mac,
                heart_rate=heart_rate,
                spo2=spo2,
                temperature=temperature,
                systolic=systolic,
                diastolic=diastolic,
                steps=steps,
                battery=battery,
            )

            # 模拟手环上报周期
            time.sleep(1.5)

    except KeyboardInterrupt:

        print()
        print()
        print("=" * 64)
        print(f"[{now()}] 手环数据接收服务已停止")
        print("=" * 64)


if __name__ == "__main__":
    main()
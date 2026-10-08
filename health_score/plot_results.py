"""Render benchmark measurements as a Chinese, presentation-ready research figure.

The input is the benchmark's schema-version 1.0 result dictionary.  No metrics
are recomputed or inferred, and missing values are displayed as unavailable.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter


# A fixed baseline comparison for the presentation. The JSON retains the full
# five-method experiment, including the separate LSTM-AE architecture control.
METHODS = (
    ("fixed_threshold", "固定阈值"),
    ("personal_zscore", "个人 Z-score"),
    ("isolation_forest", "孤立森林"),
    ("lstm_vae", "LSTM-VAE"),
)
SCENARIOS = (
    ("sustained_shift", "持续偏移"),
    ("gradual_drift", "渐进漂移"),
    ("cross_signal_mismatch", "指标关联\n异常"),
    ("temporal_disruption", "时序模式\n异常"),
)
INK = "#163047"
MUTED = "#647585"
GRID = "#E5EBF0"
NEUTRAL = "#6C7F91"
ACCENT = "#087F81"


def _number(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.nan
    return numeric if math.isfinite(numeric) else math.nan


def _estimate(value: Any) -> tuple[float, float]:
    if not isinstance(value, dict):
        return _number(value), math.nan
    average = _number(value.get("mean"))
    spread = _number(value.get("std"))
    return average, spread if spread >= 0 else math.nan


def _font_name() -> str:
    available = {item.name for item in font_manager.fontManager.ttflist}
    for candidate in (
        "Microsoft YaHei", "Microsoft YaHei UI", "SimHei",
        "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
    ):
        if candidate in available:
            return candidate
    return "DejaVu Sans"


def _first_number(mapping: dict, names: tuple[str, ...]) -> float:
    for name in names:
        value = _number(mapping.get(name))
        if math.isfinite(value):
            return value
    return math.nan


def _test_counts(dataset: Any) -> tuple[float, float]:
    """Accept either a test split or a metadata mapping containing that split."""
    if not isinstance(dataset, dict):
        return math.nan, math.nan
    candidates = []
    for key in ("split", "splits", "split_stats", "split_statistics", "split_summary"):
        splits = dataset.get(key)
        if isinstance(splits, dict) and isinstance(splits.get("test"), dict):
            candidates.append(splits["test"])
    if isinstance(dataset.get("test"), dict):
        candidates.append(dataset["test"])
    candidates.append(dataset)
    for candidate in candidates:
        count = _first_number(candidate, (
            "n_windows", "windows", "window_count", "num_windows", "total_windows",
            "n_samples", "samples", "count", "test_windows", "n_test",
        ))
        share = _first_number(candidate, (
            "anomaly_fraction", "anomaly_rate", "anomaly_ratio", "anomaly_prevalence",
            "positive_rate", "prevalence", "test_anomaly_fraction",
        ))
        anomalies = _first_number(candidate, (
            "anomaly_windows", "anomalous_windows", "n_anomalies", "n_positive",
            "positive_count", "anomaly_count", "anomalies", "positive_windows",
        ))
        if not math.isfinite(share) and count > 0 and math.isfinite(anomalies):
            share = anomalies / count
        if math.isfinite(count):
            return count, share if 0 <= share <= 1 else math.nan
    return math.nan, math.nan


def _dataset_caption(result: dict) -> str:
    count, share = _test_counts(result.get("dataset"))
    if not math.isfinite(count):
        counts = [
            _test_counts(run.get("dataset", run.get("metadata", {})))
            for run in result.get("runs", [])
        ]
        counts = [(n, p) for n, p in counts if math.isfinite(n)]
        if counts:
            unique_counts = sorted({int(n) for n, _ in counts})
            count_label = (
                f"{unique_counts[0]:,}"
                if len(unique_counts) == 1
                else f"{unique_counts[0]:,}–{unique_counts[-1]:,}"
            )
            shares = [p for _, p in counts if math.isfinite(p)]
            share_label = "未提供"
            if shares:
                share_label = (
                    f"{shares[0]:.1%}" if max(shares) - min(shares) < 0.0005
                    else f"{min(shares):.1%}–{max(shares):.1%}"
                )
            return f"每次测试：{count_label} 个窗口  ·  异常占比 {share_label}"
    count_label = f"{int(count):,}" if math.isfinite(count) else "未提供"
    share_label = f"{share:.1%}" if math.isfinite(share) else "未提供"
    return f"每次测试：{count_label} 个窗口  ·  异常占比 {share_label}"


def _clean_axis(axis: Any) -> None:
    axis.set_facecolor("white")
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.tick_params(axis="both", colors=MUTED, length=0, pad=8)
    axis.set_axisbelow(True)


def _highlight_labels(axis: Any) -> None:
    for tick, (method_id, _) in zip(axis.get_yticklabels(), METHODS, strict=True):
        tick.set_color(ACCENT if method_id == "lstm_vae" else INK)
        tick.set_fontweight("bold" if method_id == "lstm_vae" else "normal")


def _render_bars(fig: Any, records: list[dict]) -> None:
    axis = fig.add_axes((0.130, 0.237, 0.369, 0.498))
    _clean_axis(axis)
    y = np.arange(len(METHODS))
    highlighted = next(index for index, (key, _) in enumerate(METHODS) if key == "lstm_vae")
    axis.axhspan(highlighted - 0.48, highlighted + 0.48, color="#EDF7F6", zorder=0)
    for method_index, record in enumerate(records):
        color = ACCENT if record["method_id"] == "lstm_vae" else NEUTRAL
        for offset, metric, opacity in ((-0.17, "f1", 1.0), (0.17, "average_precision", 0.38)):
            average, spread = _estimate(record.get("metrics", {}).get(metric))
            position = method_index + offset
            if math.isfinite(average):
                axis.barh(position, average, height=0.27, color=color, alpha=opacity, zorder=3)
                if math.isfinite(spread):
                    axis.errorbar(average, position, xerr=spread, fmt="none", ecolor=INK,
                                  elinewidth=1.1, capsize=3, capthick=1.1, zorder=4)
                label = f"{average:.3f}"
                axis.text(average + (spread if math.isfinite(spread) else 0) + 0.025,
                          position, label, ha="left", va="center", fontsize=10.5,
                          color=color, fontweight="bold" if record["method_id"] == "lstm_vae" else "normal")
            else:
                axis.text(0.025, position, "未提供", va="center", color=MUTED, fontsize=10)
    axis.set_yticks(y, [name for _, name in METHODS], fontsize=12)
    axis.set_ylim(len(METHODS) - 0.35, -0.65)
    axis.set_xlim(0, 1.22)
    axis.set_xticks([0, 0.25, 0.50, 0.75, 1.0])
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_xlabel("指标值（越高越好）", fontsize=10.5, color=MUTED, labelpad=14)
    _highlight_labels(axis)
    fig.legend(
        handles=[Patch(facecolor=NEUTRAL, label="F1"),
                 Patch(facecolor=NEUTRAL, alpha=0.38, label="AP")],
        loc="upper left", bbox_to_anchor=(0.126, 0.785), ncol=2, frameon=False,
        fontsize=11, handlelength=1.1, handleheight=0.8, columnspacing=2.0,
    )


def _render_tradeoff(fig: Any, records: list[dict]) -> None:
    for column, (metric, title) in enumerate((
        ("recall", "召回率 ↑"), ("false_positive_rate", "误报率 ↓"),
    )):
        axis = fig.add_axes((0.671 + column * 0.166, 0.555, 0.127, 0.170))
        _clean_axis(axis)
        highlighted = next(index for index, (key, _) in enumerate(METHODS) if key == "lstm_vae")
        axis.axhspan(highlighted - 0.45, highlighted + 0.45, color="#EDF7F6", zorder=0)
        for index, record in enumerate(records):
            average, spread = _estimate(record.get("metrics", {}).get(metric))
            if not math.isfinite(average):
                axis.text(0.5, index, "—", ha="center", va="center", color=MUTED)
                continue
            color = ACCENT if record["method_id"] == "lstm_vae" else NEUTRAL
            axis.errorbar(average, index, xerr=spread if math.isfinite(spread) else None,
                          fmt="o", color=color, markersize=6.5, elinewidth=1.2,
                          capsize=2.5, markeredgecolor="white", markeredgewidth=0.7)
        axis.set_yticks(np.arange(len(METHODS)))
        if column == 0:
            axis.set_yticklabels([name for _, name in METHODS], fontsize=10)
            _highlight_labels(axis)
        else:
            axis.set_yticklabels([])
        axis.set_ylim(len(METHODS) - 0.45, -0.55)
        axis.set_xlim(-0.055, 1.055)
        axis.set_xticks([0, 0.5, 1.0])
        axis.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        axis.tick_params(axis="x", labelsize=9)
        axis.grid(axis="x", color=GRID, linewidth=0.8)
        axis.set_title(title, loc="left", fontsize=11, color=INK, pad=10)


def _render_heatmap(fig: Any, records: list[dict]) -> None:
    matrix = np.full((len(METHODS), len(SCENARIOS)), math.nan)
    for row, record in enumerate(records):
        for column, (key, _) in enumerate(SCENARIOS):
            value = record.get("scenarios", {}).get(key)
            if isinstance(value, dict) and "recall" in value:
                value = value["recall"]
            matrix[row, column] = _estimate(value)[0]
    palette = LinearSegmentedColormap.from_list(
        "health_recall", ["#F2F5F7", "#C5E4E3", "#55B0AE", "#0C6570"]
    )
    palette.set_bad("#F4F5F6")
    axis = fig.add_axes((0.673, 0.227, 0.292, 0.226))
    _clean_axis(axis)
    axis.imshow(np.ma.masked_invalid(matrix), cmap=palette, norm=Normalize(0, 1), aspect="auto")
    axis.set_yticks(np.arange(len(METHODS)), [name for _, name in METHODS], fontsize=10)
    axis.set_xticks(np.arange(len(SCENARIOS)), [name for _, name in SCENARIOS], fontsize=10)
    axis.tick_params(axis="both", pad=8)
    axis.set_xticks(np.arange(-0.5, len(SCENARIOS), 1), minor=True)
    axis.set_yticks(np.arange(-0.5, len(METHODS), 1), minor=True)
    axis.grid(which="minor", color="white", linewidth=3)
    axis.tick_params(which="minor", length=0)
    _highlight_labels(axis)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            axis.text(column, row, f"{value:.0%}" if math.isfinite(value) else "—",
                      ha="center", va="center", fontsize=11.5,
                      color="white" if value >= 0.68 else INK)


def render_report(result: dict, output_dir: Path) -> list[Path]:
    """Write the four-method baseline comparison; keep input results intact."""
    if result.get("schema_version") not in (None, "1.0"):
        raise ValueError("Unsupported result schema; expected schema_version '1.0'.")
    if not isinstance(result.get("aggregate"), list) or not result["aggregate"]:
        raise ValueError("Result must contain a nonempty 'aggregate' list of measurements.")
    by_id = {record["method_id"]: record for record in result["aggregate"]}
    records = [by_id.get(key, {"method_id": key}) for key, _ in METHODS]
    seeds = result.get("config", {}).get("seeds", [])
    repeats = len(seeds) or len(result.get("runs", []))
    repeat_text = f"{repeats} 次独立随机种子" if repeats else "独立随机种子运行次数未提供"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / "comparison.png", output_dir / "comparison.svg"]
    with plt.rc_context({
        "font.family": "sans-serif", "font.sans-serif": [_font_name(), "DejaVu Sans"],
        "axes.unicode_minus": False, "text.color": INK, "font.size": 11,
        "figure.facecolor": "#FAFBFC", "savefig.facecolor": "#FAFBFC",
        "svg.fonttype": "path", "axes.linewidth": 0.7,
    }):
        fig = plt.figure(figsize=(16, 9), dpi=150)
        try:
            fig.text(0.045, 0.934, "LSTM-VAE 与三种基础方法对比", fontsize=25,
                     fontweight="bold", color=INK, va="center")
            fig.text(0.046, 0.880, "合成体征数据 · 独立测试对象 · 窗口级指标 · 非临床验证",
                     fontsize=13.5, color=MUTED, va="center")
            fig.add_artist(plt.Line2D([0.045, 0.965], [0.840, 0.840],
                                     transform=fig.transFigure, color=GRID, linewidth=1))
            fig.text(0.046, 0.795, "整体检测表现", fontsize=16, fontweight="bold")
            fig.text(0.558, 0.795, "检出与误报", fontsize=16, fontweight="bold")
            fig.text(0.558, 0.488, "分异常类型召回率", fontsize=16, fontweight="bold")
            fig.text(0.965, 0.490, "颜色越深，召回越高", ha="right", fontsize=9.5, color=MUTED)
            _render_bars(fig, records)
            _render_tradeoff(fig, records)
            _render_heatmap(fig, records)
            fig.add_artist(plt.Line2D([0.045, 0.965], [0.138, 0.138],
                                     transform=fig.transFigure, color=GRID, linewidth=1))
            fig.text(0.046, 0.100,
                     f"PR-AUC 使用 Average Precision（AP）计算；均值 ± 标准差（{repeat_text}）；热图仅显示均值",
                     fontsize=10.5, color=MUTED)
            fig.text(0.046, 0.065, _dataset_caption(result), fontsize=10.5, color=MUTED)
            fig.text(0.965, 0.065, "蓝绿色标识 LSTM-VAE；所有方法使用相同坐标范围",
                     fontsize=9.5, ha="right", color=MUTED)
            fig.text(0.046, 0.030,
                     "固定阈值沿用项目关注界限；其余方法按验证集 F1 选阈值。场景含水平/趋势偏移、指标错位及时间重排。",
                     fontsize=9.5, color=MUTED)
            for path in paths:
                fig.savefig(path, dpi=150, format=path.suffix.lstrip("."))
        finally:
            plt.close(fig)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render measured health anomaly benchmark results.")
    parser.add_argument("results", type=Path, help="Result JSON with schema_version 1.0")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    result = json.loads(args.results.read_text(encoding="utf-8"))
    destination = args.output_dir or args.results.parent
    for path in render_report(result, destination):
        print(path.resolve())


if __name__ == "__main__":
    main()

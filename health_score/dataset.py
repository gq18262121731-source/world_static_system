"""Deterministic synthetic vital-sign sequences for an isolated benchmark.

Labels identify deliberately injected statistical events. They do not identify
diseases or establish clinical validity. This module performs no file I/O.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


FEATURE_NAMES = ["heart_rate", "temperature", "blood_oxygen", "systolic"]
SCENARIO_LABELS = {
    "normal": "正常合成序列",
    "sustained_shift": "持续水平偏移",
    "gradual_drift": "渐进趋势偏移",
    "cross_signal_mismatch": "跨指标动态关系错位",
    "temporal_disruption": "时间顺序扰乱",
}

_DEFAULTS = {
    "window_size": 24,
    "train_subjects": 36,
    "validation_subjects": 12,
    "test_subjects": 18,
    "train_windows_per_subject": 48,
    "eval_windows_per_subject": 40,
    "anomaly_fraction": 0.25,
}
_ANOMALIES = tuple(name for name in SCENARIO_LABELS if name != "normal")
_CALIBRATION_WINDOWS = 16
_STD_FLOOR = np.array([2.0, 0.08, 0.3, 2.0])


def _validated_config(config: dict[str, Any]) -> dict[str, Any]:
    resolved = {key: config.get(key, value) for key, value in _DEFAULTS.items()}
    for key in _DEFAULTS:
        if key == "anomaly_fraction":
            continue
        value = resolved[key]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"{key} must be a positive integer")
        if value < (8 if key == "window_size" else 1):
            raise ValueError(f"{key} must be >= {8 if key == 'window_size' else 1}")
        resolved[key] = int(value)
    fraction = float(resolved["anomaly_fraction"])
    if not np.isfinite(fraction) or not 0.0 <= fraction <= 1.0:
        raise ValueError("anomaly_fraction must lie between 0 and 1")
    resolved["anomaly_fraction"] = fraction
    return resolved


def _subject_parameters(rng: np.random.Generator) -> dict[str, np.ndarray | float]:
    return {
        "center": np.array([
            rng.uniform(64.0, 82.0),
            rng.uniform(36.3, 36.8),
            rng.uniform(97.0, 98.5),
            rng.uniform(110.0, 135.0),
        ]),
        "response": np.array([10.0, 0.15, -0.35, 8.0]) * rng.uniform(0.8, 1.2, 4),
        "noise": np.array([0.7, 0.025, 0.12, 1.0]) * rng.uniform(0.8, 1.2, 4),
        "amplitude": float(rng.uniform(0.8, 1.2)),
    }


def _normal_window(
    rng: np.random.Generator,
    subject: dict[str, np.ndarray | float],
    length: int,
) -> np.ndarray:
    # Shared smooth activity dynamics create relationships between all channels.
    # Both resting and active windows are normal; magnitude alone is not a label.
    phase = rng.uniform(0.0, 2.0 * np.pi)
    cycles = rng.uniform(0.45, 1.35)
    time = np.linspace(0.0, 1.0, length)
    resting = bool(rng.random() < 0.45)
    level = rng.uniform(-0.6, 0.0) if resting else rng.uniform(0.2, 1.1)
    amplitude = rng.uniform(0.15, 0.45) if resting else rng.uniform(0.5, 1.0)
    activity = level + amplitude * float(subject["amplitude"]) * (
        np.sin(2.0 * np.pi * cycles * time + phase)
        + 0.18 * np.sin(4.0 * np.pi * cycles * time + phase)
    )
    fluctuations = np.zeros(length)
    fluctuations[0] = rng.normal(0.0, 0.06)
    for index in range(1, length):
        fluctuations[index] = 0.8 * fluctuations[index - 1] + rng.normal(0.0, 0.035)
    activity += fluctuations

    # Temperature has a slower response, while heart rate and pressure co-vary.
    delayed = np.empty(length)
    delayed[0] = activity[0]
    for index in range(1, length):
        delayed[index] = 0.75 * delayed[index - 1] + 0.25 * activity[index]
    trajectories = np.column_stack([activity, delayed, activity, activity])
    values = np.asarray(subject["center"]) + trajectories * np.asarray(subject["response"])
    values += rng.normal(size=(length, 4)) * np.asarray(subject["noise"]) * rng.uniform(0.7, 1.3)
    # Small smooth physiological variation is independent of the activity factor.
    extra = np.sin(2.0 * np.pi * rng.uniform(0.3, 0.8) * time + rng.uniform(0, 2 * np.pi))
    values += extra[:, None] * np.array([0.8, 0.035, 0.10, 1.0])
    return values


def _inject_event(rng: np.random.Generator, values: np.ndarray, scenario: str) -> np.ndarray:
    """Apply a named event without consulting any threshold or model score."""
    result = values.copy()
    length = len(result)
    if scenario in {"sustained_shift", "gradual_drift"}:
        start = int(rng.integers(max(1, length // 6), max(2, length // 2)))
        duration = length - start
        severity = rng.uniform(0.8, 1.25)
        shift = np.array([12.0, 0.25, -1.25, 13.0]) * severity
        # Direction and affected feature set vary independently from the label.
        if rng.random() < 0.35:
            shift *= -1.0
        affected = rng.choice(4, size=int(rng.integers(2, 5)), replace=False)
        mask = np.zeros(4)
        mask[affected] = 1.0
        if scenario == "sustained_shift":
            envelope = np.ones(duration)
            onset = min(3, duration)
            envelope[:onset] = np.linspace(0.35, 1.0, onset)
        else:
            envelope = np.linspace(0.0, 1.5, duration)
        result[start:] += envelope[:, None] * shift * mask
    elif scenario == "cross_signal_mismatch":
        # Preserve a channel's complete marginal distribution, but misalign it
        # with the other signals. No absolute threshold defines this event.
        channel = int(rng.choice([0, 2, 3]))
        lag = int(rng.integers(max(2, length // 3), max(3, 2 * length // 3 + 1)))
        result[:, channel] = np.roll(result[:, channel], lag)
    elif scenario == "temporal_disruption":
        # Jointly reorder rows: all within-time feature relationships and all
        # marginal values are preserved, while local time continuity changes.
        segment_size = max(6, int(np.ceil(length * rng.uniform(0.6, 0.9))))
        segment_size = min(segment_size, length)
        start = int(rng.integers(0, length - segment_size + 1))
        permutation = rng.permutation(segment_size)
        if np.array_equal(permutation, np.arange(segment_size)):
            permutation = np.roll(permutation, 1)
        result[start : start + segment_size] = result[start : start + segment_size][permutation]
    else:
        raise ValueError(f"Unknown event scenario: {scenario}")
    return result


def _make_split(
    name: str,
    seed: np.random.SeedSequence,
    subject_count: int,
    windows_per_subject: int,
    window_size: int,
    anomaly_fraction: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    count = subject_count * windows_per_subject
    anomaly_count = int(np.floor(count * anomaly_fraction + 0.5))
    rng = np.random.default_rng(seed)
    # Event classes are globally balanced to within one window; their placement
    # across subjects and window indices is shuffled before generating signals.
    assignments = ["normal"] * (count - anomaly_count)
    assignments += [_ANOMALIES[index % len(_ANOMALIES)] for index in range(anomaly_count)]
    rng.shuffle(assignments)
    subject_seeds = seed.spawn(subject_count)
    values = np.empty((count, window_size, 4), dtype=np.float32)
    personal_mean = np.empty((count, 4), dtype=np.float32)
    personal_std = np.empty((count, 4), dtype=np.float32)
    subject_ids: list[str] = []

    for subject_index, subject_seed in enumerate(subject_seeds):
        parameter_seed, calibration_seed, window_seed, event_seed = subject_seed.spawn(4)
        subject = _subject_parameters(np.random.default_rng(parameter_seed))
        calibration_rng = np.random.default_rng(calibration_seed)
        calibration = np.concatenate([
            _normal_window(calibration_rng, subject, window_size)
            for _ in range(_CALIBRATION_WINDOWS)
        ])
        center = calibration.mean(axis=0)
        scale = np.maximum(calibration.std(axis=0, ddof=1), _STD_FLOOR)
        window_rng = np.random.default_rng(window_seed)
        event_rng = np.random.default_rng(event_seed)
        subject_id = f"{name}_subject_{subject_index:04d}"
        for window_index in range(windows_per_subject):
            row = subject_index * windows_per_subject + window_index
            window = _normal_window(window_rng, subject, window_size)
            if assignments[row] != "normal":
                window = _inject_event(event_rng, window, assignments[row])
            values[row] = window
            personal_mean[row] = center
            personal_std[row] = scale
            subject_ids.append(subject_id)

    counts = Counter(assignments)
    split = {
        "values": values,
        "personal_mean": personal_mean,
        "personal_std": personal_std,
        "labels": np.array([int(item != "normal") for item in assignments], dtype=np.int64),
        "scenarios": assignments,
        "subject_ids": subject_ids,
    }
    summary = {
        "subject_count": subject_count,
        "window_count": count,
        "normal_count": count - anomaly_count,
        "anomaly_count": anomaly_count,
        "anomaly_fraction": anomaly_count / count,
        "scenario_counts": {scenario: counts.get(scenario, 0) for scenario in SCENARIO_LABELS},
    }
    return split, summary


def make_dataset(config: dict[str, Any], seed: int) -> dict[str, Any]:
    """Return train/validation/test arrays with disjoint synthetic subjects.

    Evaluation labels come only from injected events. All train windows and all
    personal calibration windows are generated without event injection. Calling
    this function again with the same configuration and seed reproduces arrays.
    Unrelated configuration keys are accepted for use by a shared experiment CLI.
    """
    resolved = _validated_config(config)
    split_seeds = np.random.SeedSequence(seed).spawn(3)
    result: dict[str, Any] = {}
    summaries = {}
    for name, split_seed in zip(("train", "validation", "test"), split_seeds):
        split, summary = _make_split(
            name=name,
            seed=split_seed,
            subject_count=resolved[f"{name}_subjects"],
            windows_per_subject=resolved["train_windows_per_subject" if name == "train" else "eval_windows_per_subject"],
            window_size=resolved["window_size"],
            anomaly_fraction=0.0 if name == "train" else resolved["anomaly_fraction"],
        )
        result[name] = split
        summaries[name] = summary
    result["metadata"] = {
        "generator_version": "1.0.0",
        "seed": int(seed),
        "config": resolved,
        "feature_names": list(FEATURE_NAMES),
        "units": {"heart_rate": "bpm", "temperature": "degC", "blood_oxygen": "%", "systolic": "mmHg"},
        "step_minutes": 5,
        "step_assumption": "Each synthetic point represents a uniformly sampled 5-minute interval; windows are independent episodes, not a continuous patient timeline.",
        "split": summaries,
        "calibration": {
            "normal_windows_per_subject": _CALIBRATION_WINDOWS,
            "normal_points_per_subject": _CALIBRATION_WINDOWS * resolved["window_size"],
            "statistics": "Mean and sample standard deviation (ddof=1), with a per-feature standard-deviation floor.",
            "std_floor": _STD_FLOOR.tolist(),
            "independence": "Each subject has a separate normal calibration random stream. No train, validation, test, or injected-event window contributes to these statistics.",
        },
        "data_nature": "Fully synthetic multivariate sequences; labels denote independently injected statistical anomalies, not disease diagnoses.",
        "limitations": [
            "No real elder data, clinical outcomes, disease labels, or clinician-rated health scores are included.",
            "Synthetic activity, noise and anomaly assumptions may favor or disadvantage particular detectors; results do not establish real-world superiority.",
            "Cross-signal and time-order events can be subtle during resting periods; event labels do not guarantee easy detectability.",
            "Anomaly prevalence is deliberately controlled and does not estimate real-world prevalence.",
            "Windows are independent synthetic episodes; window metrics cannot establish event lead time or false alarms per patient-day.",
        ],
    }
    return result

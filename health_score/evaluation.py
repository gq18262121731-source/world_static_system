"""Window-level metrics. No point adjustment, test-set tuning, or rule fallback."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


METHODS = [
    ('fixed_threshold', '固定阈值'),
    ('personal_zscore', '个人Z-score'),
    ('isolation_forest', '孤立森林'),
    ('lstm_ae', 'LSTM-AE'),
    ('lstm_vae', 'LSTM-VAE'),
]


def normalize(split):
    return np.asarray(
        (split['values'] - split['personal_mean'][:, None, :]) /
        split['personal_std'][:, None, :], dtype=np.float32,
    )


def fixed_threshold_scores(values):
    """Project-inspired demonstration limits, not clinical recommendations.

    The operating point is fixed at 0. AP uses the continuous distance to the
    same limits, rather than incorrectly computing a PR curve from hard labels.
    """
    # Use the earlier warning levels, not only the project's critical limits.
    # nextafter preserves strict '<' lower bounds with a shared score >= 0 rule.
    lower = np.array([np.nextafter(50.0, -np.inf), np.nextafter(35.0, -np.inf),
                      94.0, np.nextafter(90.0, -np.inf)])
    upper = np.array([100.0, 37.5, np.inf, 140.0])
    scale = np.array([20.0, 1.0, 4.0, 30.0])
    distance = np.maximum((lower - values) / scale, (values - upper) / scale)
    return distance.max(axis=(1, 2))


def window_features(values):
    time_axis = np.linspace(-1, 1, values.shape[1], dtype=np.float32)
    slope = np.sum(values * time_axis[None, :, None], axis=1) / np.sum(time_axis ** 2)
    return np.concatenate([
        values.mean(axis=1), values.std(axis=1), values.min(axis=1),
        values.max(axis=1), slope, np.abs(np.diff(values, axis=1)).mean(axis=1),
    ], axis=1)


def choose_threshold(labels, scores):
    """Maximize validation F1; ties prefer fewer false positives.

    Predictions always use score >= threshold, including ties.
    """
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    if len(labels) != len(scores) or not len(labels) or not np.isfinite(scores).all():
        raise ValueError('Threshold selection needs finite, aligned scores and labels')
    if set(np.unique(labels)) != {0, 1}:
        raise ValueError('Validation data must contain both normal and abnormal windows')
    order = np.argsort(-scores, kind='stable')
    sorted_scores, sorted_labels = scores[order], labels[order]
    endpoints = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(scores) - 1]
    tp = np.cumsum(sorted_labels)[endpoints]
    fp = endpoints + 1 - tp
    fn = labels.sum() - tp
    f1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
    best = max(range(len(endpoints)), key=lambda i: (f1[i], -fp[i], sorted_scores[endpoints[i]]))
    return float(sorted_scores[endpoints[best]])


def evaluate(labels, scores, threshold, scenarios):
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    if len(labels) != len(scores) or not np.isfinite(scores).all():
        raise ValueError('Evaluation needs finite, aligned scores')
    predicted = scores >= threshold
    tp = int(np.sum(predicted & (labels == 1)))
    fp = int(np.sum(predicted & (labels == 0)))
    tn = int(np.sum(~predicted & (labels == 0)))
    fn = int(np.sum(~predicted & (labels == 1)))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    metrics = {
        'precision': precision, 'recall': recall,
        'f1': 2 * tp / max(2 * tp + fp + fn, 1),
        'false_positive_rate': fp / max(fp + tn, 1),
        'average_precision': float(average_precision_score(labels, scores)),
        'roc_auc': float(roc_auc_score(labels, scores)),
    }
    scenario_array = np.asarray(scenarios)
    recalls = {}
    for name in sorted(set(scenarios)):
        selected = (scenario_array == name) & (labels == 1)
        if selected.any():
            recalls[name] = float(predicted[selected].mean())
    return metrics, {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn}, recalls


def aggregate_runs(runs):
    def summarize(values):
        return {'mean': float(np.mean(values)), 'std': float(np.std(values, ddof=1)) if len(values) > 1 else 0.0}
    aggregate = []
    for method_id, label in METHODS:
        rows = [next(m for m in run['methods'] if m['method_id'] == method_id) for run in runs]
        aggregate.append({
            'method_id': method_id, 'label': label,
            'metrics': {key: summarize([r['metrics'][key] for r in rows]) for key in rows[0]['metrics']},
            'scenarios': {key: summarize([r['scenarios'][key] for r in rows]) for key in rows[0]['scenarios']},
            'fit_seconds': summarize([r['fit_seconds'] for r in rows]),
            'normal_validation_fpr_calibration': {
                key: summarize([r['normal_validation_fpr_calibration']['metrics'][key] for r in rows])
                for key in rows[0]['normal_validation_fpr_calibration']['metrics']
            },
        })
    return aggregate

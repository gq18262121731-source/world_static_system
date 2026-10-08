"""Train once; subsequently reproduce the comparison from an auditable JSON cache."""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stdout
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = '1.0'
# Only this earlier launcher is compatible; its experiment logic is unchanged.
LEGACY_RUNNER_SHA256 = 'b874bc88b979403f2b6ecf2a3b47ed9d5cdac2f9bd4f11f59c4aeaf46e6dafb2'
LEGACY_EXPERIMENT_AST_SHA256 = '64db4dc24b5931989f41e10104dd9411a2957c87c89eb36d1633d362131e0320'
DEFAULT_CONFIG = {
    'protocol_version': 1,
    'seeds': [11, 23, 37],
    'window_size': 24,
    'train_subjects': 36, 'validation_subjects': 12, 'test_subjects': 18,
    'train_windows_per_subject': 48, 'eval_windows_per_subject': 40,
    'anomaly_fraction': 0.25,
    'epochs': 50, 'patience': 10, 'batch_size': 128,
    'hidden_size': 48, 'latent_size': 12, 'learning_rate': 0.001,
    'kl_beta': 0.005, 'kl_warmup_epochs': 10,
    'iforest_estimators': 200,
    'normal_validation_fpr_target': 0.05,
    'fixed_limits': 'HR<50 or >=100; temperature<35 or >=37.5; SpO2<=94; systolic<90 or >=140',
    'threshold_policy': 'fixed rules: zero; other methods: validation F1, ties fewer FP',
    'reconstruction_score': 'mean squared error over all time steps and features',
}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def source_fingerprint(config):
    # Fingerprint calculation code, not CLI logging/opening or plot styling.
    # Keep computational helpers in the three hashed modules below. Any future
    # computation outside run_experiment or these modules must also be hashed.
    tree = ast.parse((ROOT / Path(__file__).name).read_text(encoding='utf-8-sig'))
    experiment = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'run_experiment')
    # This historical cache key is an identifier, not a filesystem path.
    # Preserve it so moving/renaming the launcher does not invalidate results.
    sources = {'run_benchmark.py::run_experiment': hashlib.sha256(
        ast.dump(experiment, include_attributes=False).encode('utf-8')).hexdigest()}
    for name in ('dataset.py', 'models.py', 'evaluation.py'):
        sources[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    digest = hashlib.sha256(canonical_json({'config': config, 'sources': sources}).encode('utf-8')).hexdigest()
    return digest, sources


def _legacy_cache_matches(result, fingerprint):
    """Accept the verified earlier launcher without rewriting its provenance."""
    saved_sources = result.get('source_sha256', {})
    if not isinstance(saved_sources, dict) or set(saved_sources) != {
            'run_benchmark.py', 'dataset.py', 'models.py', 'evaluation.py'}:
        return False
    if saved_sources['run_benchmark.py'] != LEGACY_RUNNER_SHA256:
        return False
    config = result.get('config')
    if not isinstance(config, dict):
        return False
    original = hashlib.sha256(canonical_json(
        {'config': config, 'sources': saved_sources}).encode('utf-8')).hexdigest()
    if result.get('fingerprint') != original:
        return False
    current, current_sources = source_fingerprint(config)
    return (current == fingerprint
            and current_sources['run_benchmark.py::run_experiment'] == LEGACY_EXPERIMENT_AST_SHA256
            and all(saved_sources[name] == current_sources[name]
                    for name in ('dataset.py', 'models.py', 'evaluation.py')))


def read_cache(path, fingerprint):
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        integrity = result.pop('integrity_sha256', None)
        actual = hashlib.sha256(canonical_json(result).encode('utf-8')).hexdigest()
        if integrity != actual:
            return None, 'JSON integrity check failed'
        if result.get('schema_version') != SCHEMA_VERSION:
            return None, 'cache schema changed'
        if result.get('fingerprint') != fingerprint:
            if not _legacy_cache_matches(result, fingerprint):
                return None, 'experiment code or parameters changed'
        result['integrity_sha256'] = integrity
        return result, 'valid'
    except FileNotFoundError:
        return None, 'no saved cache'
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return None, f'cannot read cache: {exc}'


def save_cache(result, path):
    payload = {key: value for key, value in result.items() if key != 'integrity_sha256'}
    payload['integrity_sha256'] = hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)
    return payload


def run_experiment(config, fingerprint, sources, requested_device):
    # Set before importing/initializing CUDA; cache replay never imports torch.
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    import numpy as np
    import torch
    from sklearn.ensemble import IsolationForest
    from dataset import make_dataset
    from evaluation import (METHODS, aggregate_runs, choose_threshold, evaluate,
                            fixed_threshold_scores, normalize, window_features)
    from models import fit_sequence_model, reconstruction_scores

    if requested_device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA requested but unavailable. Use --device cpu or auto.')
    device = 'cuda' if requested_device == 'cuda' or (requested_device == 'auto' and torch.cuda.is_available()) else 'cpu'
    print(f'[TRAIN] device={device}; seeds={config["seeds"]}; epochs<={config["epochs"]}', flush=True)
    started = time.perf_counter()
    runs = []
    dataset_metadata = None
    for seed in config['seeds']:
        print(f'[DATA] seed={seed}: generating independent subjects and windows', flush=True)
        data = make_dataset(config, seed)
        dataset_metadata = data['metadata'] if dataset_metadata is None else dataset_metadata
        train, validation, test = (data[name] for name in ('train', 'validation', 'test'))
        train_ids, validation_ids, test_ids = (set(s['subject_ids']) for s in (train, validation, test))
        if train_ids & validation_ids or train_ids & test_ids or validation_ids & test_ids:
            raise RuntimeError('Subject leakage between splits')
        if np.any(train['labels']):
            raise RuntimeError('Training data must be normal only')
        normalized = {name: normalize(data[name]) for name in ('train', 'validation', 'test')}
        normal_validation = normalized['validation'][validation['labels'] == 0]
        run = {
            'seed': seed, 'dataset': data['metadata'],
            'validation': {key: validation[key].tolist() if hasattr(validation[key], 'tolist') else validation[key]
                           for key in ('labels', 'scenarios', 'subject_ids')},
            'test': {key: test[key].tolist() if hasattr(test[key], 'tolist') else test[key]
                     for key in ('labels', 'scenarios', 'subject_ids')},
            'methods': [],
        }
        for method_id, label in METHODS:
            print(f'[FIT] seed={seed} method={method_id}', flush=True)
            method_started = time.perf_counter()
            training = {}
            if method_id == 'fixed_threshold':
                val_scores = fixed_threshold_scores(validation['values'])
                test_scores = fixed_threshold_scores(test['values'])
                fit_seconds = 0.0
            elif method_id == 'personal_zscore':
                val_scores = np.abs(normalized['validation']).max(axis=(1, 2))
                test_scores = np.abs(normalized['test']).max(axis=(1, 2))
                fit_seconds = 0.0  # Personal calibration is supplied equally to learned methods.
            elif method_id == 'isolation_forest':
                model = IsolationForest(n_estimators=config['iforest_estimators'],
                                        max_samples='auto', random_state=seed, n_jobs=2)
                model.fit(window_features(normalized['train']))
                fit_seconds = time.perf_counter() - method_started
                val_scores = -model.score_samples(window_features(normalized['validation']))
                test_scores = -model.score_samples(window_features(normalized['test']))
            else:
                model, training = fit_sequence_model(
                    normalized['train'], normal_validation, config, seed,
                    variational=method_id == 'lstm_vae', device=device,
                    progress=lambda message: print(f'  {message}', flush=True),
                )
                fit_seconds = training['fit_seconds']
                val_scores = reconstruction_scores(model, normalized['validation'], device)
                test_scores = reconstruction_scores(model, normalized['test'], device)
                # Independent of the metrics: repeated inference must be stable.
                # Keep batch partition identical: CUDA kernels can round
                # differently for an 8-window batch versus a 256-window batch.
                repeated = reconstruction_scores(model, normalized['test'], device)
                training['repeat_inference_max_abs_delta'] = float(np.max(np.abs(repeated - test_scores)))
                if not np.array_equal(repeated, test_scores):
                    raise RuntimeError('Repeated model inference was not stable')
                del model
            threshold = 0.0 if method_id == 'fixed_threshold' else choose_threshold(validation['labels'], val_scores)
            metrics, confusion, scenarios = evaluate(test['labels'], test_scores, threshold, test['scenarios'])
            validation_metrics, _, _ = evaluate(validation['labels'], val_scores, threshold, validation['scenarios'])
            normal_scores = val_scores[validation['labels'] == 0]
            fpr_threshold = float(np.nextafter(np.quantile(
                normal_scores, 1.0 - config['normal_validation_fpr_target'], method='higher'), np.inf))
            fpr_metrics, fpr_confusion, _ = evaluate(test['labels'], test_scores, fpr_threshold, test['scenarios'])
            run['methods'].append({
                'method_id': method_id, 'label': label, 'threshold': threshold,
                'threshold_source': 'project-inspired fixed limits' if method_id == 'fixed_threshold' else 'validation only',
                'fit_seconds': fit_seconds, 'metrics': metrics, 'confusion': confusion,
                'scenarios': scenarios, 'validation_metrics': validation_metrics,
                'validation_scores': np.asarray(val_scores, dtype=float).tolist(),
                'test_scores': np.asarray(test_scores, dtype=float).tolist(),
                'training': training,
                'normal_validation_fpr_calibration': {
                    'target': config['normal_validation_fpr_target'], 'threshold': fpr_threshold,
                    'actual_validation_fpr': float(np.mean(normal_scores >= fpr_threshold)),
                    'metrics': fpr_metrics, 'confusion': fpr_confusion,
                    'note': 'Additional diagnostic using the same normal-validation FPR policy for every method. Test FPR may differ; fixed-rule margin cutoff here differs from its original rule.',
                },
            })
            print(f'  TEST F1={metrics["f1"]:.4f} AP={metrics["average_precision"]:.4f} '
                  f'recall={metrics["recall"]:.4f} FPR={metrics["false_positive_rate"]:.4f}', flush=True)
        runs.append(run)
    packages = {}
    for package in ('numpy', 'scikit-learn', 'torch', 'matplotlib'):
        packages[package] = importlib.metadata.version(package)
    return {
        'schema_version': SCHEMA_VERSION, 'fingerprint': fingerprint,
        'config': config, 'source_sha256': sources,
        'provenance': {
            'data_kind': 'synthetic',
            'evaluated_at': datetime.now(timezone.utc).isoformat(),
            'python': sys.version.split()[0], 'platform': platform.platform(),
            'packages': packages, 'device': device,
            'gpu': torch.cuda.get_device_name(0) if device == 'cuda' else None,
            'total_fit_and_evaluation_seconds': time.perf_counter() - started,
            'protocol': 'Independent synthetic subjects, normal-only training, held-out validation thresholds, untouched test scores.',
            'unit': f'one independently generated {config["window_size"]}-step window; not a continuous monitoring event',
            'limitations': [
                'Synthetic statistical anomalies; no clinical validation or real elder health-score ground truth.',
                'Normal calibration history is assumed available for every subject.',
                f'Anomaly prevalence is set to {config["anomaly_fraction"]:.0%} for this benchmark, not estimated real-world prevalence.',
                'Fixed-rule operating point is predetermined; other cutoffs maximize validation F1.',
                'AP uses continuous rule-margin scores for fixed thresholds; F1 uses the original fixed operating point.',
                f'Standard deviations reflect {len(config["seeds"])} synthetic data/training seeds, not clinical confidence intervals.',
                'No point adjustment, daily false-alarm estimate, detection-lead-time claim, or forced winner.',
                'Model losses and anomaly scores are not calibrated disease probabilities or health-score accuracy.',
            ],
        },
        'dataset': dataset_metadata, 'runs': runs, 'aggregate': aggregate_runs(runs),
    }


def print_summary(result):
    print('\nmethod                 F1       AP       Recall   FPR', flush=True)
    for row in result['aggregate']:
        metrics = row['metrics']
        print(f'{row["method_id"]:22s} {metrics["f1"]["mean"]:.4f}   '
              f'{metrics["average_precision"]["mean"]:.4f}   '
              f'{metrics["recall"]["mean"]:.4f}   {metrics["false_positive_rate"]["mean"]:.4f}')


def open_figure(path):
    """Open the finished PNG using the system's image viewer."""
    target = str(path.resolve())
    if sys.platform == 'win32':
        os.startfile(target)
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', target])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrain', action='store_true', help='Ignore cached results and train again')
    parser.add_argument('--plot-only', action='store_true', help='Require valid JSON; never train')
    parser.add_argument('--no-open', action='store_true', help='Save figures without opening the image viewer')
    parser.add_argument('--verbose', action='store_true', help='Show cache diagnostics and detailed training logs')
    parser.add_argument('--quick', action='store_true', help='Small smoke run, separate output/quick cache; not presentation data')
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--epochs', type=int, help='Override epoch cap; changes cache fingerprint')
    parser.add_argument('--seeds', type=int, nargs='+', help='Override independent seeds; changes cache fingerprint')
    parser.add_argument('--output-dir', type=Path, help='Directory for results.json and comparison images')
    args = parser.parse_args(argv)
    if args.retrain and args.plot_only:
        parser.error('--retrain and --plot-only cannot be combined')
    config = dict(DEFAULT_CONFIG)
    if args.quick:
        config.update(seeds=[11], train_subjects=8, validation_subjects=4, test_subjects=4,
                      train_windows_per_subject=24, eval_windows_per_subject=24, epochs=5,
                      iforest_estimators=40)
    if args.epochs is not None:
        if args.epochs < 1:
            parser.error('--epochs must be positive')
        config['epochs'] = args.epochs
    if args.seeds:
        if len(set(args.seeds)) != len(args.seeds) or min(args.seeds) < 0:
            parser.error('--seeds must be distinct non-negative integers')
        config['seeds'] = args.seeds
    output_dir = (args.output_dir or ROOT / 'output' / ('quick' if args.quick else '')).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_path = output_dir / 'results.json'
    fingerprint, sources = source_fingerprint(config)
    print('正在准备对比图…', flush=True)
    result, reason = read_cache(cache_path, fingerprint)
    if result is not None and not args.retrain:
        if args.verbose:
            print(f'[CACHE HIT] {cache_path}; skipped data generation and all training.', flush=True)
    else:
        if args.plot_only:
            parser.error(f'No valid cache ({reason}). Run without --plot-only first.')
        if args.verbose:
            print(f'[CACHE MISS] {"--retrain requested" if args.retrain else reason}', flush=True)
            result = run_experiment(config, fingerprint, sources, args.device)
        else:
            # Keep errors visible; only optional progress messages are quiet.
            with open(os.devnull, 'w', encoding='utf-8') as quiet, redirect_stdout(quiet):
                result = run_experiment(config, fingerprint, sources, args.device)
        result = save_cache(result, cache_path)
        if args.verbose:
            print(f'[SAVED] {cache_path}', flush=True)
    from plot_results import render_report
    paths = render_report(result, output_dir)
    if args.verbose:
        print_summary(result)
        for path in paths:
            print(f'[FIGURE] {path}')
    figure_path = next(path for path in paths if path.suffix.lower() == '.png')
    print(f'对比图已就绪：{figure_path}', flush=True)
    if not args.no_open:
        try:
            open_figure(figure_path)
        except OSError as exc:
            print(f'图片已保存，但无法自动打开：{exc}\n请手动打开：{figure_path}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())

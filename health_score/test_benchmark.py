"""Small structural/protocol checks; no backend fixtures or database access."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from dataset import make_dataset
from evaluation import choose_threshold, evaluate, fixed_threshold_scores, normalize
import detector as runner
from detector import DEFAULT_CONFIG, read_cache, save_cache, source_fingerprint


class DatasetTests(unittest.TestCase):
    def test_disjoint_deterministic_subjects_and_independent_baselines(self):
        config = dict(DEFAULT_CONFIG, train_subjects=2, validation_subjects=2,
                      test_subjects=2, train_windows_per_subject=8, eval_windows_per_subject=8)
        first = make_dataset(config, 123)
        again = make_dataset(config, 123)
        all_normal = make_dataset(dict(config, anomaly_fraction=0.0), 123)
        ids = [set(first[key]['subject_ids']) for key in ('train', 'validation', 'test')]
        self.assertFalse(ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
        self.assertEqual(int(first['train']['labels'].sum()), 0)
        for key in ('train', 'validation', 'test'):
            np.testing.assert_array_equal(first[key]['values'], again[key]['values'])
            np.testing.assert_array_equal(first[key]['personal_mean'], all_normal[key]['personal_mean'])
            np.testing.assert_array_equal(first[key]['personal_std'], all_normal[key]['personal_std'])
            self.assertTrue(np.isfinite(normalize(first[key])).all())


class MetricsTests(unittest.TestCase):
    def test_threshold_ties_match_brute_force_validation_f1(self):
        labels = np.array([0, 1, 0, 1, 1, 0, 0, 1])
        scores = np.array([0.1, 0.3, 0.3, 0.5, 0.5, 0.5, 0.7, 0.7])
        def rank(threshold):
            pred = scores >= threshold
            tp = int((pred & (labels == 1)).sum())
            fp = int((pred & (labels == 0)).sum())
            fn = int((~pred & (labels == 1)).sum())
            return (2 * tp / (2 * tp + fp + fn), -fp, threshold)
        expected = max(np.unique(scores), key=rank)
        self.assertEqual(choose_threshold(labels, scores), expected)

    def test_confusion_and_fpr_denominator(self):
        labels = np.array([1, 1, 0, 0, 0])
        scores = np.array([0.9, 0.3, 0.8, 0.1, 0.2])
        metrics, confusion, scenarios = evaluate(labels, scores, 0.5, ['shift', 'shift', 'normal', 'normal', 'normal'])
        self.assertEqual(confusion, {'tp': 1, 'fp': 1, 'tn': 2, 'fn': 1})
        self.assertEqual(metrics['f1'], 0.5)
        self.assertAlmostEqual(metrics['false_positive_rate'], 1 / 3)
        self.assertEqual(scenarios['shift'], 0.5)

    def test_warning_boundaries(self):
        normal = np.array([50.0, 36.5, 95.0, 120.0])
        self.assertLess(fixed_threshold_scores(normal[None, None, :])[0], 0)
        for feature, value in ((0, 100.0), (1, 37.5), (2, 94.0), (3, 140.0)):
            point = normal.copy()
            point[feature] = value
            self.assertGreaterEqual(fixed_threshold_scores(point[None, None, :])[0], 0)


class ModelTests(unittest.TestCase):
    def test_reconstruction_shape_batch_independence_and_stable_inference(self):
        import torch
        from models import SequenceAutoencoder
        torch.set_num_threads(1)
        torch.manual_seed(10)
        values = torch.randn(8, 24, 4)
        for variational in (False, True):
            model = SequenceAutoencoder(variational=variational).eval()
            with torch.no_grad():
                first = model(values)[0]
                second = model(values)[0]
                separate = model(values[:1])[0]
            self.assertEqual(first.shape, values.shape)
            torch.testing.assert_close(first, second, rtol=0, atol=0)
            torch.testing.assert_close(first[:1], separate, rtol=1e-5, atol=1e-6)
            model.train()
            reconstruction, mu, logvar = model(values)
            loss = ((reconstruction - values) ** 2).mean()
            if variational:
                loss += 0.005 * (-0.5 * (1 + logvar - mu.square() - logvar.exp()).mean())
            loss.backward()
            self.assertTrue(torch.isfinite(loss))
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))


class CacheTests(unittest.TestCase):
    def test_cache_roundtrip_tamper_and_configuration_change(self):
        fingerprint, _ = source_fingerprint(DEFAULT_CONFIG)
        changed, _ = source_fingerprint(dict(DEFAULT_CONFIG, epochs=51))
        self.assertNotEqual(fingerprint, changed)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'results.json'
            save_cache({'schema_version': '1.0', 'fingerprint': fingerprint, 'example': [1, 2]}, path)
            restored, reason = read_cache(path, fingerprint)
            self.assertEqual(reason, 'valid')
            self.assertEqual(restored['example'], [1, 2])
            self.assertIsNone(read_cache(path, changed)[0])
            payload = json.loads(path.read_text(encoding='utf-8'))
            payload['example'] = [900]
            path.write_text(json.dumps(payload), encoding='utf-8')
            self.assertIsNone(read_cache(path, fingerprint)[0])


def _example_result(config=None):
    config = dict(DEFAULT_CONFIG if config is None else config)
    fingerprint, sources = source_fingerprint(config)
    return {
        'schema_version': '1.0', 'fingerprint': fingerprint,
        'config': config, 'source_sha256': sources,
        'provenance': {'evaluated_at': '2026-09-15T00:00:00+00:00'},
        'aggregate': [], 'runs': [],
    }


class EntryPointTests(unittest.TestCase):
    """Exercise the public command without training or opening real applications."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_dir = Path(self.temporary.name).resolve()
        self.cache_path = self.output_dir / 'results.json'
        self.png = self.output_dir / 'comparison.png'
        self.svg = self.output_dir / 'comparison.svg'
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.render = self.enterContext(mock.patch('plot_results.render_report',
                                                  return_value=[self.png, self.svg]))
        self.train = self.enterContext(mock.patch.object(runner, 'run_experiment'))
        self.opener = self.enterContext(mock.patch.object(runner, 'open_figure'))

    def invoke(self, *arguments):
        with redirect_stdout(self.stdout), redirect_stderr(self.stderr):
            return runner.main(['--output-dir', str(self.output_dir), *arguments])

    def prepare_cache(self):
        result = _example_result()
        save_cache(result, self.cache_path)
        return result

    def test_cache_hit_is_quiet_skips_training_and_opens_png_once(self):
        self.prepare_cache()
        original_import = __import__

        def forbid_torch(name, *args, **kwargs):
            if name == 'torch' or name.startswith('torch.'):
                raise AssertionError('Cache replay must not import PyTorch')
            return original_import(name, *args, **kwargs)

        with mock.patch('builtins.__import__', side_effect=forbid_torch):
            self.assertEqual(self.invoke(), 0)
        self.train.assert_not_called()
        self.render.assert_called_once()
        self.opener.assert_called_once_with(self.png)
        self.assertIn(str(self.png), self.stdout.getvalue())
        self.assertNotIn('CACHE', self.stdout.getvalue())
        self.assertNotIn('[TRAIN]', self.stdout.getvalue())

    def test_no_open_disables_external_application(self):
        self.prepare_cache()
        self.assertEqual(self.invoke('--no-open'), 0)
        self.train.assert_not_called()
        self.render.assert_called_once()
        self.opener.assert_not_called()

    def test_verbose_explains_cache_source(self):
        self.prepare_cache()
        self.assertEqual(self.invoke('--verbose', '--no-open'), 0)
        self.assertIn('[CACHE HIT]', self.stdout.getvalue())
        self.assertIn(str(self.cache_path), self.stdout.getvalue())
        self.train.assert_not_called()

    def test_cache_miss_runs_once_saves_and_suppresses_training_stdout(self):
        def train(config, fingerprint, sources, device):
            print('[TRAIN] details for the developer')
            return _example_result(config)

        self.train.side_effect = train
        self.assertEqual(self.invoke('--no-open'), 0)
        self.train.assert_called_once()
        self.assertIsNotNone(read_cache(self.cache_path, source_fingerprint(DEFAULT_CONFIG)[0])[0])
        self.assertNotIn('[TRAIN]', self.stdout.getvalue())
        self.assertNotIn('CACHE', self.stdout.getvalue())
        self.assertEqual(self.invoke('--no-open'), 0)
        self.train.assert_called_once()

    def test_retrain_ignores_valid_cache_and_verbose_keeps_training_details(self):
        self.prepare_cache()

        def train(config, fingerprint, sources, device):
            print('[TRAIN] real training path invoked')
            return _example_result(config)

        self.train.side_effect = train
        self.assertEqual(self.invoke('--retrain', '--verbose', '--no-open'), 0)
        self.train.assert_called_once()
        self.assertIn('[CACHE MISS]', self.stdout.getvalue())
        self.assertIn('[TRAIN] real training path invoked', self.stdout.getvalue())

    def test_plot_only_missing_cache_never_trains_or_opens(self):
        with self.assertRaises(SystemExit) as raised:
            self.invoke('--plot-only')
        self.assertNotEqual(raised.exception.code, 0)
        self.assertTrue(self.stderr.getvalue())
        self.train.assert_not_called()
        self.render.assert_not_called()
        self.opener.assert_not_called()

    def test_plot_only_with_valid_cache_opens_without_training(self):
        self.prepare_cache()
        self.assertEqual(self.invoke('--plot-only'), 0)
        self.train.assert_not_called()
        self.opener.assert_called_once_with(self.png)

    def test_training_exception_propagates_in_quiet_mode(self):
        self.train.side_effect = RuntimeError('model training failed')
        with self.assertRaisesRegex(RuntimeError, 'model training failed'):
            self.invoke()
        self.assertFalse(self.cache_path.exists())
        self.render.assert_not_called()
        self.opener.assert_not_called()

    def test_render_exception_propagates_before_opening(self):
        self.prepare_cache()
        self.render.side_effect = OSError('could not save figure')
        with self.assertRaisesRegex(OSError, 'could not save figure'):
            self.invoke()
        self.train.assert_not_called()
        self.opener.assert_not_called()

    def test_open_failure_preserves_results_and_reports_image_path(self):
        self.prepare_cache()
        original_bytes = self.cache_path.read_bytes()
        self.opener.side_effect = OSError('no image application is registered')
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(original_bytes, self.cache_path.read_bytes())
        self.assertIn(str(self.png), self.stdout.getvalue() + self.stderr.getvalue())
        self.opener.assert_called_once_with(self.png)


class LegacyCacheTests(unittest.TestCase):
    """Only the previously audited experiment may retain its original cache."""

    OLD_RUNNER_SHA256 = 'b874bc88b979403f2b6ecf2a3b47ed9d5cdac2f9bd4f11f59c4aeaf46e6dafb2'
    CORE_FILES = ('dataset.py', 'models.py', 'evaluation.py')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.cache_path = self.directory / 'results.json'

    @staticmethod
    def legacy_fingerprint(config, sources):
        payload = json.dumps({'config': config, 'sources': sources}, sort_keys=True,
                             separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def legacy_result(self):
        result = _example_result()
        sources = {key: result['source_sha256'][key] for key in self.CORE_FILES}
        sources['run_benchmark.py'] = self.OLD_RUNNER_SHA256
        result['source_sha256'] = sources
        result['fingerprint'] = self.legacy_fingerprint(result['config'], sources)
        return result

    def test_known_legacy_cache_is_reused_without_rewriting_provenance(self):
        original = self.legacy_result()
        saved = save_cache(original, self.cache_path)
        original_bytes = self.cache_path.read_bytes()
        restored, _ = read_cache(self.cache_path, source_fingerprint(DEFAULT_CONFIG)[0])
        self.assertEqual(restored, saved)
        self.assertEqual(restored['provenance'], original['provenance'])
        self.assertEqual(original_bytes, self.cache_path.read_bytes())

    def test_moved_directory_and_renamed_launcher_reuse_existing_cache(self):
        saved = save_cache(self.legacy_result(), self.cache_path)
        original_bytes = self.cache_path.read_bytes()
        original_fingerprint, original_sources = source_fingerprint(DEFAULT_CONFIG)
        moved = self.directory / 'renamed folder'
        moved.mkdir()
        launcher = moved / 'custom_launcher.py'
        launcher.write_bytes(Path(runner.__file__).read_bytes())
        for name in self.CORE_FILES:
            (moved / name).write_bytes((runner.ROOT / name).read_bytes())
        (moved / 'results.json').write_bytes(original_bytes)
        spec = importlib.util.spec_from_file_location('renamed_health_launcher', launcher)
        renamed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renamed)
        fingerprint, sources = renamed.source_fingerprint(DEFAULT_CONFIG)
        self.assertEqual((fingerprint, sources), (original_fingerprint, original_sources))
        self.assertFalse((moved / 'run_benchmark.py').exists())
        self.assertFalse((moved / 'detector.py').exists())
        self.assertEqual(renamed.read_cache(moved / 'results.json', fingerprint)[0], saved)
        self.assertEqual((moved / 'results.json').read_bytes(), original_bytes)

    def test_legacy_cache_rejects_different_requested_parameters(self):
        save_cache(self.legacy_result(), self.cache_path)
        for change in ({'epochs': 51}, {'seeds': [11, 23, 99]}):
            with self.subTest(change=change):
                fingerprint, _ = source_fingerprint(dict(DEFAULT_CONFIG, **change))
                self.assertIsNone(read_cache(self.cache_path, fingerprint)[0])

    def test_legacy_cache_rejects_unknown_runner_or_inconsistent_fingerprint(self):
        for modification in ('unknown_runner', 'inconsistent_fingerprint'):
            with self.subTest(modification=modification):
                result = self.legacy_result()
                if modification == 'unknown_runner':
                    result['source_sha256']['run_benchmark.py'] = '0' * 64
                    result['fingerprint'] = self.legacy_fingerprint(result['config'], result['source_sha256'])
                else:
                    result['fingerprint'] = '0' * 64
                save_cache(result, self.cache_path)
                self.assertIsNone(read_cache(self.cache_path, source_fingerprint(DEFAULT_CONFIG)[0])[0])

    def test_legacy_cache_rejects_current_core_code_or_experiment_changes(self):
        save_cache(self.legacy_result(), self.cache_path)
        source_directory = runner.ROOT
        copies = self.directory / 'sources'
        copies.mkdir()
        runner_name = Path(runner.__file__).name
        originals = {name: (source_directory / name).read_bytes()
                     for name in (*self.CORE_FILES, runner_name)}
        for changed_name in originals:
            with self.subTest(changed_name=changed_name):
                for name, content in originals.items():
                    (copies / name).write_bytes(content)
                if changed_name == runner_name:
                    original = (copies / changed_name).read_text(encoding='utf-8')
                    modified = original.replace('    import numpy as np\n',
                                                '    import numpy as np\n    raise RuntimeError("changed computation")\n', 1)
                    self.assertNotEqual(original, modified)
                    (copies / changed_name).write_text(modified, encoding='utf-8')
                else:
                    with (copies / changed_name).open('ab') as stream:
                        stream.write(b'\n# Simulate a changed core implementation.\n')
                with mock.patch.object(runner, 'ROOT', copies):
                    fingerprint, _ = source_fingerprint(DEFAULT_CONFIG)
                    self.assertIsNone(read_cache(self.cache_path, fingerprint)[0])


if __name__ == '__main__':
    unittest.main()

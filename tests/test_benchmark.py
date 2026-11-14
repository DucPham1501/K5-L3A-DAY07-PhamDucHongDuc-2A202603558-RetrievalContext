"""Protect the boundary between benchmark labels and model-visible input."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import benchmark


class BenchmarkInputTests(unittest.TestCase):
    def test_rejects_gold_at_runtime_boundary(self):
        for extra in ('gold', 'expected_answer', 'answerable', 'gold_chunk_ids', 'absence_reason'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                benchmark.validate_input_case({'id': 'q', 'question': 'Q?', extra: 'label'})

    def test_rejects_hidden_gold_and_invalid_types_in_filter(self):
        for filters in ({'source_id': 'gold-source'}, {'year': True}, {'doc_type': {'gold': 'answer'}}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                benchmark.validate_input_case({'id': 'q', 'question': 'Q?', 'filter': filters})

    def test_dev_run_needs_neither_test_nor_gold_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'benchmark/inputs'
            inputs.mkdir(parents=True)
            cases = [{'id': 'q', 'question': 'Q?', 'filter': {'year': 2023}}]
            (inputs / 'dev.json').write_text(json.dumps(cases), encoding='utf-8')
            with patch.object(benchmark, 'ROOT', root):
                self.assertEqual(benchmark.load_inputs('dev'), cases)
                with self.assertRaises(FileNotFoundError):
                    benchmark.load_inputs('test')
                with self.assertRaises(ValueError):
                    benchmark.load_inputs('../test')


if __name__ == '__main__':
    unittest.main()

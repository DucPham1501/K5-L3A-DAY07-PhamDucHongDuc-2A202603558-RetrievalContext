"""Load question-only inputs for a selected split; gold is evaluator-only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_input_case(case):
    if not isinstance(case, dict) or not {'id', 'question'} <= set(case) <= {'id', 'question', 'filter'}:
        raise ValueError('Runtime inputs must contain only id, question and optional filter')
    if any(not isinstance(case[k], str) or not case[k].strip() for k in ('id', 'question')):
        raise ValueError('Invalid runtime id/question')
    if 'filter' in case:
        filters = case['filter']
        if not isinstance(filters, dict) or set(filters) - {'doc_type', 'year'}:
            raise ValueError('Invalid runtime filter fields')
        if 'doc_type' in filters and (not isinstance(filters['doc_type'], str) or not filters['doc_type'].strip()):
            raise ValueError('Invalid doc_type')
        if 'year' in filters and type(filters['year']) is not int:
            raise ValueError('Invalid year')


def load_inputs(split):
    if split not in ('dev', 'test'):
        raise ValueError('Choose dev or test explicitly')
    # Never open the evaluator files or the other split during an agent run.
    cases = json.loads((ROOT / 'benchmark' / 'inputs' / f'{split}.json').read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('No runtime cases')
    for case in cases:
        validate_input_case(case)
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate runtime IDs')
    return cases

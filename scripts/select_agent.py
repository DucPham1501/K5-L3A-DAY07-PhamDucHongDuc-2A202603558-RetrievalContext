"""Lock the dev-selected agent before any test run; no test labels are read."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def rate(value):
    return value['n'] / value['N'] if value['N'] else -1.0


def main():
    target = ROOT / 'results/experiments/selection.json'
    if target.exists():
        raise ValueError('Selection already locked; do not overwrite after seeing test')
    plan = read('configs/experiments.json')
    options = [{'id': 'baseline', **plan['baseline']}] + plan['experiments']
    comparisons = []
    for complexity, option in enumerate(options):
        directory = option['dev_run']
        record = read(f'{directory}/run.json')
        evaluation = read(f'{directory}/evaluation.json')
        summary = read(f'{directory}/summary.json')
        if record['status'] != 'complete' or evaluation['split'] != 'dev' or evaluation['cases'] != 17:
            raise ValueError('Each candidate needs a complete source-reviewed dev run')
        if sha(option['config']) != record['config_sha256']:
            raise ValueError('Candidate config changed after dev')
        for name, expected in record['asset_sha256'].items():
            if sha(name) != expected:
                raise ValueError('Candidate used different corpus/benchmark')
        first = evaluation['first_retrieval_exact']
        key = [evaluation['grounded_answer']['mean'], rate(evaluation['citation_validity']),
               rate(evaluation['abstention']), evaluation['context_evidence_exact']['rate'],
               first['hit3']['rate'], first['hit1']['rate'], -summary['median_elapsed_ms'],
               -(summary['model_usage']['estimated_usd'] + (summary['embedding_estimated_usd'] or 0)), -complexity]
        comparisons.append({**option, 'selection_key': key, 'evaluation_sha256': sha(f'{directory}/evaluation.json'),
            'reviews_sha256': sha(f'{directory}/reviews.json'), 'run_sha256': sha(f'{directory}/run.json'),
            'config_sha256': sha(option['config'])})
    selected = max(comparisons, key=lambda row: row['selection_key'])
    sources = ['src/agent.py', 'src/agent_controller.py', 'src/agent_benchmark.py', 'src/agent_review.py',
               'src/retrieval.py', 'src/day6/retrieval.py', 'src/day6/embeddings.py', 'src/day6/store.py',
               'src/benchmark.py', 'scripts/select_agent.py']
    lock = {'status': 'locked', 'locked_at': datetime.now(timezone.utc).isoformat(),
        'selected': selected['id'], 'selected_config': selected['config'], 'baseline_config': plan['baseline']['config'],
        'criteria': plan['selection_criteria'], 'dev_comparisons': comparisons,
        'allowed_test_config_sha256': sorted({sha(plan['baseline']['config']), selected['config_sha256']}),
        'benchmark_sha256': read('benchmark/manifest.json')['sha256'],
        'code_sha256': {name: sha(name) for name in sources}, 'test_results_used': False}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Locked from dev:', selected['id'], selected['config'])


if __name__ == '__main__':
    main()

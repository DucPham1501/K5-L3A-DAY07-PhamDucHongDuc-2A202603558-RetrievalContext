"""Bounded multi-tool agent with one cumulative evidence snapshot per model call."""
import json
import re
import time

from .agent_controller import SEARCH_TOOLS, system_prompt
from .retrieval import BM25Retriever, pack_context, reciprocal_rank_fusion, validate_search

ABSTENTION = 'Không đủ bằng chứng trong tài liệu để trả lời đầy đủ câu hỏi.'


def validate_config(config):
    for key in ('max_searches', 'max_model_calls', 'top_k', 'candidate_k', 'context_budget_chars', 'max_completion_tokens'):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f'Invalid {key}')
    if not 3 <= config['top_k'] <= config['candidate_k'] <= 100:
        raise ValueError('Expected 3 <= top_k <= candidate_k <= 100')
    if config['max_model_calls'] <= config['max_searches']:
        raise ValueError('Need a final model call after searches')
    allowed = config['allowed_search_tools']
    if not allowed or len(set(allowed)) != len(allowed) or set(allowed) - set(SEARCH_TOOLS):
        raise ValueError('Invalid search tools')
    if config['context_policy'] not in ('recent_first', 'first_seen'):
        raise ValueError('Unsupported context policy')
    system_prompt(config)


class RetrievalTools:
    def __init__(self, dense, chunks, config):
        self.dense, self.config = dense, config
        self.bm25 = BM25Retriever(chunks, **config['bm25'])

    def search(self, name, query, *, filters):
        validate_search(query, filters, self.config['top_k'])
        branches = {}
        if name in ('search_dense', 'search_hybrid'):
            branches['dense'] = self.dense.search(query, filters=filters, top_k=self.config['candidate_k'])
        if name in ('search_bm25', 'search_hybrid'):
            branches['bm25'] = self.bm25.search(query, filters=filters, top_k=self.config['candidate_k'])
        if name == 'search_hybrid':
            results = reciprocal_rank_fusion(branches, top_k=self.config['top_k'], **self.config['rrf'])
        elif name in ('search_dense', 'search_bm25'):
            results = next(iter(branches.values()))[:self.config['top_k']]
        else:
            raise ValueError('Unknown retrieval tool')
        return {'results': results, 'branches': branches}


def update_context(candidates, new_results, config):
    combined = new_results + candidates if config['context_policy'] == 'recent_first' else candidates + new_results
    unique, seen = [], set()
    for row in combined:
        if row['id'] not in seen:
            unique.append(row)
            seen.add(row['id'])
    context, ids = pack_context(unique, budget=config['context_budget_chars'])
    return unique, context, ids


def valid_citations(answer, citations, context_ids):
    if not isinstance(answer, str) or not answer.strip() or not isinstance(citations, list) or not citations:
        return False
    if any(not isinstance(cid, str) for cid in citations) or len(set(citations)) != len(citations):
        return False
    inline = re.findall(r'\[([^\[\]\n]+)\]', answer)
    return set(inline) == set(citations) and set(citations) <= set(context_ids)


def render_citations(answer, citations, context_ids):
    """Normalize presentation only; reject unknown IDs, never infer support."""
    if not isinstance(answer, str) or not answer.strip() or not isinstance(citations, list) or not citations:
        return None
    if any(not isinstance(cid, str) for cid in citations):
        return None
    ids = [cid.strip().removeprefix('[').removesuffix(']').strip() for cid in citations]
    if len(set(ids)) != len(ids) or not set(ids) <= set(context_ids):
        return None
    for group in re.findall(r'\[([^\[\]\n]+)\]', answer):
        grouped_ids = [cid.strip() for cid in group.split(',')]
        if not set(grouped_ids) <= set(ids):
            return None
        answer = answer.replace('[' + group + ']', ' '.join('[' + cid + ']' for cid in grouped_ids))
    existing = set(re.findall(r'\[([^\[\]\n]+)\]', answer))
    missing = [cid for cid in ids if cid not in existing]
    if missing:
        answer = answer.rstrip() + ' ' + ' '.join('[' + cid + ']' for cid in missing)
    return (answer, ids) if valid_citations(answer, ids, context_ids) else None


def run_agent(question, controller, tools, config, *, filters=None):
    validate_config(config)
    filters = validate_search(question, filters, config['top_k'])
    events, searches, candidates = [], [], []
    context, context_ids = '', []
    previous_call, feedback = None, None
    start_record = len(controller.records)
    started = time.perf_counter()

    def finish(status, *, reason, answer=ABSTENTION, citations=None):
        citations = citations or []
        by_id = {c['id']: c for c in candidates}
        return {'status': status, 'answer': answer, 'citations': citations, 'stop_reason': reason,
                'citation_sources': [{'id': cid, 'source': by_id[cid]['source'], 'page': by_id[cid]['page']}
                                     for cid in citations],
                'context': context, 'context_ids': context_ids, 'context_chars': len(context),
                'context_budget_chars': config['context_budget_chars'], 'events': events,
                'search_count': len(searches), 'model_calls': controller.records[start_record:],
                'elapsed_ms': (time.perf_counter() - started) * 1000}

    try:
        for _ in range(config['max_model_calls']):
            allowed = list(config['allowed_search_tools']) if len(searches) < config['max_searches'] else []
            if searches:
                allowed += ['submit_answer', 'abstain']
            messages = [{'role': 'system', 'content': system_prompt(config)},
                        {'role': 'user', 'content': json.dumps({'question': question, 'user_filter': filters,
                         'searches_used': len(searches), 'max_searches': config['max_searches']}, ensure_ascii=False)}]
            if feedback:
                messages.insert(1, {'role': 'system', 'content': 'Kiểm tra của ứng dụng: ' + feedback})
            if previous_call:
                # Prior raw tool outputs are absent: only the current context is model-visible.
                messages += [previous_call['assistant_message'], {'role': 'tool',
                    'tool_call_id': previous_call['call_id'], 'content': json.dumps({
                    'data_only': True, 'context': context, 'context_ids': context_ids,
                    'search_history': searches, 'validation_feedback': feedback,
                    'searches_remaining': config['max_searches'] - len(searches)}, ensure_ascii=False)}]
            action = controller.decide(messages, allowed)
            name, args = action['name'], action['arguments']
            if name not in allowed or not isinstance(args, dict):
                raise ValueError('Invalid model action')
            previous_call, feedback = action, None
            events.append({'event': 'tool_call', 'tool': name, 'arguments': args, 'call_id': action['call_id']})
            if name in SEARCH_TOOLS:
                if set(args) != {'query'} or not isinstance(args['query'], str) or not args['query'].strip() or len(args['query']) > 2000:
                    raise ValueError('Invalid search arguments')
                query = args['query']
                identity = (name, ' '.join(query.casefold().split()))
                if any((s['tool'], ' '.join(s['query'].casefold().split())) == identity for s in searches):
                    events.append({'event': 'repeated_search', 'tool': name, 'query': query})
                    return finish('abstain', reason='repeated_search')
                searches.append({'tool': name, 'query': query})
                event = {'event': 'search', 'tool': name, 'query': query, 'query_original': question,
                         'filter': filters, 'filter_origin': 'explicit user input, fixed by application',
                         'top_k': config['top_k'], 'candidate_k': config['candidate_k'], 'status': 'running'}
                events.append(event)
                begin = time.perf_counter()
                try:
                    result = tools.search(name, query, filters=filters)
                except Exception as exc:
                    event.update(status='error', error_type=type(exc).__name__, elapsed_ms=(time.perf_counter()-begin)*1000)
                    raise
                rows = result['results']
                if len(rows) > config['top_k'] or len({r['id'] for r in rows}) != len(rows):
                    raise ValueError('Invalid retrieval result count/IDs')
                if any(any(r['metadata'].get(k) != v for k, v in filters.items()) for r in rows):
                    raise ValueError('Retrieval violated user filter')
                old_ids = set(context_ids)
                candidates, context, context_ids = update_context(candidates, rows, config)
                event.update(status='ok', results=rows, branches=result.get('branches', {}),
                             context=context, context_ids=context_ids, context_chars=len(context),
                             newly_visible_ids=sorted(set(context_ids)-old_ids), elapsed_ms=(time.perf_counter()-begin)*1000)
            elif name == 'submit_answer':
                if set(args) != {'answer', 'citations'}:
                    raise ValueError('Invalid answer arguments')
                rendered = render_citations(args['answer'], args['citations'], context_ids)
                if rendered:
                    answer, citations = rendered
                    events.append({'event': 'answer', 'structural_citations_valid': True,
                                   'format_normalized': (answer, citations) != (args['answer'], args['citations']),
                                   'note': 'Semantic support still requires source review.'})
                    return finish('answered', reason='model_answer', answer=answer, citations=citations)
                feedback = 'Citation không hợp lệ: dùng đúng và đủ ID trong context hiện tại và dạng [id], hoặc abstain.'
                events.append({'event': 'invalid_citations', 'rejected_answer': args})
            elif name == 'abstain':
                if set(args) != {'reason'} or not isinstance(args['reason'], str) or not args['reason'].strip():
                    raise ValueError('Invalid abstention arguments')
                events.append({'event': 'abstain', 'model_reason': args['reason']})
                return finish('abstain', reason='model_insufficient_evidence')
        return finish('abstain', reason='model_call_limit')
    except Exception as exc:
        events.append({'event': 'error', 'error_type': type(exc).__name__})
        result = finish('error', reason='execution_error', answer='')
        result['error_type'] = type(exc).__name__
        return result

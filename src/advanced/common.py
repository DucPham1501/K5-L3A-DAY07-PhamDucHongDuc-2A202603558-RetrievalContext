import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/advance'
PDF = DATA / '2303.08774v6.pdf'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def image_part(path):
    data = base64.b64encode(Path(path).read_bytes()).decode('ascii')
    return {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + data, 'detail': 'high'}}


def client():
    from dotenv import load_dotenv
    from openai import OpenAI
    load_dotenv(ROOT / '.env', encoding='utf-8-sig')
    return OpenAI(timeout=90, max_retries=1)


def usage(response):
    return {'request_id': response._request_id, 'model': response.model,
            **response.usage.model_dump()}


def cost(records, prices):
    total = 0
    for record in records:
        cached = (record.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0
        total += ((record['prompt_tokens'] - cached) * prices['input']
                  + cached * prices['cached_input'] + record['completion_tokens'] * prices['output']) / 1e6
    return total

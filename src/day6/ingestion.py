"""Read and normalize source data. TODO: implement functions.

Original starter TODOs are retained for reference; implementations are below.
"""
import json, logging, re, unicodedata
from pathlib import Path
from .models import DocumentPage

def normalize_text(text: str) -> str:
    """TODO: normalize Unicode and whitespace without discarding useful structure."""
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n').replace('\r', '\n')
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(re.sub(r'[^\S\n]+', ' ', l).strip() for l in text.split('\n'))).strip()

def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """TODO: extract each physical page; keep its page number and source.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    from pypdf import PdfReader
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        text = normalize_text(page.extract_text() or '')
        if not text:
            logging.error('Empty PDF page, OCR required: %s:%s', document_id, number)
        pages.append(DocumentPage(document_id, source, number, text))
    return pages

def load_corpus(path, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    expected = {(d['source_id'], p): d for d in manifest['documents'] for p in d['included_pages']}
    pages, seen = [], set()
    for line in path.read_text(encoding='utf-8').splitlines():
        obj = json.loads(line)
        key = (obj['document_id'], obj['page'])
        if key not in expected or key in seen:
            raise ValueError(f'Unexpected/duplicate page: {key}')
        seen.add(key)
        text = normalize_text(obj['text'])
        if not text or text != obj['text']:
            logging.error('Empty or changed normalized corpus page: %s', key)
            raise ValueError(f'Invalid frozen corpus page: {key}')
        for field in ('doc_type', 'year'):
            if obj['metadata'][field] != expected[key][field]:
                raise ValueError(f'Metadata mismatch: {key} {field}')
        pages.append(DocumentPage(obj['document_id'], obj['source'], obj['page'], text, obj['metadata']))
    if seen != set(expected) or len(pages) < 30:
        raise ValueError('Missing pages or fewer than 30 content pages')
    return pages

import hashlib
import re
from .models import Chunk

def make_chunk(page, start, end, method):
    while start < end and page.text[start].isspace(): start += 1
    while end > start and page.text[end-1].isspace(): end -= 1
    text = page.text[start:end]
    identity = f'{page.document_id}:{page.page}:{method}:{start}:{end}:{text}'
    return Chunk(hashlib.sha256(identity.encode()).hexdigest(), page.document_id, page.source, page.page, text,
                 {**page.metadata, 'start_char':start, 'end_char':end, 'chunking':method})

def fixed_size(page, size, overlap):
    if size < 1 or not 0 <= overlap < size: raise ValueError('Invalid size/overlap')
    chunks = []
    for start in range(0, len(page.text), size-overlap):
        end = min(start+size, len(page.text))
        if page.text[start:end].strip(): chunks.append(make_chunk(page,start,end,'fixed'))
        if end == len(page.text): break
    return chunks

def by_paragraph(page, max_size):
    if max_size < 1: raise ValueError('max_size must be positive')
    starts = sorted({0, *[m.start() for m in re.finditer(r'(?m)^(?:Điều \d+\.|Chương [IVX]+\b|\d+\. |[a-zđ]\) )|(?<=\n)\n+',page.text)]})
    pieces = []
    for a,b in zip(starts,starts[1:]+[len(page.text)]):
        while b-a > max_size:
            cut = page.text.rfind(' ',a,a+max_size+1)
            if cut <= a: cut = a+max_size
            pieces.append((a,cut)); a=cut
        if page.text[a:b].strip(): pieces.append((a,b))
    grouped = []
    for a,b in pieces:
        heading = re.match(r'(Điều \d+\.|Chương [IVX]+\b)',page.text[a:b])
        if grouped and not heading and b-grouped[-1][0] <= max_size:
            grouped[-1]=(grouped[-1][0],b)
        else: grouped.append((a,b))
    return [make_chunk(page,a,b,'paragraph') for a,b in grouped]

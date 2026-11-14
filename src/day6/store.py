import json, math

class PgVectorStore:
    def __init__(self,database_url,dimensions,namespace='openai-small-1536-v1'):
        import psycopg
        if not database_url: raise ValueError('DATABASE_URL missing')
        self.conn=psycopg.connect(database_url,connect_timeout=5,autocommit=True)
        self.dimensions,self.namespace=dimensions,namespace

    def vector_literal(self,v):
        if len(v)!=self.dimensions or not all(math.isfinite(x) for x in v) or not any(v): raise ValueError('Invalid vector')
        return '['+','.join(str(float(x)) for x in v)+']'

    def create_schema(self):
        with self.conn.transaction():
            self.conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
            self.conn.execute('''CREATE TABLE IF NOT EXISTS day6_chunks (
                namespace text NOT NULL, strategy text NOT NULL, chunk_id text NOT NULL,
                document_id text NOT NULL, source text NOT NULL, page integer NOT NULL,
                content text NOT NULL, metadata jsonb NOT NULL, embedding vector NOT NULL,
                PRIMARY KEY(namespace,strategy,chunk_id))''')

    def upsert(self,strategy,chunks,vectors):
        if strategy not in ('A','B','C') or not chunks or len(chunks)!=len(vectors): raise ValueError('Invalid store input')
        if len({c.chunk_id for c in chunks})!=len(chunks): raise ValueError('Duplicate chunk IDs')
        rows=[(self.namespace,strategy,c.chunk_id,c.document_id,c.source,c.page,c.text,json.dumps(c.metadata,ensure_ascii=False),self.vector_literal(v)) for c,v in zip(chunks,vectors)]
        with self.conn.transaction():
            self.conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(self.namespace+strategy,))
            self.conn.execute('DELETE FROM day6_chunks WHERE namespace=%s AND strategy=%s',(self.namespace,strategy))
            with self.conn.cursor() as cur:
                cur.executemany('''INSERT INTO day6_chunks VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::vector)
                    ON CONFLICT(namespace,strategy,chunk_id) DO UPDATE SET content=excluded.content,
                    metadata=excluded.metadata, embedding=excluded.embedding''',rows)

    def snapshot_ids(self,strategy):
        return [r[0] for r in self.conn.execute('SELECT chunk_id FROM day6_chunks WHERE namespace=%s AND strategy=%s ORDER BY chunk_id',(self.namespace,strategy)).fetchall()]

    def search(self,strategy,query_vector,top_k=3,filters=None):
        filters=filters or {}
        if strategy not in ('A','B','C') or not 1<=top_k<=100: raise ValueError('Invalid strategy/top_k')
        if strategy!='C' and filters: raise ValueError('Only C applies filters')
        for k,v in filters.items():
            if k not in ('doc_type','year') or (k=='year' and type(v)is not int) or (k=='doc_type' and not isinstance(v,str)): raise ValueError('Invalid metadata filter')
        literal=self.vector_literal(query_vector)
        rows=self.conn.execute('''SELECT chunk_id,document_id,source,page,content,metadata,1-(embedding <=> %s::vector) AS score
            FROM day6_chunks WHERE namespace=%s AND strategy=%s AND metadata @> %s::jsonb
            ORDER BY embedding <=> %s::vector,chunk_id LIMIT %s''',(literal,self.namespace,strategy,json.dumps(filters),literal,top_k)).fetchall()
        return [dict(zip(('chunk_id','document_id','source','page','text','metadata','score'),r)) for r in rows]

    def versions(self):
        r=self.conn.execute("SELECT current_setting('server_version'),extversion FROM pg_extension WHERE extname='vector'").fetchone()
        return {'postgresql':r[0],'pgvector':r[1],'metric':'cosine','search':'exact','table':'day6_chunks'}

    def close(self): self.conn.close()

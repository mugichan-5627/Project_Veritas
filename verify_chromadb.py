import sys
print('='*60)
print('ChromaDB BGE-M3 Rebuild Verification')
print('='*60)

# Step 1: Check ChromaDB collections exist
print('\n[1] Collection Chunk Counts')
print('-'*40)
import chromadb
client = chromadb.PersistentClient(
    path='C:/Users/Moosa/Downloads/Project_Veritas/project_veritas/memory/chroma_db'
)
collections = client.list_collections()
total = 0
for col in collections:
    count = col.count()
    total += count
    # Flag if suspiciously low
    flag = ' <- CHECK THIS' if count < 100 and col.name != 'current_deal' else ''
    print(f'  {col.name:<30} {count:>6} chunks{flag}')
print(f'  {"TOTAL":<30} {total:>6} chunks')

# Step 2: Check embedding dimension on each collection
print('\n[2] Embedding Dimension Check (must be 1024 for BGE-M3)')
print('-'*40)
for col in collections:
    if col.count() == 0:
        print(f'  {col.name:<30} EMPTY — skip')
        continue
    try:
        sample = col.get(limit=1, include=['embeddings'])
        if sample['embeddings']:
            dim = len(sample['embeddings'][0])
            status = 'OK' if dim == 1024 else f'WRONG — expected 1024'
            print(f'  {col.name:<30} dim={dim} {status}')
        else:
            print(f'  {col.name:<30} No embeddings returned')
    except Exception as e:
        print(f'  {col.name:<30} ERROR: {e}')

# Step 3: Test semantic query on each active collection
print('\n[3] Semantic Query Test (checks retrieval is working)')
print('-'*40)

from FlagEmbedding import BGEM3FlagModel
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

def query_collection(col_name, query_text):
    try:
        col = client.get_collection(
            name=col_name,
            embedding_function=None  # we pass embeddings manually
        )
        if col.count() == 0:
            print(f'  {col_name}: EMPTY')
            return
        # Embed the query
        result = model.encode([query_text])['dense_vecs']
        query_embedding = result[0].tolist()
        # Query
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=2,
            include=['documents', 'metadatas', 'distances']
        )
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        dists = results['distances'][0]
        print(f'\n  Collection: {col_name}')
        for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
            source = meta.get('source', 'unknown')
            preview = doc[:80].replace('\n', ' ')
            print(f'    Result {i+1}: [{source}] dist={dist:.3f}')
            print(f'             "{preview}..."')
    except Exception as e:
        print(f'  {col_name}: ERROR — {e}')

query_collection('valuation_methodology',  'WACC terminal value DCF calculation')
query_collection('forensic_and_credit',    'board independence governance red flags')
query_collection('india_market_context',   'India PE deal market regulatory environment')
query_collection('forensic_and_credit',    'promoter pledge insider trading SEBI')

# Step 4: Minimum chunk count thresholds
print('\n[4] Pass/Fail Thresholds')
print('-'*40)
thresholds = {
    'valuation_methodology':  4000,
    'forensic_and_credit':    2000,
    'india_market_context':    200,
    'current_deal':              0,
}
all_pass = True
for col in collections:
    count = col.count()
    threshold = thresholds.get(col.name, 0)
    passed = count >= threshold
    if not passed:
        all_pass = False
    status = 'PASS' if passed else f'FAIL (need >={threshold})'
    print(f'  {col.name:<30} {count:>6} chunks — {status}')

print()
if all_pass:
    print('ALL CHECKS PASSED — safe to build Agent 5')
else:
    print('FAILURES DETECTED — fix before building Agent 5')
print('='*60)

from FlagEmbedding import BGEM3FlagModel
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
print('Loading BGE-M3 model (downloading ~2.4GB)...')
model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)
result = model.encode(['EBITDA margin expansion driven by operating leverage'])
vecs = result['dense_vecs']
print(f'Embedding dimension: {len(vecs[0])}')
print('Expected: 1024')
print('BGE-M3 WORKING')

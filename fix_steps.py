import re

with open('test_full_pipeline.py', 'r') as f:
    text = f.read()

text = re.sub(r'print\(f"\\n============================================================"\)\s*print\(f"  STEP 4: Multi-Agent Investment Committee Debate"\)\s*print\(f"  LLM: NVIDIA NIM \(" \+ NVIDIA_MODEL \+ "\)"\)\s*print\(f"============================================================\\n"\)', 'next_step("Multi-Agent Investment Committee Debate")\n    print(f"  LLM: NVIDIA NIM ({NVIDIA_MODEL})")', text)

text = re.sub(r'print\(f"\\n" \+ "=" \* 60\)\s*print\(f"  STEP 5: Final IC Memo Generation"\)\s*print\("=" \* 60 \+ "\\n"\)', 'next_step("Final IC Memo Generation")', text)

with open('test_full_pipeline.py', 'w') as f:
    f.write(text)

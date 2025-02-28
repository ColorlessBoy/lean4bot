import json
from LLMService import LLMService
import sys
from pathlib import Path
from tqdm import tqdm

with open("theorems.json", "r", encoding="utf-8") as f:
    theorems = json.load(f)

root = Path(__file__).parent / "TestDeepseekR1"

aliyunService = LLMService("TestDeepseekR1")

for theorem in tqdm(theorems[:3]):
    output = root / (theorem["name"] + ".json")
    if output.exists():
        continue
    code = "```lean\nimport MiniF2F.Minif2fImport\nopen BigOperators Real Nat Topology\nnamespace PlayGround\n"+theorem["code"]+"\n```"
    message = aliyunService.chatSession(code, theorem["name"])
    with open(output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

aliyunService.release()
sys.exit(0)

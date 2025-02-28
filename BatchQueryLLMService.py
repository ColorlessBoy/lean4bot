import json
from LLMService import LLMService
import sys
from pathlib import Path
from tqdm import tqdm

with open("theorems.json", "r", encoding="utf-8") as f:
    theorems = json.load(f)

root = Path(__file__).parent / "TestDeepseekR1"

aliyunService = LLMService("TestDeepseekR1")

for theorem in tqdm(theorems[:2]):
    output = root / (theorem["name"] + ".json")
    if output.exists():
        continue
    code = "\nimport MiniF2F.Minif2fImport\nopen BigOperators Real Nat Topology\nnamespace PlayGround\n"+theorem["code"]+"\n"
    """
    if "<" in code:
        print("skip", theorem["name"])
        continue
    """
    message = aliyunService.chatSession(code, theorem["name"])
    with open(output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

aliyunService.release()
sys.exit(0)

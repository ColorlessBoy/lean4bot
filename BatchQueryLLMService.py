import json
from LLMService import LLMService
import sys
from pathlib import Path
from tqdm import tqdm

with open("theorems.json", "r", encoding="utf-8") as f:
    theorems = json.load(f)

root = Path(__file__).parent / "TestQwq"

aliyunService = LLMService("TestQwq")

for theorem in tqdm(theorems):
    output = root / (theorem["name"] + ".json")
    if output.exists():
        continue
    code = "\nimport MiniF2F.Minif2fImport\nopen BigOperators Real Nat Topology\nnamespace PlayGround\n"+theorem["code"]+"\n"
    """
    # 阿里云的deepseek-r1的奇怪bug
    if "<" in code:
        print("skip", theorem["name"])
        continue
    """
    message = aliyunService.chatSession(code, theorem["name"])
    if message is None:
        continue
    with open(output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

aliyunService.release()
sys.exit(0)

import os
import sys
from openai import OpenAI
from LeanServer import LeanServer
import json
from initPrompt import initPrompt
import re
import argparse
import hashlib

"""
# 阿里云 
API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "deepseek-v3"
"""
# 火山云 
API_KEY = os.getenv("ARK_API_KEY")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "deepseek-v3-241226"

class LLMService:
    def __init__(self, name: str, projectPath: str = None):
        self.client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
        )
        self.leanServer = LeanServer(name, projectPath=projectPath)

    def release(self):
        self.client.close()
        self.leanServer.release()

    @staticmethod
    def __hash_code__(code: str) -> str:
        """计算代码的哈希值"""
        # 移除空白字符后再计算哈希值
        normalized_code = ' '.join(code.split())
        return hashlib.md5(normalized_code.encode('utf-8')).hexdigest()

    def chatSession(self, question, maxTries=10):
        messages = [*initPrompt]
        messages.append(
            {
                "role": "user",
                "content": "上一题你证明正确。请听下一题："
                + question,
            },
        )
        code_counts: dict[str, int] = {}
        for _ in range(maxTries):
            try:
                stream = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    stream=True,  # 启用流式输出
                    temperature=0.6,
                    max_tokens=16384,
                )
                response = LLMService.__processStreamResponse__(stream)
                messages.append({"role": "assistant", "content": response["content"]})
                answer = LLMService.__extractJsonContent__(response["content"])
                answer = json.loads(answer)
                print("answer:", answer)
                current_code = answer["code"]
                code_hash = self.__hash_code__(answer["code"])
                if code_hash in code_counts:
                    if code_counts[code_hash] >= 3:
                        print("\n连续3次生成重复代码，系统决定终止本次证明尝试。")
                        messages.append(
                            {
                                "role": "user",
                                "content": "由于连续3次生成重复代码，系统决定终止本次证明尝试。"
                            }
                        )
                        break
                    code_counts[code_hash] += 1
                    print(f"\n第 {code_counts[current_code]} 次出现相同的代码，请重新思考并给出不同的证明方法。")
                    messages.append({
                        "role": "user",
                        "content": f"这是第 {code_counts[current_code]} 次出现相同的代码，请重新思考并给出不同的证明方法。"
                    })
                    continue
                else:
                    code_counts[code_hash] = 1
                info = self.leanServer.getCodeInfo(answer["code"])
                if len(info["diagnostics"]) > 0:
                    print("\nerror diagnostics")
                    response_info = {"diagnostics": info["diagnostics"]}
                    print("response_info:", response_info)
                    messages.append(
                        {
                            "role": "user",
                            "content": f"回复的格式不错，请保持。证明代码有报错，不要被示例里的intro误导，你可能不需要。注意中间的错误会导致后续证明都有问题，顺便提醒一下你应该在description中包含对报错信息的理解，避免重复犯错：```json {json.dumps(response_info, ensure_ascii=False)} ```",
                        }
                    )
                else:
                    """
                    key = LLMService.__compareInfo__(answer["info"], info["goals"])
                    print("key:", key)
                    if key:
                        print("\nerror info", info["goals"][key])
                        response_info = {key: info["goals"][key]}
                        print("response_info:", response_info)
                        messages.append(
                            {
                                "role": "user",
                                "content": f"回复的格式不错，请保持。你虽然证明了题目，但是过程info有错误，注意info的编号，可以造成累积错误：```json {json.dumps(response_info, ensure_ascii=False)} ```",
                            }
                        )
                    else:
                    """
                    print("\n证明成功\ninfo:", info)
                    messages.append(
                        {
                            "role": "user",
                            "content": "你的证明完全正确。",
                        }
                    )
                    break
            except Exception as e:
                print(f"\n请求出错：{str(e)}")
                break
        return messages

    def __processStreamResponse__(stream, isStream=True):
        """处理流式响应，收集完整回复"""
        full_reasoning = ""
        full_content = ""

        for chunk in stream:
            if isStream:
                # 实时打印流式输出
                if hasattr(chunk.choices[0].delta, "reasoning_content"):
                    reasoning = chunk.choices[0].delta.reasoning_content or ""
                    print(reasoning, end="", flush=True)
                    full_reasoning += reasoning

                if hasattr(chunk.choices[0].delta, "content"):
                    content = chunk.choices[0].delta.content or ""
                    print(content, end="", flush=True)
                    full_content += content
            else:
                # 非流式处理
                full_reasoning = chunk.choices[0].message.reasoning_content
                full_content = chunk.choices[0].message.content

        return {"reasoning": full_reasoning.strip(), "content": full_content.strip()}

    def __extractJsonContent__(text):
        """从markdown代码块中提取JSON内容"""
        pattern = r"```json\n?(.*?)\n?```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def __compareInfo__(
        responseInfo: dict[str, list[str]], leanInfo: dict[str, list[str]]
    ):
        for key, value in leanInfo.items():
            if key not in responseInfo or str(value) != str(leanInfo[key]):
                return key
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run LLM Service with custom output file"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="message.json",
        help="Output file path (default: message.json)",
    )
    parser.add_argument(
        "-p",
        "--projectPath",
        default=None,
        help="Path to Lean project directory",
    )
    parser.add_argument(
        "-q",
        "--question",
        default="import MiniF2F.Minif2fImport\nopen BigOperators Real Nat Topology\nnamespace PlayGround\ntheorem Exists.imp {α : Sort u} {p q : α -> Prop} (h1 : ∀ (a : α), p a -> q a) (h2 : Exists p) : Exists q := by",
        help="Question to process",
    )
    args = parser.parse_args()

    aliyunService = LLMService("test")
    message = aliyunService.chatSession(args.question)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

    aliyunService.release()
    sys.exit(0)

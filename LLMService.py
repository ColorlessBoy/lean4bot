import os
import sys
from openai import OpenAI
from LeanServer import LeanServer
import json
from initPrompt import initPrompt
import re
import argparse


class LLMService:
    def __init__(self, name: str, projectPath: str = None):
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.leanServer = LeanServer(name, projectPath=projectPath)

    def release(self):
        self.client.close()
        self.leanServer.release()

    def chatSession(self, question, maxTries=10):
        messages = initPrompt
        messages.append(
            {
                "role": "user",
                "content": "上一题你证明对了，过程理解也是正确的。请听下一题："
                + question,
            },
        )
        for _ in range(maxTries):
            try:
                stream = self.client.chat.completions.create(
                    model="deepseek-v3",
                    messages=messages,
                    stream=True,  # 启用流式输出
                    temperature=0.7,
                )
                response = LLMService.__processStreamResponse__(stream)
                messages.append({"role": "assistant", "content": response["content"]})
                answer = LLMService.__extractJsonContent__(response["content"])
                answer = json.loads(answer)
                print("answer:", answer)
                info = self.leanServer.getCodeInfo(answer["code"])
                if len(info["diagnostics"]) > 0:
                    print("\nerror diagnostics")
                    response_info = {"diagnostics": info["diagnostics"]}
                    print("response_info:", response_info)
                    messages.append(
                        {
                            "role": "user",
                            "content": f"回复的格式不错，请保持。证明代码有报错，注意中间的错误会导致后续证明都有问题：```json {json.dumps(response_info, ensure_ascii=False)} ```",
                        }
                    )
                else:
                    key = LLMService.__compareInfo__(answer["info"], info["goals"])
                    print("key:", key)
                    if key:
                        print("\nerror info", info["goals"][key])
                        response_info = {key: info["goals"][key]}
                        print("response_info:", response_info)
                        messages.append(
                            {
                                "role": "user",
                                "content": f"回复的格式不错，请保持。你虽然证明了题目，但是过程info有一步是错的，可能导致后面都是错的：```json {json.dumps(response_info, ensure_ascii=False)} ```",
                            }
                        )
                    else:
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
        default="import MiniF2F.Minif2fImport\\nopen BigOperators Real Nat Topology\\nnamespace PlayGround\\nimport MiniF2F.Minif2fImport\\nopen BigOperators Real Nat Topology\\nnamespace PlayGround\\ntheorem And.comm : ∀ {a b : Prop}, a ∧ b → b ∧ a := by",
        help="Question to process",
    )
    args = parser.parse_args()

    aliyunService = LLMService("test")
    message = aliyunService.chatSession(args.question)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

    aliyunService.release()
    sys.exit(0)

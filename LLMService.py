import os
import sys
from openai import OpenAI
from LeanServer import LeanServer
import json
from initPrompt import initPrompt
import re
import argparse
import hashlib

# 阿里云 
API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "deepseek-r1"
"""
# 火山云 
API_KEY = os.getenv("ARK_API_KEY")
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
# MODEL_NAME = "deepseek-v3-241226"
MODEL_NAME = "deepseek-r1-250120"
"""

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

    def chatSession(self, question, name, maxTries=10):
        question = question.strip()
        messages = [*initPrompt]
        messages.append({
            "role": "user",
            "content": "上一题你证明正确。请听下一题(请注意回答的code字段代码要保持原题目不变，不要忽略小于号）：" + question,
        })
        code_counts: dict[str, int] = {}
        
        for _ in range(maxTries):
            try:
                stream = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    stream=True,
                    temperature=0.6,
                    max_tokens=16384,
                )
                
                # 添加调试日志
                print("\n开始处理响应流...")
                response, hasRepeat = LLMService.__processStreamResponse__(stream)
                print("\n响应内容:", json.dumps(response, ensure_ascii=False, indent=2))
                
                try:
                    print("\n提取JSON内容...")
                    answer = LLMService.__extractJsonContent__(response["content"])
                    messages.append({
                        "role": "assistant",
                        "content": response["content"],
                    })
                    if hasRepeat:
                        messages.append({
                            "role": "user",
                            "content": "你进入逻辑混乱的死循环状态了，非常危险，请重新思考正确答案。"
                        })
                        continue
                    print("\n解析前的JSON字符串:", answer)
                    answer = json.loads(answer)
                    print("\n解析后的JSON对象:", json.dumps(answer, ensure_ascii=False, indent=2))
                except json.JSONDecodeError as je:
                    print(f"\nJSON解析错误位置: 行 {je.lineno}, 列 {je.colno}")
                    print(f"错误信息: {je.msg}")
                    print(f"原始内容:\n{response['content']}")
                    messages.append({
                        "role": "user",
                        "content": '你是不是忘记遵循格式了```json\n{"description":xxx,"info":xxx,"code":xxx}\n```'
                    })
                    continue  # 不要立即终止，给出另一次尝试的机会
                except Exception as e:
                    print(f"\n其他错误: {type(e).__name__}")
                    print(f"错误信息: {str(e)}")
                    print(f"原始内容:\n{response['content']}")
                    messages.append({
                        "role": "user",
                        "content": f"其他错误: {type(e).__name__}，{str(e)}"
                    })
                    continue
                    
                current_code = answer["code"].strip()
                if name not in current_code:
                    # 简单防作弊检查 
                    print("\n题目被修改")
                    messages.append({
                        "role": "user",
                        "content": f"题目被你修改了，这是严重的作弊行为。请新作答：{question}"
                    })
                    continue
                if "namespace PlayGround" not in current_code:
                    current_code = "namespace PlayGround\n" + current_code
                if "open BigOperators Real Nat Topology" not in current_code:
                    current_code = "open BigOperators Real Nat Topology\n" + current_code
                if "import MiniF2F.Minif2fImport" not in current_code:
                    current_code = "import MiniF2F.Minif2fImport\n" + current_code

                code_hash = self.__hash_code__(current_code)
                if code_hash in code_counts:
                    code_counts[code_hash] += 1
                    if code_counts[code_hash] >= 3:
                        print("\n超过3次生成重复代码，系统决定终止本次证明尝试。")
                        messages.append(
                            {
                                "role": "user",
                                "content": "由于连续3次生成重复代码，系统决定终止本次证明尝试。"
                            }
                        )
                        break
                    print(f"\n你第 {code_counts[code_hash]} 次提交相同的错误代码，智者不会在同一一个地方摔倒两次，请重新思考并给出不同的证明方法。")
                    messages.append({
                        "role": "user",
                        "content": f"你第 {code_counts[code_hash]} 次提交相同的错误代码，智者不会在同一一个地方摔倒两次，请重新思考并给出不同的证明方法。 {str(self.leanServer.diagnostics)}"
                    })
                    continue
                else:
                    code_counts[code_hash] = 1
                info = self.leanServer.getCodeInfo(current_code)
                print("\n获取到的代码信息:", json.dumps(info, ensure_ascii=False, indent=2))

                if info is None:
                    print("\n获取代码信息失败")
                    messages.append({
                        "role": "user",
                        "content": "获取代码信息失败，请重新生成证明。"
                    })
                    continue

                if len(info["diagnostics"]) > 0:
                    print("\nerror diagnostics")
                    response_info = {"diagnostics": info["diagnostics"]}
                    json_response_info = json.dumps(response_info, ensure_ascii=False)
                    print("response_info:", json_response_info)
                    if "tactic 'introN' failed" in json_response_info:
                        json_response_info = "请不要被示例里的intro误导，可能根本不需要intro。" + json_response_info
                    messages.append(
                        {
                            "role": "user",
                            "content": f"回复的格式不错，请保持。证明代码有报错，注意中间的错误会导致后续证明都有问题，顺便提醒一下你应该在description中包含对报错信息的理解，避免重复犯错：```json {json.dumps(response_info, ensure_ascii=False)} ```",
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
                print("\n请求出错详细信息:")
                print(f"错误类型: {type(e).__name__}")
                print(f"错误信息: {str(e)}")
                print("堆栈跟踪:")
                import traceback
                traceback.print_exc()
                break
                
        return messages
    
    def __hasRepeat__(content: str, window = 100, threshold = 10) -> bool:
        if len(content) <= window * threshold:
            return False
        pattern = content[-window:]  # 获取最后window个字符
        if not pattern.strip():  # 忽略纯空白的模式
            return False
            
        # 计算重叠出现的次数
        count = 0
        pos = 0
        while True:
            pos = content.find(pattern, pos)
            if pos == -1:
                break
            count += 1
            pos += 1  # 移动一个字符继续查找
            
        return count > threshold

    def __processStreamResponse__(stream, isStream=True):
        """处理流式响应，收集完整回复"""
        full_reasoning = ""
        full_content = ""
        hasRepeat = False

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
                    if LLMService.__hasRepeat__(full_content):
                        print("\n检测到重复内容，终止流式处理")
                        hasRepeat = True
                        break
            else:
                # 非流式处理
                full_reasoning = chunk.choices[0].message.reasoning_content
                full_content = chunk.choices[0].message.content

        return {"reasoning": full_reasoning.strip(), "content": full_content.strip()}, hasRepeat

    @staticmethod
    def __extractJsonContent__(text):
        """从markdown代码块中提取JSON内容"""
        print("\n开始提取JSON内容...")
        print(f"输入文本:\n{text}")
        
        # 检查是否是完整的JSON
        try:
            json.loads(text)
            print("输入已经是有效的JSON")
            return text
        except json.JSONDecodeError:
            # 不是完整JSON，尝试从markdown中提取
            pattern = r"```json\n?(.*?)\n?```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                print(f"从markdown提取的内容:\n{content}")
                return content
            
            print("未找到JSON代码块，返回原始文本")
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
    parser.add_argument(
        "-n",
        "--name",
        default="Exists.imp",
        help="Question name",
    )
    args = parser.parse_args()

    aliyunService = LLMService("test")
    message = aliyunService.chatSession(args.question, args.name)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)

    aliyunService.release()
    sys.exit(0)

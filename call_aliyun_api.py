import os
import sys
from openai import OpenAI
from LeanServer import LeanServer
import json
from prompt import initPrompt
import re

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
leanServer = LeanServer("test")


def process_stream_response(stream, is_stream=True):
    """处理流式响应，收集完整回复"""
    full_reasoning = ""
    full_content = ""

    for chunk in stream:
        if is_stream:
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

def extract_json_content(text):
    """从markdown代码块中提取JSON内容"""
    pattern = r"```json\n?(.*?)\n?```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def compare_info(response_info: dict[str, list[str]], lean_info: dict[str, list[str]]):
    if len(response_info) != len(lean_info):
        return False
    for key, value in response_info.items():
        if key not in lean_info or str(value) != str(lean_info[key]):
            return False
    return True


def chat_session():
    messages = initPrompt
    for _ in range(5):
        try:
            stream = client.chat.completions.create(
                model="deepseek-v3",
                messages=messages,
                stream=True,  # 启用流式输出
                temperature=0.7,
            )
            response = process_stream_response(stream)
            with open("api.txt", "a", encoding="utf-8") as f:
                json.dump({"role": "assistant", "content": response["content"]}, f, ensure_ascii=False, indent=2)
                f.write(",\n")
            answer = extract_json_content(response["content"])
            answer = json.loads(answer)
            info = leanServer.getCodeInfo(answer["code"])
            if len(info["diagnostics"]) > 0:
                print("\nerror diagnostics")
                messages.append({"role": "user", "content": f"回复的格式不错，请保持。证明代码有报错：```json {json.dumps(info, ensure_ascii=False)} ```"})
            elif not compare_info(answer["info"], info["goals"]):
                print("\nerror info")
                messages.append({"role": "user", "content": f"回复的格式不错，请保持。你虽然证明了题目，但是过程info有些地方是错的：```json {json.dumps(info, ensure_ascii=False)} ```"})
            else:
                print("\n证明成功\ninfo:", info)
                break
            print("info:", info)
            with open("api.txt", "a", encoding="utf-8") as f:
                json.dump(messages[-1], f, ensure_ascii=False, indent=2)
                f.write(",\n")
        except Exception as e:
            print(f"\n请求出错：{str(e)}")
            break


if __name__ == "__main__":
    chat_session()
    client.close()
    leanServer.release()
    sys.exit(0)

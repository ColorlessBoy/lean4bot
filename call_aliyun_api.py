import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

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

def chat_session():
    messages = []
    
    while True:
        # 获取用户输入
        user_input = input("\n您：")
        if user_input.lower() in ["exit", "quit"]:
            print("对话结束")
            break
            
        messages.append({"role": "user", "content": user_input})
        
        try:
            # 发起流式请求
            stream = client.chat.completions.create(
                model="deepseek-r1",
                messages=messages,
                stream=True,  # 启用流式输出
                temperature=0.7,
                max_tokens=2000
            )
            
            print("\n" + "="*20 + "思考过程" + "="*20)
            response = process_stream_response(stream)
            
            print("\n" + "="*20 + "最终答案" + "="*20)
            print(response['content'])
            
            # 将助理回复加入上下文
            messages.append({
                "role": "assistant",
                "content": response['content'],
                "reasoning_content": response['reasoning']
            })
            
        except Exception as e:
            print(f"\n请求出错：{str(e)}")
            messages.pop()  # 移除失败的输入

if __name__ == "__main__":
    print("开始对话（输入 exit 退出）")
    chat_session()
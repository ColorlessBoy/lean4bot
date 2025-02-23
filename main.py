import subprocess
import json

def send_data(process, data):
    """发送数据到进程"""
    data_with_eof = data + "\x04"
    process.stdin.write(data_with_eof.encode("utf-8"))
    process.stdin.flush()
    output = process.stdout.read()
    try: 
        response = json.loads(output.decode("utf-8"))
        return response
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        print("Raw output:", output)

# 通过管道启动程序 A
process = subprocess.Popen(['python3', 'lean_server.py'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

# 向程序 A 发送数据
with open("LeanProject/test.lean", "r") as f:
    data = f.read()
response = send_data(process, data)
print (response)

# 关闭 stdin 流并发送 EOF
process.stdin.close()

# 等待程序 A 完成执行
process.wait()
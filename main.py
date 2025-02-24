from LeanServer import LeanServer
import logging

# 设置日志配置
logging.basicConfig(
    filename='main.log',  # 日志输出到文件
    level=logging.DEBUG,  # 记录所有级别的日志
    format='%(asctime)s - %(levelname)s - %(message)s'
)

leanServer = LeanServer("test")
# 向程序 A 发送数据
with open("LeanProject/test.lean", "r") as f:
    code = f.read()
info = leanServer.getCodeInfo(code)
print(info)

leanServer.release()
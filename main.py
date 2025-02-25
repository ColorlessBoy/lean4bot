from LeanServer import LeanServer
import logging
from pathlib import Path

# 设置日志配置
logging.basicConfig(
    filename="main.log",  # 日志输出到文件
    level=logging.DEBUG,  # 记录所有级别的日志
    format="%(asctime)s - %(levelname)s - %(message)s",
)

leanServer = LeanServer(
    "test",
    rootPath=Path(__file__).parent / "miniF2F-lean4",
    text=[
        "import MiniF2F.Minif2fImport",
        "open BigOperators Real Nat Topology",
        "namespace PlayGround",
    ],
)
# 向程序 A 发送数据
with open("miniF2F-lean4/test.lean", "r") as f:
    code = f.read()
info = leanServer.getCodeInfo(code)
print(info)

leanServer.release()

import logging
from pathlib import Path
from typing import Optional
import subprocess
from threading import Event
import sys
from pylspclient import LspClient, JsonRpcEndpoint, LspEndpoint
from pylspclient.lsp_pydantic_strcuts import (
    TextDocumentItem,
    LanguageIdentifier,
    Position,
)

# 设置日志配置
logging.basicConfig(
    filename='LeanServer.log',  # 日志输出到文件
    level=logging.DEBUG,  # 记录所有级别的日志
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def toUri(path: Path) -> str:
    """Convert a path to a URI."""
    return str(path.absolute().as_uri())

# 假设这是需要清理的资源
class LeanServer:
    def __init__(self, name, rootPath: Optional[str] = None, fileName: Optional[str] = None, text: list[str] = []):
        if rootPath is None:
            rootPath = Path(__file__).parent / "LeanProject"
        if fileName is None:
            fileName = f"{name}.lean"
        self.name = name
        self.rootPath = rootPath
        self.rootUri = toUri(rootPath)
        self.leanProcess = LeanServer.__initLeanProcess__(rootPath)
        self.diagnostics = {}
        self.diagnostics_updated = Event()  # Add event flag
        self.lspClient = self.__initLspClient__()
        filePath = rootPath / fileName
        self.textDocument: TextDocumentItem = LeanServer.__init_text_document__(filePath, text)
        self.lspClient.didOpen(self.textDocument)
        self.text = text
        logging.info(f"Resource {self.name} initialized.")

    def release(self):
        logging.info(f"Releasing resource {self.name}.")
        if self.leanProcess:
            self.leanProcess.terminate()
            self.leanProcess.wait()
            logging.info("Lean process released.")
        if self.lspClient:
            self.lspClient.shutdown()
            self.lspClient.exit()
            logging.info("Lsp client released.")
        logging.info(f"Resource {self.name} released.")

    def getCodeInfo(self, code : str):
        logging.info("Received request to check_proof")
        self.didChange(code.split("\n"))
        goals = self.getInteractiveGoals()
        diagnostics = self.getDiagnostics()
        logging.debug(f"code: {repr(code)}")
        logging.debug(f"goals: {goals}")
        logging.debug(f"diagnostics: {diagnostics}")
        return {"goals":goals, "diagnostics":diagnostics}

    def didChange(self, text: list[str]) -> any:
        logging.info("didChange() start.")
        logging.debug('\n'.join(text))
        range = {
            "start": {"line": 0, "character": 0},
            "end": {"line": len(self.text), "character": 0},
        }
        params = [{"range": range, "text": "\n".join(text)}]
        self.diagnostics_updated.clear()
        self.lspClient.didChange(self.textDocument, params)
        self.text = text
        logging.info("didChange() successed.")

    
    def getInteractiveGoals(self) -> list[dict]:
        logging.info("getInteractiveGoals() start.")
        result = {}
        sessionId: str = LeanServer.__initRpcSessionId__(self.lspClient, self.textDocument.uri)
        for line in range(len(self.text)):
            position = Position(line=line + 1, character=0)
            params = {
                "method": "Lean.Widget.getInteractiveGoals",
                "params": {
                    "textDocument": self.textDocument.model_dump(),
                    "position": position.model_dump(),
                },
                "sessionId": sessionId,
                "position": position.model_dump(),
                "textDocument": self.textDocument.model_dump(),
            }
            response = self.lspClient.lsp_endpoint.call_method("$/lean/rpc/call", **params)
            if response is None or "goals" not in response:
                result[str(line)] = []
            else:
                goals = [LeanServer.__processGoal__(goal) for goal in response["goals"]]
                result[str(line)] = goals
        logging.info("getInteractiveGoals() successed.")
        return result
    
    def getDiagnostics(self, serverity = 1, timeout = 1):
        logging.info("getDiagnostics() start.")
        logging.info(self.diagnostics)
        if not self.diagnostics_updated.wait(timeout):
            logging.warning(f"Timeout waiting for diagnostics after {timeout} seconds")
        processed_diagnostics = [diag for diag in self.diagnostics[self.textDocument.uri] if int(diag['severity']) <= serverity]
        logging.info("getDiagnostics() end.")
        return processed_diagnostics

    def __initLeanProcess__(rootPath: str) -> subprocess.Popen:
        try:
            logging.info("Lean process start.")
            # Start Lean server subprocess with redirected I/O
            # Using 'lake serve' command with LeanProject directory as working directory
            lean_process = subprocess.Popen(
                ["lake", "serve", "--"],
                cwd=rootPath,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logging.info("Lean process successed.")
            return lean_process
        except Exception as e:
            # Handle any startup failures and ensure clean exit
            logging.error(f"Lean process failed: {e}", file=sys.stderr)
            raise  # Re-raise exception to abort context manager
    
    def __initLspClient__(self):
        def onDiagnostics(params):
            logging.debug("onDiagnostics()", params)
            self.diagnostics[self.textDocument.uri] = params["diagnostics"]
            self.diagnostics_updated.set()  # Signal that diagnostics are updated

        def empty_callback(params):
            pass
        json_rpc_endpoint = JsonRpcEndpoint(
            self.leanProcess.stdin, self.leanProcess.stdout
        )
        lsp_endpoint = LspEndpoint(
            json_rpc_endpoint,
            notify_callbacks={
                "textDocument/publishDiagnostics": onDiagnostics,
                "$/lean/fileProgress": empty_callback,
            },
        )
        lsp_client = LspClient(lsp_endpoint)
        logging.info("Lean client initializing...")
        initialize_response = lsp_client.initialize(
            processId = None,
            rootPath = None,
            rootUri = self.rootUri,
            initializationOptions = None,
            capabilities = {},
            trace = "off",
            workspaceFolders = None,
        )
        if initialize_response["serverInfo"]["name"] != "Lean 4 Server":
            raise RuntimeError("Initializing lean client failed.")
        lsp_client.initialized()
        logging.info("Lean client initialized.")
        logging.info("Lean server info", initialize_response["serverInfo"])
        return lsp_client
    
    def __init_text_document__(file_path: Path, text: list[str]) -> TextDocumentItem:
        file_uri = toUri(file_path)
        version = 1
        textDocument = TextDocumentItem(
            uri=file_uri, languageId=LanguageIdentifier.LEAN, version=version, text='\n'.join(text)
        )
        return textDocument

    def __initRpcSessionId__(lspClient: LspClient, fileUri: str) -> str:
        logging.info("initRpcSessionId start")
        response = lspClient.lsp_endpoint.call_method("$/lean/rpc/connect", uri=fileUri)
        logging.info("initRpcSessionId response:", response)
        return response["sessionId"]
    
    def __processGoal__(goal) -> str:
        result = []
        goal_prefix = goal.get("goalPrefix", "")
        goal_type = goal.get("type", {})
        goal_type_str = LeanServer.__processTaggedText__(goal_type)

        # 提取并处理假设
        hyps = goal.get("hyps", [])
        hyps_str = []
        for hyp in hyps:
            hyp_names = ", ".join(hyp.get("names", []))
            hyp_type = LeanServer.__processTaggedText__(hyp.get("type", {}))
            hyps_str.append(f"{hyp_names} : {hyp_type}")
        if hyps_str:
            result.append(f"{', '.join(hyps_str)}")
        # 汇总信息
        result.append(f"{goal_prefix}{goal_type_str}")
        return " ".join(result)

    def __processTaggedText__(tagged):
        """递归处理TaggedText结构，将其转化为可阅读的字符串"""
        if isinstance(tagged, dict):
            if "text" in tagged:
                return tagged["text"]
            elif "tag" in tagged:
                # 处理有标签的情况
                return LeanServer.__processTaggedText__(tagged["tag"][1])  # 对第一个tag子元素递归处理
            elif "append" in tagged:
                # 处理append数组，递归处理每个元素
                return "".join(LeanServer.__processTaggedText__(sub_tag) for sub_tag in tagged["append"])
        return ""

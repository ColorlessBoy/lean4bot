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
    filename="LeanServer.log",  # 日志输出到文件
    level=logging.DEBUG,  # 记录所有级别的日志
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def toUri(path: Path) -> str:
    """Convert a path to a URI."""
    return str(path.absolute().as_uri())


# 假设这是需要清理的资源
class LeanServer:
    def __init__(
        self,
        name,
        projectPath: Optional[str] = None,
        fileName: Optional[str] = None,
        text: list[str] = [],
        timeout = 20,
    ):
        if projectPath is None:
            projectPath = Path(__file__).parent / "miniF2F-lean4"
        if fileName is None:
            fileName = f"{name}.lean"
        self.name = name
        self.timeout = timeout
        self.rootPath = projectPath
        self.rootUri = toUri(projectPath)
        self.leanProcess = LeanServer.__initLeanProcess__(projectPath)
        self.diagnostics = {}
        self.diagnosticsUpdated = Event()  # Add event flag
        self.progressCompleted = Event()  # Add event flag
        self.lspClient = self.__initLspClient__()
        filePath = projectPath / fileName
        self.textDocument: TextDocumentItem = LeanServer.__init_text_document__(
            filePath, text
        )
        self.lspClient.didOpen(self.textDocument)
        self.text = text
        self.headLines = len(text)
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

    def getCodeInfo(self, code: str):
        logging.info("Received request to check_proof")
        self.diagnostics[self.textDocument.uri] = []
        self.progressCompleted.clear()
        self.diagnosticsUpdated.clear()
        self.didChange(code.split("\n"))
        diagnostics = self.getDiagnostics()
        if len(diagnostics) > 0:
            goals = []
        else:
            goals = self.getInteractiveGoals()
        logging.debug(f"code: {repr(code)}")
        logging.debug(f"goals: {goals}")
        logging.debug(f"diagnostics: {diagnostics}")
        return {"goals": goals, "diagnostics": diagnostics}

    def didChange(self, text: list[str]) -> any:
        logging.info("didChange() start.")
        logging.debug("\n".join(text))
        range = {
            "start": {"line": 0, "character": 0},
            "end": {"line": len(self.text), "character": 0},
        }
        params = [{"range": range, "text": "\n".join(text)}]
        self.lspClient.didChange(self.textDocument, params)
        self.text = text
        logging.info("didChange() successed.")

    def getInteractiveGoals(self) -> list[dict]:
        logging.info("getInteractiveGoals() start.")
        result = {}
        sessionId: str = LeanServer.__initRpcSessionId__(
            self.lspClient, self.textDocument.uri
        )
        last_goals_str = ""
        logging.debug(f"sessionId: {sessionId}")
        try: 
            for line in range(1, len(self.text)):
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
                response = self.lspClient.lsp_endpoint.call_method(
                    "$/lean/rpc/call", **params
                )
                if response and "goals" in response and len(response["goals"]) > 0:
                    goals = [LeanServer.__processGoal__(goal) for goal in response["goals"]]
                    goals_str = str(goals)
                    if line > 0 and goals_str != last_goals_str:
                        result[str(line)] = goals
                        last_goals_str = goals_str
            logging.info("getInteractiveGoals() successed.")
        except Exception as e:
            logging.error("getInteractiveGoals() failed: " + str(e))
        return result

    def getDiagnostics(self):
        logging.info("getDiagnostics() start.")
        uri = self.textDocument.uri
        
        # 等待进度完成
        if not self.progressCompleted.wait(self.timeout):
            logging.warning(f"Timeout waiting for progress after {self.timeout} seconds")
        
        # 等待诊断更新
        if not self.diagnosticsUpdated.wait(self.timeout):
            logging.warning(f"Timeout waiting for diagnostics after {self.timeout} seconds")
            return []
        
        # 检查URI是否存在于diagnostics中
        if uri not in self.diagnostics:
            logging.warning(f"No diagnostics found for URI: {uri}")
            return []
        
        return self.diagnostics.get(uri, [])

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
            logging.debug(f"onDiagnostics called with params: {params}")
            uri = params.get("uri")
            if not uri:
                logging.warning("No uri in diagnostics params")
                return
                
            diagnostics = [d for d in params.get("diagnostics", []) if int(d.get("severity", 1)) <= 1 and 'no goals to be solved' not in d.get("message", "") or int(d.get("severity", 1)) == 2 and "sorry" in d.get("message", "")]
            logging.debug(f"Received diagnostics: {diagnostics}")
            
            # 更新diagnostics
            self.diagnostics[uri] = diagnostics
            
            # 只有在收到有效诊断信息时才设置标志
            if len(diagnostics) > 0:
                logging.info(f"Setting diagnostics flags for {len(diagnostics)} items")
                self.diagnosticsUpdated.set()
                self.progressCompleted.set()
            logging.debug(f"Current diagnostics state: {self.diagnostics}")


        def onFileProgress(params):
            if self.progressCompleted.is_set():
                return
            logging.debug("onFileProgress()" + str(params))
            if len(params["processing"]) == 0:
                self.progressCompleted.set()
        
        def emptyCallback(params):
            pass

        json_rpc_endpoint = JsonRpcEndpoint(
            self.leanProcess.stdin, self.leanProcess.stdout
        )
        lsp_endpoint = LspEndpoint(
            json_rpc_endpoint,
            notify_callbacks={
                "textDocument/publishDiagnostics": onDiagnostics,
                "$/lean/fileProgress": onFileProgress,
                "workspace/semanticTokens/refresh": emptyCallback,
            },
            timeout=self.timeout,
        )
        lsp_client = LspClient(lsp_endpoint)
        logging.info("Lean client initializing...")
        initialize_response = lsp_client.initialize(
            processId=None,
            rootPath=None,
            rootUri=self.rootUri,
            initializationOptions=None,
            capabilities={},
            trace="off",
            workspaceFolders=None,
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
            uri=file_uri,
            languageId=LanguageIdentifier.LEAN,
            version=version,
            text="\n".join(text),
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
                return LeanServer.__processTaggedText__(
                    tagged["tag"][1]
                )  # 对第一个tag子元素递归处理
            elif "append" in tagged:
                # 处理append数组，递归处理每个元素
                return "".join(
                    LeanServer.__processTaggedText__(sub_tag)
                    for sub_tag in tagged["append"]
                )
        return ""

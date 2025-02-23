import subprocess
import pathlib
import sys
from pylspclient import LspClient, JsonRpcEndpoint, LspEndpoint
from pylspclient.lsp_pydantic_strcuts import (
    TextDocumentItem,
    TextDocumentIdentifier,
    LanguageIdentifier,
    Position,
)
import random
import json

class ServerProcessManager:
    def __init__(self):
        self.process = None

    def __enter__(self):
        try:
            print("Lean server launching...")
            # Start Lean server subprocess with redirected I/O
            # Using 'lake serve' command with LeanProject directory as working directory
            self.process = subprocess.Popen(
                ["lake", "serve", "--"],
                cwd=str(pathlib.Path(__file__).parent / "LeanProject"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Validate pipe creation to prevent silent failures
            if self.process.stdin is None or self.process.stdout is None:
                raise RuntimeError(
                    "Failed to get stdin or stdout from the Lean server process."
                )
            print("Lean server Launched.")
            return self.process
        except Exception as e:
            # Handle any startup failures and ensure clean exit
            print(f"Launching lean server failed: {e}", file=sys.stderr)
            raise  # Re-raise exception to abort context manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            self.process.terminate()
            self.process.wait()


class LspClientManager:
    def __init__(self, root_uri: str, server_process: subprocess.Popen):
        self.root_uri = root_uri
        self.server_process = server_process
        self.lsp_client = None
        self.diagnostics = {}
    
    def get_diagnostics(self, uri: str) -> list:
        return self.diagnostics.get(uri, [])

    def __enter__(self):
        def on_diagnostics(params):
            uri = params["uri"]
            self.diagnostics[uri] = params["diagnostics"]

        def empty_callback(params):
            pass

        json_rpc_endpoint = JsonRpcEndpoint(
            self.server_process.stdin, self.server_process.stdout
        )
        lsp_endpoint = LspEndpoint(
            json_rpc_endpoint,
            notify_callbacks={
                "textDocument/publishDiagnostics": on_diagnostics,
                "$/lean/fileProgress": empty_callback,
            },
        )
        self.lsp_client = LspClient(lsp_endpoint)
        process_id = None
        root_path = None
        initialization_options = None
        capabilities = {}
        trace = "off"
        workspace_folders = None
        print("Lean client initializing...")
        initialize_response = self.lsp_client.initialize(
            process_id,
            root_path,
            self.root_uri,
            initialization_options,
            capabilities,
            trace,
            workspace_folders,
        )
        if initialize_response["serverInfo"]["name"] != "Lean 4 Server":
            raise RuntimeError("Initializing lean client failed.")
        print("Lean client initialized.")
        print("Lean server info", initialize_response["serverInfo"])
        self.lsp_client.initialized()
        return self.lsp_client, self.get_diagnostics

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lsp_client:
            self.lsp_client.shutdown()
            self.lsp_client.exit()


def getTextDocument(file_path: pathlib.Path, text: str) -> TextDocumentItem:
    file_uri = to_uri(file_path)
    version = 1
    textDocument = TextDocumentItem(
        uri=file_uri, languageId=LanguageIdentifier.LEAN, version=version, text=text
    )
    return textDocument


def getRpcSession(lspClient: LspClient, fileUri: str) -> str:
    print("getRpcSession start")
    response = lspClient.lsp_endpoint.call_method("$/lean/rpc/connect", uri=fileUri)
    print("getRpcSession response:", response)
    return response["sessionId"]


# 递归处理TaggedText结构
def process_tagged_text(tagged):
    """递归处理TaggedText结构，将其转化为可阅读的字符串"""
    if isinstance(tagged, dict):
        if "text" in tagged:
            return tagged["text"]
        elif "tag" in tagged:
            # 处理有标签的情况
            return process_tagged_text(tagged["tag"][1])  # 对第一个tag子元素递归处理
        elif "append" in tagged:
            # 处理append数组，递归处理每个元素
            return "".join(process_tagged_text(sub_tag) for sub_tag in tagged["append"])
    return ""


def process_goal(goal) -> str:
    result = []
    goal_prefix = goal.get("goalPrefix", "")
    goal_type = goal.get("type", {})
    goal_type_str = process_tagged_text(goal_type)

    # 提取并处理假设
    hyps = goal.get("hyps", [])
    hyps_str = []
    for hyp in hyps:
        hyp_names = ", ".join(hyp.get("names", []))
        hyp_type = process_tagged_text(hyp.get("type", {}))
        hyps_str.append(f"{hyp_names} : {hyp_type}")
    if hyps_str:
        result.append(f"{', '.join(hyps_str)}")
    # 汇总信息
    result.append(f"{goal_prefix} {goal_type_str}")
    return " ".join(result)


def process_goals(goals) -> str:
    """处理目标数据，将其转化为可阅读的字符串"""
    result = []
    for goal in goals:
        result.append(process_goal(goal))
    return "\n".join(result)


def getInteractiveGoals(
    lspClient: LspClient,
    textDocument: TextDocumentIdentifier,
    position: Position,
    sessionId: str,
) -> list[dict]:
    """
    Send a request to get interactive goals from Lean server.

    Args:
        textDocument (TextDocumentIdentifier): The text document
        position (Position): The position in the document
        sessionId (str): The session ID for the request

    Returns:
        dict: The response from the Lean server
    """
    params = {
        "method": "Lean.Widget.getInteractiveGoals",
        "params": {
            "textDocument": textDocument.model_dump(),
            "position": position.model_dump(),
        },
        "sessionId": sessionId,
        "position": position.model_dump(),
        "textDocument": textDocument.model_dump(),
    }
    response = lspClient.lsp_endpoint.call_method("$/lean/rpc/call", **params)
    goals = process_goals(response["goals"])
    return goals


def generate_session_id() -> str:
    """Generate a new session ID to avoid outdated session errors."""
    return str(
        random.randint(1000000000000000000, 9999999999999999999)
    )  # More secure random ID


def to_uri(path: pathlib.Path) -> str:
    """Convert a path to a URI."""
    return str(path.absolute().as_uri())


def get_text_changes(oldText: list[str], newText: list[str]) -> object:
    range = {
        "start": {"line": 0, "character": 0},
        "end": {"line": len(oldText), "character": 0},
    }
    return [{"range": range, "text": "\n".join(newText)}]

def post_process_diagnostics(diagnostics, serverity = 1):
    """
    Post-process the diagnostics to remove unnecessary information.
    """
    processed_diagnostics = [diag for diag in diagnostics if diag["severity"] <= serverity]
    return processed_diagnostics

def main():
    root_path = pathlib.Path(__file__).parent / "LeanProject"
    root_uri = to_uri(root_path)
    with ServerProcessManager() as server_process:
        with LspClientManager(root_uri, server_process) as (lsp_client, get_diagnostics):
            # 使用 LSP 客户端进行其他操作
            file_path = root_path / "test.lean"
            textDocument = getTextDocument(file_path, "")
            lsp_client.didOpen(textDocument)
            session_id = getRpcSession(lsp_client, textDocument.uri)
            old_text = []

            while True:  # 添加循环接收输入
                # 读取stdin输入
                try:
                    input_data = sys.stdin.read()
                    if not input_data or input_data.endswith('\x04'):  # 检查EOF
                        if input_data:  # 如果有数据，去掉EOF字符
                            input_data = input_data[:-1]
                        if not input_data:  # 如果没有数据了，退出循环
                            break
                    new_text = input_data.split("\n")
                except KeyboardInterrupt:
                    break
                lsp_client.didChange(textDocument, get_text_changes(old_text, new_text))
                old_text = new_text 
                for line in range(len(new_text)):
                    # 使用生成的会话 ID
                    goals = getInteractiveGoals(
                        lsp_client,
                        TextDocumentIdentifier(uri=textDocument.uri),
                        Position(line=line + 1, character=0),
                        session_id,
                    )
                diagnostics = post_process_diagnostics(get_diagnostics(textDocument.uri))
                # 输出JSON格式结果
                print(json.dumps({
                    "goals": goals,
                    "diagnostics": diagnostics
                }, ensure_ascii=False))
                sys.stdout.flush()

if __name__ == "__main__":
    main()

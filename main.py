import subprocess
import pathlib
import sys
from pylspclient import LspClient, JsonRpcEndpoint, LspEndpoint
from pylspclient.lsp_pydantic_strcuts import TextDocumentItem, LanguageIdentifier, TextDocumentIdentifier, Position
import random

class ServerProcessManager:
    def __init__(self):
        self.process = None

    def __enter__(self):
        try:
            print("Lean server launching...")
            self.process = subprocess.Popen(
                ["lake", "serve", "--"],
                cwd=str(pathlib.Path(__file__).parent / 'LeanProject'),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if self.process.stdin is None or self.process.stdout is None:
                raise RuntimeError("Failed to get stdin or stdout from the Lean server process.")
            print("Lean server Launched.")
            return self.process
        except Exception as e:
            print(f"Launching lean server failed: {e}", file=sys.stderr)
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            self.process.terminate()
            self.process.wait()

class LspClientManager:
    def __init__(self, root_uri: str, server_process: subprocess.Popen):
        self.root_uri = root_uri
        self.server_process = server_process
        self.lsp_client = None

    def __enter__(self):
        json_rpc_endpoint = JsonRpcEndpoint(self.server_process.stdin, self.server_process.stdout)
        lsp_endpoint = LspEndpoint(json_rpc_endpoint)
        self.lsp_client = LspClient(lsp_endpoint)
        process_id = None
        root_path = None
        initialization_options = None
        capabilities = {}
        trace = "off"
        workspace_folders = None
        print("Lean client initializing...")
        initialize_response = self.lsp_client.initialize(process_id, root_path, self.root_uri, initialization_options, capabilities, trace, workspace_folders)
        if initialize_response['serverInfo']['name'] != 'Lean 4 Server':
            raise RuntimeError("Initializing lean client failed.")
        print("Lean client initialized.")
        print("Lean server info", initialize_response['serverInfo'])
        self.lsp_client.initialized()
        return self.lsp_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lsp_client:
            self.lsp_client.shutdown()
            self.lsp_client.exit()

def getTextDocument(file_path : pathlib.Path, text: str) -> TextDocumentItem:
    file_uri = to_uri(file_path)
    version = 1
    textDocument = TextDocumentItem(uri=file_uri, languageId=LanguageIdentifier.LEAN, version=version, text=text)
    return textDocument

def getRpcSession(lspClient: LspClient, fileUri: str) -> str:
    print("getRpcSession start")
    response = lspClient.lsp_endpoint.call_method("$/lean/rpc/connect", uri=fileUri)
    print("getRpcSession response:", response)
    return response['sessionId']
# 递归处理TaggedText结构
def process_tagged_text(tagged):
    """递归处理TaggedText结构，将其转化为可阅读的字符串"""
    if isinstance(tagged, dict):
        if 'text' in tagged:
            return tagged['text']
        elif 'tag' in tagged:
            # 处理有标签的情况
            return process_tagged_text(tagged['tag'][1])  # 对第一个tag子元素递归处理
        elif 'append' in tagged:
            # 处理append数组，递归处理每个元素
            return ''.join(process_tagged_text(sub_tag) for sub_tag in tagged['append'])
    return ""

def process_goal(goal) -> str:
    result = []
    goal_prefix = goal.get('goalPrefix', '')
    goal_type = goal.get('type', {})
    goal_type_str = process_tagged_text(goal_type)
    
    # 提取并处理假设
    hyps = goal.get('hyps', [])
    hyps_str = []
    for hyp in hyps:
        hyp_names = ', '.join(hyp.get('names', []))
        hyp_type = process_tagged_text(hyp.get('type', {}))
        hyps_str.append(f"{hyp_names} : {hyp_type}")
    if hyps_str:
        result.append(f"{', '.join(hyps_str)}")
    # 汇总信息
    result.append(f"{goal_prefix} {goal_type_str}")
    return ' '.join(result)

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
    sessionId: str
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
            "position": position.model_dump()
        },
        "sessionId": sessionId,
        "position": position.model_dump(),
        "textDocument": textDocument.model_dump()
    }
    response = lspClient.lsp_endpoint.call_method("$/lean/rpc/call", **params)
    goals = process_goals(response['goals'])
    return goals

def generate_session_id() -> str:
    """Generate a new session ID to avoid outdated session errors."""
    return str(random.randint(1000000000000000000, 9999999999999999999))  # More secure random ID

def to_uri(path: pathlib.Path) -> str:
    """Convert a path to a URI."""
    return str(path.absolute().as_uri())

def main():
    root_path = pathlib.Path(__file__).parent / 'LeanProject'
    root_uri = to_uri(root_path)
    with ServerProcessManager() as server_process:
        with LspClientManager(root_uri, server_process) as lsp_client:
            # 使用 LSP 客户端进行其他操作
            file_path = root_path / 'test.lean'
            with open(file_path, "r") as f:
                text = f.readlines()
            print("text", text)
            textDocument = getTextDocument(file_path, ''.join(text))
            lsp_client.didOpen(textDocument)
            session_id = getRpcSession(lsp_client, textDocument.uri)
            for line in range(len(text)):
                # 使用生成的会话 ID
                goals = getInteractiveGoals(
                    lsp_client,
                    TextDocumentIdentifier(uri=textDocument.uri),
                    Position(line=line+1, character=0),
                    session_id
                )
                print("line", line, ":", goals)


if __name__ == "__main__":
    main()

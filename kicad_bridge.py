import argparse
import json
import subprocess
import sys


KICAD_MCP_EXE = r"C:\Program Files\KiCad\10.0\bin\kicad-mcp\.venv\Scripts\kicad-mcp.exe"


def read_line(stream):
    line = stream.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return line
    return line


def run_mcp_tool(tool_name, arguments, socket_url):
    proc = subprocess.Popen(
        [
            KICAD_MCP_EXE,
            "--socket-url",
            socket_url,
            "--editor-type",
            "schematic",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "codex", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    ]

    for req in requests:
        proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    proc.stdin.close()

    output = proc.stdout.read()
    proc.wait(timeout=30)

    result = None
    for line in output.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("id") == 2:
            result = obj
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket-url", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--args", default="{}")
    args = parser.parse_args()

    arguments = json.loads(args.args)
    response = run_mcp_tool(args.tool, arguments, args.socket_url)
    json.dump(response, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

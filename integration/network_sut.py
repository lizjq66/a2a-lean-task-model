"""Loopback-only JSON-RPC SUT using the pinned SDK and upstream TCK executor."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import subprocess

from starlette.applications import Starlette
import uvicorn

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types.a2a_pb2 import AgentCard, AgentCapabilities, AgentInterface, AgentSkill
from provenance import require_revision

SDK_COMMIT = "01da00b0951ba6201af860d17b4c088be7902d43"
TCK_COMMIT = "263b9cfaf16a554bdfb166a7ba5b67716e946349"


class TrafficRecorder:
    """Record completed HTTP exchanges in this synthetic local experiment only."""

    def __init__(self, app, path):
        self.app, self.path = app, path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_chunks, response_chunks = [], []
        status = None

        async def read():
            message = await receive()
            if message["type"] == "http.request":
                request_chunks.append(message.get("body", b""))
            return message

        async def write(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            if message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, read, write)
        finally:
            record = {"method": scope["method"], "path": scope["path"], "status": status,
                      "request_body": b"".join(request_chunks).decode("utf-8", errors="replace"),
                      "response_body": b"".join(response_chunks).decode("utf-8", errors="replace")}
            with self.path.open("a") as output:
                output.write(json.dumps(record) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tck_checkout", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--traffic", type=Path, required=True)
    args = parser.parse_args()
    require_revision("a2a-sdk", SDK_COMMIT)
    checkout = args.tck_checkout.resolve()
    sha = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if sha != TCK_COMMIT:
        raise SystemExit("Wrong TCK source revision")
    source = checkout / "sut/a2a-python/sut_agent.py"
    committed = subprocess.check_output(["git", "-C", str(checkout), "show", "HEAD:sut/a2a-python/sut_agent.py"])
    if source.read_bytes() != committed:
        raise SystemExit("Generated executor differs from the pinned source")
    spec = importlib.util.spec_from_file_location("upstream_tck_sut", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    card = AgentCard(
        name="Lean TCK network probe", description="Pinned upstream executor, JSON-RPC only",
        version="1", capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"], default_output_modes=["text/plain"],
        supported_interfaces=[AgentInterface(url=f"http://127.0.0.1:{args.port}",
                                             protocol_binding="JSONRPC", protocol_version="1.0")],
        skills=[AgentSkill(id="tck", name="TCK", description="Controlled TCK scenarios", tags=["test"])],
    )
    handler = DefaultRequestHandler(agent_executor=module.TckAgentExecutor(),
                                    task_store=InMemoryTaskStore(), agent_card=card)

    @asynccontextmanager
    async def lifespan(app):
        yield
        await handler.aclose()

    app = Starlette(routes=[*create_agent_card_routes(agent_card=card),
                            *create_jsonrpc_routes(request_handler=handler, rpc_url="/")],
                    lifespan=lifespan)
    args.traffic.parent.mkdir(parents=True, exist_ok=True)
    args.traffic.write_text("")
    uvicorn.run(TrafficRecorder(app, args.traffic), host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()

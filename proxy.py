#!/usr/bin/env python3
"""Local stdio proxy — bridges Claude Desktop to the remote Railway MCP server."""
import asyncio
import mcp.types as mcp_types
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession
from mcp.server import Server
from mcp.server.stdio import stdio_server

REMOTE_URL = "https://14napiint-production.up.railway.app/mcp"
HEADERS = {"Authorization": "Bearer 123456789"}


async def main() -> None:
    async with streamablehttp_client(REMOTE_URL, headers=HEADERS, timeout=180) as (read, write, _):
        async with ClientSession(read, write) as remote:
            await remote.initialize()

            server = Server("14n-acled-proxy")

            @server.list_tools()
            async def list_tools() -> list[mcp_types.Tool]:
                result = await remote.list_tools()
                return result.tools

            @server.call_tool()
            async def call_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
                result = await remote.call_tool(name, arguments)
                return result.content

            async with stdio_server() as (stdin, stdout):
                await server.run(
                    stdin, stdout, server.create_initialization_options()
                )


asyncio.run(main())

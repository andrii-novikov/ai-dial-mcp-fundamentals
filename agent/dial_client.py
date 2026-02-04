import json
import logging
from collections import defaultdict
from typing import Any

from mcp_client import MCPClient
from models.message import Message, Role
from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class DialClient:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        mcp_clients: list[MCPClient],
    ):
        self.mcp_clients = mcp_clients
        self.openai = AsyncAzureOpenAI(
            api_key=api_key, azure_endpoint=endpoint, api_version="2025-01-01-preview"
        )
        self.tools = []
        self.mcp_clients_tools = {}

        logger.info("DialClient initialized")

    async def __aenter__(self):
        await self._load_tools()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def _load_tools(self):
        for mcp_client in self.mcp_clients:
            try:
                tools = await mcp_client.get_tools()
                self.tools.extend(tools)

                for tool in tools:
                    self.mcp_clients_tools[tool["function"]["name"]] = mcp_client

                logger.info(
                    "Tools loaded from MCP client %s", mcp_client.mcp_server_url
                )
            except Exception as e:
                logger.error(
                    f"Error loading tools from MCP client {mcp_client.mcp_server_url}: {e}"
                )
        logger.info("Tools loaded")
        logger.debug("Tools: %s", json.dumps(self.tools, indent=2))

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        tool_dict = defaultdict(
            lambda: {
                "id": None,
                "function": {"arguments": "", "name": None},
                "type": None,
            }
        )

        for delta in tool_deltas:
            idx = delta.index
            if delta.id:
                tool_dict[idx]["id"] = delta.id
            if delta.function.name:
                tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function.arguments:
                tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type:
                tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _stream_response(self, messages: list[Message]) -> Message:
        """Stream OpenAI response and handle tool calls"""
        stream = await self.openai.chat.completions.create(
            **{
                "model": "gpt-4o",
                "messages": [msg.to_dict() for msg in messages],
                "tools": self.tools,
                "temperature": 0.0,
                "stream": True,
            }
        )

        content = ""
        tool_deltas = []

        print("🤖: ", end="", flush=True)

        async for chunk in stream:
            delta = chunk.choices[0].delta

            # Stream content
            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content

            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

        print()
        return Message(
            role=Role.AI,
            content=content,
            tool_calls=self._collect_tool_calls(tool_deltas) if tool_deltas else [],
        )

    async def get_completion(self, messages: list[Message]) -> Message:
        """Process user query with streaming and tool calling"""
        ai_message: Message = await self._stream_response(messages)

        # Check if any tool calls are present and perform them
        if ai_message.tool_calls:
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            # recursively calling agent with tool messages
            return await self.get_completion(messages)

        return ai_message

    async def _call_tools(self, ai_message: Message, messages: list[Message]):
        """Execute tool calls using MCP client"""
        if not ai_message.tool_calls:
            return

        for tool_call in ai_message.tool_calls:
            tool_call_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])

            try:
                mcp_client = self.mcp_clients_tools[tool_name]
                tool_response = await mcp_client.call_tool(tool_name, tool_args)
                messages.append(
                    Message(
                        role=Role.TOOL,
                        content=tool_response,
                        tool_call_id=tool_call_id,
                    )
                )
            except Exception as e:
                messages.append(
                    Message(role=Role.TOOL, content=str(e), tool_call_id=tool_call_id)
                )

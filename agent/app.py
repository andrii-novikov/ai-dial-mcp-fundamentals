import asyncio
import logging
import os

from dial_client import DialClient
from mcp import Resource
from mcp.types import Prompt
from mcp_client import MCPClient
from models.message import Message, Role
from prompts import SYSTEM_PROMPT

DIAL_ENDPOINT = "https://ai-proxy.lab.epam.com"
API_KEY = os.getenv("DIAL_API_KEY")

logger = logging.getLogger(__name__)

# https://remote.mcpservers.org/fetch/mcp
# Pay attention that `fetch` doesn't have resources and prompts


async def main():
    if not API_KEY:
        print("API_KEY is not set")
        return

    mcp_server_url = "http://localhost:8005/mcp"
    fetch_mcp_url = "https://remote.mcpservers.org/fetch/mcp"

    async with MCPClient(mcp_server_url=fetch_mcp_url) as mcp_client:
        resources: list[Resource] = await mcp_client.get_resources()
        print("\nAvailable MCP Resources:")
        for resource in resources:
            print(f"  - {resource.name}")
            resource_data = await mcp_client.get_resource(resource.uri)
            # print(f"    - Content: {resource_data}")

        tools = await mcp_client.get_tools()
        print("\nAvailable MCP Tools:")
        for tool in tools:
            function = tool["function"]
            print(f"  - {function['name']}: {function['description']}")

        dial_client = DialClient(
            api_key=API_KEY, endpoint=DIAL_ENDPOINT, mcp_client=mcp_client, tools=tools
        )
        messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]

        print("\nAvailable MCP Prompts:")
        prompts: list[Prompt] = await mcp_client.get_prompts()
        for prompt in prompts:
            content = await mcp_client.get_prompt(prompt.name)
            print(f"  - {prompt.name}")
            messages.append(Message(role=Role.USER, content=content))

        while True:
            user_input = input("> ")
            if user_input in ["exit", "quit", "q"]:
                break
            messages.append(Message(role=Role.USER, content=user_input))
            ai_response = await dial_client.get_completion(messages)
            messages.append(ai_response)


if __name__ == "__main__":
    asyncio.run(main())

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

logger = logging.basicConfig(level=logging.WARNING)

# https://remote.mcpservers.org/fetch/mcp
# Pay attention that `fetch` doesn't have resources and prompts


async def main():
    if not API_KEY:
        print("API_KEY is not set")
        return

    user_mcp_url = "http://localhost:8005/mcp"
    fetch_mcp_url = "https://remote.mcpservers.org/fetch/mcp"

    async with (
        MCPClient(mcp_server_url=fetch_mcp_url) as fetch_mcp_client,
        MCPClient(mcp_server_url=user_mcp_url) as user_mcp_client,
        DialClient(
            api_key=API_KEY,
            endpoint=DIAL_ENDPOINT,
            mcp_clients=[fetch_mcp_client, user_mcp_client],
        ) as dial_client,
    ):
        messages = [Message(role=Role.SYSTEM, content=SYSTEM_PROMPT)]

        while True:
            user_input = input("> ")
            if user_input in ["exit", "quit", "q"]:
                break
            messages.append(Message(role=Role.USER, content=user_input))
            ai_response = await dial_client.get_completion(messages)
            messages.append(ai_response)


if __name__ == "__main__":
    asyncio.run(main())

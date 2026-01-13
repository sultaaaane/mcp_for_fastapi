import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    server = StdioServerParameters(
        command="python3",
        args=["server.py"],
    )

    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            result = await session.call_tool("testing", {"test": "waaaaaaaaaa"})

            print(result)


asyncio.run(main())

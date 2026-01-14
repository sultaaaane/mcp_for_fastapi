import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    server = StdioServerParameters(
        command="python3",
        args=["server.py"],
    )

    try:
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.call_tool(
                    "discover_endpoints", {"base_url": "http://localhost:8000"}
                )
                print("Discovered endpoints:", result)

                result = await session.call_tool(
                    "test_all_endpoints", {"base_url": "http://localhost:8000"}
                )
                print("Test results:", result)

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

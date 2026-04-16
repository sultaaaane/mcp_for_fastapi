import asyncio
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


async def main():
    base_url = "http://127.0.0.1:8001"
    server = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
    )

    try:
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                result = await session.call_tool(
                    "discover_endpoints", {"base_url": base_url}
                )
                print("Discovered endpoints:", result)

                result = await session.call_tool(
                    "get_endpoint_schema",
                    {"base_url": base_url, "path": "/tasks", "method": "POST"},
                )
                print("POST /tasks schema:", result)

                result = await session.call_tool(
                    "test_endpoint",
                    {
                        "base_url": base_url,
                        "path": "/tasks",
                        "method": "POST",
                        "body": {"id": 10, "title": "AI", "task": "Created via MCP"},
                    },
                )
                print("POST /tasks test:", result)

                result = await session.call_tool(
                    "test_all_endpoints", {"base_url": base_url}
                )
                print("Test results:", result)

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

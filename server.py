from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FastAPI_Endpoints")


@mcp.tool()
def testing(test: str) -> str:
    return f"i've been telling you {test}"


mcp.run()

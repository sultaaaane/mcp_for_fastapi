import asyncio
import httpx
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
import sys

app = Server("FastAPI_Endpoints")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="discover_endpoints",
            description="Discover all endpoints from a FastAPI application",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "The base URL of your FastAPI app (e.g., http://localhost:8000)",
                    }
                },
                "required": ["base_url"],
            },
        ),
        Tool(
            name="test_endpoint",
            description="Test a specific endpoint from your FastAPI app",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the endpoint to test",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "HTTP method to use",
                    },
                    "body": {
                        "type": "object",
                        "description": "Request body for POST/PUT/PATCH requests",
                    },
                    "headers": {
                        "type": "object",
                        "description": "Custom headers to send with the request",
                    },
                },
                "required": ["url", "method"],
            },
        ),
        Tool(
            name="test_all_endpoints",
            description="Test all GET endpoints from a FastAPI application",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "The base URL of your FastAPI app",
                    }
                },
                "required": ["base_url"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, args: dict) -> list[TextContent]:
    if name == "discover_endpoints":
        base_url = args["base_url"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{base_url}/openapi.json")
                openapi_spec = response.json()

                endpoints = []
                for path, methods in openapi_spec.get("paths", {}).items():
                    for method, details in methods.items():
                        endpoints.append(
                            {
                                "path": path,
                                "method": method.upper(),
                                "summary": details.get("summary", ""),
                                "description": details.get("description", ""),
                            }
                        )
                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(endpoints)} endpoints: \n {endpoints}",
                    )
                ]
            except Exception as e:
                return [
                    TextContent(
                        type="text", text=f"Error discovering endpoints: {str(e)}"
                    )
                ]
    elif name == "test_endpoint":
        url = args["url"]
        method = args["method"]
        body = args.get("body")
        headers = args.get("headers", {})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method, url=url, json=body if body else None, headers=headers
                )
                results = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                    "success": response.is_success,
                }
                return [TextContent(type="text", text=f"Test Result: \n {results}")]
            except Exception as e:
                return [
                    TextContent(type="text", text=f"Error testing endpoint: {str(e)}")
                ]
    elif name == "test_all_endpoints":
        base_url = args["base_url"]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{base_url}/openapi.json")
                openapi_spec = response.json()

                results = []
                for path, methods in openapi_spec.get("paths", {}).items():
                    for method, details in methods.items():
                        full_url = f"{base_url}{path}"
                        method_upper = method.upper()
                        try:
                            request_body = None
                            if method_upper in ["POST", "PUT", "PATCH"]:
                                request_body_schema = (
                                    details.get("requestBody", {})
                                    .get("content", {})
                                    .get("application/json", {})
                                    .get("schema", {})
                                )
                                request_body = {}
                            test_response = await client.request(
                                method=method_upper,
                                url=full_url,
                                json=request_body if request_body is not None else None,
                            )
                            results.append(
                                {
                                    "endpoint": f"{method_upper} {path}",
                                    "status": test_response.status_code,
                                    "success": test_response.is_success,
                                    "body": (
                                        test_response.text[:200]
                                        if test_response.text
                                        else None
                                    ),
                                }
                            )
                        except Exception as endpoint_error:
                            results.append(
                                {
                                    "endpoint": f"{method_upper} {path}",
                                    "status": "error",
                                    "success": False,
                                    "error": str(endpoint_error),
                                }
                            )

                return [
                    TextContent(
                        type="text",
                        text=f"Tested {len(results)} endpoints:\n{results}",
                    )
                ]
            except Exception as e:
                return [
                    TextContent(type="text", text=f"Error testing endpoints: {str(e)}")
                ]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    print("Running main...", file=sys.stderr)
    asyncio.run(main())

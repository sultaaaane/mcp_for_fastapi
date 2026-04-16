import asyncio
from copy import deepcopy
import sys
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

app = Server("FastAPI_Endpoints")


def _resolve_schema(
    schema: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}

    ref = schema.get("$ref")
    if not ref:
        return schema

    prefix = "#/components/schemas/"
    if not ref.startswith(prefix):
        return schema

    schema_name = ref[len(prefix) :]
    resolved = components.get("schemas", {}).get(schema_name, {})
    return resolved if isinstance(resolved, dict) else {}


def _example_for_type(schema_type: str | None) -> Any:
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    return "example"


def _build_example_from_schema(
    schema: dict[str, Any], components: dict[str, Any]
) -> Any:
    resolved = _resolve_schema(schema, components)

    if "example" in resolved:
        return resolved["example"]

    if "anyOf" in resolved and resolved["anyOf"]:
        return _build_example_from_schema(resolved["anyOf"][0], components)

    if "oneOf" in resolved and resolved["oneOf"]:
        return _build_example_from_schema(resolved["oneOf"][0], components)

    schema_type = resolved.get("type")
    if schema_type == "object":
        properties = resolved.get("properties", {})
        required_fields = resolved.get("required", list(properties.keys()))
        result: dict[str, Any] = {}
        for field in required_fields:
            result[field] = _build_example_from_schema(
                properties.get(field, {}), components
            )
        return result

    if schema_type == "array":
        item_schema = resolved.get("items", {})
        return [_build_example_from_schema(item_schema, components)]

    return _example_for_type(schema_type)


def _extract_request_body_schema(
    details: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any]:
    content = details.get("requestBody", {}).get("content", {})
    json_schema = content.get("application/json", {}).get("schema", {})
    return _resolve_schema(json_schema, components)


def _required_parameter_examples(
    details: dict[str, Any], components: dict[str, Any], location: str
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for parameter in details.get("parameters", []):
        if parameter.get("in") != location:
            continue
        if not parameter.get("required", False):
            continue
        parameter_schema = _resolve_schema(parameter.get("schema", {}), components)
        values[parameter.get("name", "")] = _build_example_from_schema(
            parameter_schema, components
        )
    return {key: value for key, value in values.items() if key}


def _replace_path_params(path: str, path_params: dict[str, Any]) -> str:
    rendered = path
    for name, value in path_params.items():
        rendered = rendered.replace(f"{{{name}}}", str(value))
    return rendered


def _extract_endpoint_metadata(
    path: str, method: str, details: dict[str, Any], components: dict[str, Any]
) -> dict[str, Any]:
    request_schema = _extract_request_body_schema(details, components)
    required_body_fields = request_schema.get("required", []) if request_schema else []
    required_query_params = list(
        _required_parameter_examples(details, components, "query").keys()
    )
    required_path_params = list(
        _required_parameter_examples(details, components, "path").keys()
    )

    metadata: dict[str, Any] = {
        "path": path,
        "method": method.upper(),
        "summary": details.get("summary", ""),
        "description": details.get("description", ""),
        "required_query_params": required_query_params,
        "required_path_params": required_path_params,
        "required_body_fields": required_body_fields,
    }

    if request_schema:
        metadata["request_body_schema"] = deepcopy(request_schema)
        metadata["example_body"] = _build_example_from_schema(
            request_schema, components
        )

    return metadata


async def _fetch_openapi_spec(
    client: httpx.AsyncClient, base_url: str
) -> dict[str, Any]:
    response = await client.get(f"{base_url}/openapi.json")
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="discover_endpoints",
            description="Discover all endpoints from a FastAPI application with required args metadata",
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
            name="get_endpoint_schema",
            description="Get detailed schema and required args for a single endpoint",
            inputSchema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "The base URL of your FastAPI app",
                    },
                    "path": {
                        "type": "string",
                        "description": "The endpoint path (e.g., /tasks)",
                    },
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "description": "HTTP method",
                    },
                },
                "required": ["base_url", "path", "method"],
            },
        ),
        Tool(
            name="test_endpoint",
            description="Test a specific endpoint from your FastAPI app with query/path/body arguments",
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
                    "base_url": {
                        "type": "string",
                        "description": "Optional base URL to build endpoint URL",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional endpoint path to combine with base_url",
                    },
                    "query_params": {
                        "type": "object",
                        "description": "Query string parameters",
                    },
                    "path_params": {
                        "type": "object",
                        "description": "Path parameters to replace in path templates",
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
                "required": ["method"],
            },
        ),
        Tool(
            name="test_all_endpoints",
            description="Test all endpoints from a FastAPI application using auto-generated required args",
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
        base_url = args["base_url"].rstrip("/")

        async with httpx.AsyncClient() as client:
            try:
                openapi_spec = await _fetch_openapi_spec(client, base_url)
                components = openapi_spec.get("components", {})

                endpoints = []
                for path, methods in openapi_spec.get("paths", {}).items():
                    for method, details in methods.items():
                        endpoints.append(
                            _extract_endpoint_metadata(
                                path, method, details, components
                            )
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

    if name == "get_endpoint_schema":
        base_url = args["base_url"].rstrip("/")
        path = args["path"]
        method = args["method"].lower()

        async with httpx.AsyncClient() as client:
            try:
                openapi_spec = await _fetch_openapi_spec(client, base_url)
                components = openapi_spec.get("components", {})
                details = openapi_spec.get("paths", {}).get(path, {}).get(method)

                if details is None:
                    return [
                        TextContent(
                            type="text",
                            text=f"Endpoint not found for {method.upper()} {path}",
                        )
                    ]

                endpoint_schema = _extract_endpoint_metadata(
                    path, method, details, components
                )
                return [
                    TextContent(
                        type="text",
                        text=f"Endpoint schema for {method.upper()} {path}:\n{endpoint_schema}",
                    )
                ]
            except Exception as e:
                return [
                    TextContent(
                        type="text", text=f"Error getting endpoint schema: {str(e)}"
                    )
                ]

    if name == "test_endpoint":
        method = args["method"].upper()
        url = args.get("url")
        base_url = args.get("base_url")
        path = args.get("path")
        query_params = args.get("query_params", {})
        path_params = args.get("path_params", {})
        body = args.get("body")
        headers = args.get("headers", {})

        if not url and base_url and path:
            rendered_path = _replace_path_params(path, path_params)
            url = f"{base_url.rstrip('/')}{rendered_path}"

        if not url:
            return [
                TextContent(
                    type="text",
                    text="Error testing endpoint: provide either url or base_url + path",
                )
            ]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=query_params or None,
                    json=body if body is not None else None,
                    headers=headers,
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

    if name == "test_all_endpoints":
        base_url = args["base_url"].rstrip("/")

        async with httpx.AsyncClient() as client:
            try:
                openapi_spec = await _fetch_openapi_spec(client, base_url)
                components = openapi_spec.get("components", {})

                results = []
                for path, methods in openapi_spec.get("paths", {}).items():
                    for method, details in methods.items():
                        method_upper = method.upper()
                        path_params = _required_parameter_examples(
                            details, components, "path"
                        )
                        query_params = _required_parameter_examples(
                            details, components, "query"
                        )
                        rendered_path = _replace_path_params(path, path_params)
                        full_url = f"{base_url}{rendered_path}"

                        request_body = None
                        if method_upper in ["POST", "PUT", "PATCH"]:
                            request_schema = _extract_request_body_schema(
                                details, components
                            )
                            if request_schema:
                                request_body = _build_example_from_schema(
                                    request_schema, components
                                )

                        try:
                            test_response = await client.request(
                                method=method_upper,
                                url=full_url,
                                params=query_params or None,
                                json=request_body if request_body is not None else None,
                            )
                            results.append(
                                {
                                    "endpoint": f"{method_upper} {path}",
                                    "status": test_response.status_code,
                                    "success": test_response.is_success,
                                    "query_params_used": query_params,
                                    "path_params_used": path_params,
                                    "body_used": request_body,
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
                                    "query_params_used": query_params,
                                    "path_params_used": path_params,
                                    "body_used": request_body,
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

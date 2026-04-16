from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx


class DiscoverRequest(BaseModel):
    base_url: str


class TestEndpointRequest(BaseModel):
    url: str
    method: str
    body: Optional[Any] = None
    headers: Optional[Dict[str, str]] = None


class TestAllRequest(BaseModel):
    base_url: str


app = FastAPI(title="mcp-fastapi-wrapper")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/discover_endpoints")
async def discover_endpoints(req: DiscoverRequest):
    base_url = req.base_url.rstrip("/")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_url}/openapi.json")
            resp.raise_for_status()
            openapi_spec = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error fetching openapi.json: {e}")

    endpoints: List[Dict[str, Any]] = []
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

    return {"count": len(endpoints), "endpoints": endpoints}


@app.post("/test_endpoint")
async def test_endpoint(req: TestEndpointRequest):
    method = req.method.upper()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=req.url,
                json=req.body if req.body is not None else None,
                headers=req.headers or {},
                timeout=30,
            )

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text,
            "success": response.is_success,
        }
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test_all_endpoints")
async def test_all_endpoints(req: TestAllRequest):
    base_url = req.base_url.rstrip("/")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{base_url}/openapi.json")
            resp.raise_for_status()
            openapi_spec = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Error fetching openapi.json: {e}")

        results: List[Dict[str, Any]] = []
        for path, methods in openapi_spec.get("paths", {}).items():
            for method, details in methods.items():
                full_url = f"{base_url}{path}"
                method_upper = method.upper()
                try:
                    request_body = None
                    if method_upper in ["POST", "PUT", "PATCH"]:
                        request_body = {}

                    test_resp = await client.request(
                        method=method_upper,
                        url=full_url,
                        json=request_body if request_body is not None else None,
                        timeout=15,
                    )

                    results.append(
                        {
                            "endpoint": f"{method_upper} {path}",
                            "status": test_resp.status_code,
                            "success": test_resp.is_success,
                            "body_preview": test_resp.text[:200] if test_resp.text else None,
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

    return {"tested": len(results), "results": results}

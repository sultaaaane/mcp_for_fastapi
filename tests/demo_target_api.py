import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


class Task(BaseModel):
    id: int
    title: str
    task: str


app = FastAPI(
    title="Demo Target API for MCP",
    description="Demo Target API for MCP",
    version="0.1.0",
    port=5421,
)

TASKS: list[Task] = [
    Task(id=1, title="Setup", task="Run demo target API"),
    Task(id=2, title="Discover", task="Call discover_endpoints tool"),
]

AUTH_SCHEME = HTTPBearer(auto_error=False)
DEMO_API_TOKEN = os.getenv("DEMO_API_TOKEN", "dev-token")


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(AUTH_SCHEME),
) -> None:
    expected = f"Bearer {DEMO_API_TOKEN}"
    provided = (
        f"{credentials.scheme} {credentials.credentials}" if credentials else None
    )

    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/")
async def root():
    return {"health": "healthy", "service": "demo-target-api"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/tasks")
async def get_tasks(_: None = Depends(require_auth)):
    return {"count": len(TASKS), "tasks": [task.model_dump() for task in TASKS]}


@app.post("/tasks")
async def add_task(task: Task, _: None = Depends(require_auth)):
    if any(existing.id == task.id for existing in TASKS):
        raise HTTPException(status_code=409, detail="Task id already exists")
    TASKS.append(task)
    return {"created": task.model_dump()}


@app.patch("/tasks")
async def update_task(task: Task, _: None = Depends(require_auth)):
    for index, existing in enumerate(TASKS):
        if existing.id == task.id:
            TASKS[index] = task
            return {"updated": task.model_dump()}
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks")
async def delete_task(
    task_id: int = Query(..., alias="id", description="Task id to delete"),
    _: None = Depends(require_auth),
):
    for index, existing in enumerate(TASKS):
        if existing.id == task_id:
            removed = TASKS.pop(index)
            return {"deleted": removed.model_dump()}
    raise HTTPException(status_code=404, detail="Task not found")

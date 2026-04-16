from fastapi import FastAPI, HTTPException, Query
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


@app.get("/")
async def root():
    return {"health": "healthy", "service": "demo-target-api"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/tasks")
async def get_tasks():
    return {"count": len(TASKS), "tasks": [task.model_dump() for task in TASKS]}


@app.post("/tasks")
async def add_task(task: Task):
    if any(existing.id == task.id for existing in TASKS):
        raise HTTPException(status_code=409, detail="Task id already exists")
    TASKS.append(task)
    return {"created": task.model_dump()}


@app.patch("/tasks")
async def update_task(task: Task):
    for index, existing in enumerate(TASKS):
        if existing.id == task.id:
            TASKS[index] = task
            return {"updated": task.model_dump()}
    raise HTTPException(status_code=404, detail="Task not found")


@app.delete("/tasks")
async def delete_task(id: int = Query(..., description="Task id to delete")):
    for index, existing in enumerate(TASKS):
        if existing.id == id:
            removed = TASKS.pop(index)
            return {"deleted": removed.model_dump()}
    raise HTTPException(status_code=404, detail="Task not found")

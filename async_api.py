import asyncio
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ciberscore_pentest_ollama_agent

app = FastAPI(title="Async Agent API")
FRONTEND_ORIGIN = "http://192.168.10.165:5173"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = asyncio.Lock()

EXECUTOR_MAX_WORKERS = 4
executor: Optional[ThreadPoolExecutor] = None


class RunRequest(BaseModel):
    target: str
    timeout: Optional[int] = None


class RunResponse(BaseModel):
    job_id: str


@app.on_event("startup")
async def on_startup():
    global executor
    executor = ThreadPoolExecutor(max_workers=EXECUTOR_MAX_WORKERS)


@app.on_event("shutdown")
async def on_shutdown():
    global executor
    if executor:
        executor.shutdown(wait=False)


async def _set_job_status(job_id: str, **kwargs):
    async with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return
        job.update(kwargs)


async def _run_agent_in_background(job_id: str, target: str):

    await _set_job_status(job_id, status="running", started_at=datetime.utcnow().isoformat())
    loop = asyncio.get_running_loop()

    try:
        coro = loop.run_in_executor(executor, ciberscore_pentest_ollama_agent.start_pentest, target)
        result = await asyncio.wait_for(coro,172800) # 2 days by the moment
        await _set_job_status(job_id, status="done", output=result, finished_at=datetime.utcnow().isoformat())
    except asyncio.TimeoutError:
        tb = f"Job timed out "
        await _set_job_status(job_id, status="failed", output=tb, finished_at=datetime.utcnow().isoformat())
    except Exception as e:
        tb = traceback.format_exc()
        await _set_job_status(job_id, status="failed", output=f"Exception: {e}\n{tb}", finished_at=datetime.utcnow().isoformat())


@app.post("/startpentest", response_model=RunResponse)
async def run(req: RunRequest):
    if not req.target or not req.target.strip():
        raise HTTPException(status_code=400, detail="target must be a non-empty string")

    job_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    job_record = {
        "job_id": job_id,
        "status": "pending",
        "target": req.target,
        "created_at": now,
        "started_at": None,
        "finished_at": None,
        "output": None,
    }

    async with jobs_lock:
        jobs[job_id] = job_record

    asyncio.create_task(_run_agent_in_background(job_id, req.target))

    return RunResponse(job_id=job_id)


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    async with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job_id not found")
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "target": job["target"],
            "created_at": job["created_at"],
            "started_at": job["started_at"],
            "finished_at": job["finished_at"],
            "output": job["output"],
        }


@app.get("/health")
async def health():
    return {"status": "ok", "jobs_in_memory": len(jobs)}

if __name__ == "__main__":
    uvicorn.run("async_api:app", host="0.0.0.0", port=8000, reload=False)
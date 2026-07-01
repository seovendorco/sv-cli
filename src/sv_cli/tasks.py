"""Async task helpers.

The public API root currently advertises tool endpoints, not a separate task
endpoint. This module therefore keeps task handling generic: task-creating tool
commands record the tool that produced a task ID, then task status/result calls
use that tool endpoint with status/result actions unless a future definition
states otherwise.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .api_client import APIClient
from .definitions import DefinitionsManager
from .errors import ConfigError, TimeoutError
from .utils import app_dir, read_json_file, write_json_file

TASK_ID_KEYS = ("task_id", "taskId", "task", "id", "job_id", "jobId")
STATUS_KEYS = ("status", "state", "task_status")
DONE_STATES = {"done", "complete", "completed", "success", "succeeded", "finished", "ready"}
ERROR_STATES = {"error", "failed", "failure", "cancelled", "canceled"}


def tasks_path() -> Path:
    return app_dir() / "tasks.json"


def load_tasks() -> dict[str, Any]:
    return read_json_file(tasks_path(), {}) or {}


def save_task(task_id: str, tool: str, endpoint: str | None = None) -> None:
    tasks = load_tasks()
    tasks[task_id] = {"tool": tool, "endpoint": endpoint, "created_at": int(time.time())}
    write_json_file(tasks_path(), tasks)


def get_task_tool(task_id: str, tool: str | None = None) -> str:
    if tool:
        return tool
    tasks = load_tasks()
    entry = tasks.get(task_id)
    if entry and entry.get("tool"):
        return str(entry["tool"])
    raise ConfigError(
        f'No local tool mapping found for task "{task_id}". Re-run with --tool, for example: '
        f"sv task status {task_id} --tool seogpt2"
    )


def extract_task_id(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in TASK_ID_KEYS:
            value = data.get(key)
            if value:
                return str(value)
        for value in data.values():
            found = extract_task_id(value)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = extract_task_id(item)
            if found:
                return found
    return None


def extract_status(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in STATUS_KEYS:
            value = data.get(key)
            if value:
                return str(value).lower()
        for value in data.values():
            found = extract_status(value)
            if found:
                return found
    return None


def has_result(data: Any) -> bool:
    if isinstance(data, dict):
        return any(key in data for key in ("result", "results", "data", "output", "content"))
    return data is not None


def status_payload(task_id: str) -> dict[str, Any]:
    return {"action": "getTaskStatus", "task_id": task_id}


def result_payload(task_id: str) -> dict[str, Any]:
    return {"action": "getResult", "task_id": task_id}


def wait_for_task(
    *,
    task_id: str,
    tool: str,
    api_key: str,
    definitions: DefinitionsManager,
    client: APIClient,
    timeout_seconds: int = 600,
    poll_interval: int = 5,
    no_progress: bool = False,
    console: Console | None = None,
) -> Any:
    console = console or Console(stderr=True)
    entry = definitions.get_tool(tool)
    endpoint = entry.get("endpoint")
    if not endpoint:
        raise ConfigError(f'Tool "{tool}" does not have an endpoint in definitions cache.')

    deadline = time.monotonic() + timeout_seconds

    def poll_once() -> Any:
        status_response = client.request_tool(
            endpoint=str(endpoint), payload=status_payload(task_id), api_key=api_key, timeout=poll_interval + 30
        ).data
        status = extract_status(status_response)
        if status in ERROR_STATES:
            return status_response
        if status in DONE_STATES or has_result(status_response):
            # Some APIs return the result directly from status. If not, ask for result.
            if any(key in status_response for key in ("result", "results", "output", "content")):
                return status_response
            return client.request_tool(endpoint=str(endpoint), payload=result_payload(task_id), api_key=api_key).data
        return None

    if no_progress:
        while time.monotonic() < deadline:
            result = poll_once()
            if result is not None:
                return result
            time.sleep(poll_interval)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("Polling task {task.fields[task_id]}"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress_task = progress.add_task("poll", task_id=task_id, total=None)
            while time.monotonic() < deadline:
                result = poll_once()
                if result is not None:
                    progress.update(progress_task, completed=1)
                    return result
                time.sleep(poll_interval)

    raise TimeoutError(
        "The task is still running.\n"
        f"Task ID:\n{task_id}\n"
        "Check later with:\n"
        f"sv task status {task_id}\n"
        f"sv task result {task_id}"
    )

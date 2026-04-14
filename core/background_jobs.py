"""Background job helpers for async-style step work."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable

import streamlit as st


@dataclass
class BackgroundJobStore:
    executor: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(max_workers=4))
    jobs: dict[str, Future] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)

    def ensure(self, job_id: str, fn: Callable[[], Any]) -> Future:
        with self.lock:
            future = self.jobs.get(job_id)
            if future is None:
                future = self.executor.submit(fn)
                self.jobs[job_id] = future
            return future

    def pop(self, job_id: str) -> Future | None:
        with self.lock:
            return self.jobs.pop(job_id, None)


@st.cache_resource
def get_background_job_store() -> BackgroundJobStore:
    """Return the shared background job store."""
    return BackgroundJobStore()

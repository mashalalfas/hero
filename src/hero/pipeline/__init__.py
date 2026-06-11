"""Pipeline — automated execution of pipeline manifests created by `hero go`.

Provides PipelineExecutor to poll dispatch queue, track soldier completion,
and update pipeline manifest status through the full lifecycle.
"""

from __future__ import annotations

from hero.pipeline.executor import PipelineExecutor, PipelineResult
from hero.pipeline.watcher import PipelineWatcher, start_background_watcher

__all__ = ["PipelineExecutor", "PipelineResult", "PipelineWatcher", "start_background_watcher"]

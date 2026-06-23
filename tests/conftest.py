from __future__ import annotations

import importlib.machinery
import importlib.util
from collections.abc import Iterator
from types import ModuleType
from typing import Any

import pytest


class _PatchAfterExecLoader:
    def __init__(
        self,
        loader: importlib.machinery.SourceFileLoader,
        patches: dict[str, Any],
    ) -> None:
        self._loader = loader
        self._patches = patches

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        create_module = getattr(self._loader, "create_module", None)
        if create_module is None:
            return None
        return create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        self._loader.exec_module(module)
        for name, value in self._patches.items():
            setattr(module, name, value)


@pytest.fixture(autouse=True)
def isolate_report_backed_unit_tests(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Iterator[None]:
    target_patches = {
        "test_build_payload_groups_approval_bundles": {
            "generate_goal_unblock_board_20260620": {
                "load_completed_bundles": lambda: set(),
            },
        },
        "test_build_rows_maps_grouped_rks_status": {
            "generate_goal_evidence_ledger_20260620": {
                "load_final_evidence_statuses": lambda: {},
            },
        },
    }.get(request.node.name)
    if not target_patches:
        yield
        return

    original_spec_from_file_location = importlib.util.spec_from_file_location

    def patched_spec_from_file_location(
        name: str,
        location: str,
        *args: Any,
        **kwargs: Any,
    ) -> importlib.machinery.ModuleSpec | None:
        spec = original_spec_from_file_location(name, location, *args, **kwargs)
        if spec is None or name not in target_patches:
            return spec
        if not isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            return spec
        spec.loader = _PatchAfterExecLoader(spec.loader, target_patches[name])
        return spec

    monkeypatch.setattr(importlib.util, "spec_from_file_location", patched_spec_from_file_location)
    yield

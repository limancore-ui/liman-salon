"""Explicit pytest plugin for isolated PostgreSQL integration-test runs.

Load with ``pytest -p tests.postgres_safety_plugin``. The plugin owns one
process-wide lifecycle: after completion or failed initialization, a second
guarded run in the same interpreter is rejected. The installed session shim
may still be referenced by imported application modules, so it is deliberately
not removed from ``sys.modules`` during teardown.
"""

from __future__ import annotations

from typing import Any, Callable

from tests.postgres_safety import (
    PostgresTestSafetyError,
    block_unapproved_engine_creation,
    configure_guarded_postgres_runtime,
    install_isolated_test_settings,
    restore_engine_creation,
    restore_isolated_test_settings,
)


class _PluginLifecycle:
    """Transactional, one-shot owner for pytest plugin resources."""

    def __init__(
        self,
        *,
        configure_runtime: Callable[..., tuple[Any, Any]] = configure_guarded_postgres_runtime,
        install_settings: Callable[..., tuple[Any, Any, Any]] = install_isolated_test_settings,
        install_engine_patches: Callable[..., list[Any]] = block_unapproved_engine_creation,
        restore_engine_patches: Callable[[list[Any]], None] = restore_engine_creation,
        restore_settings: Callable[[tuple[Any, Any, Any]], None] = restore_isolated_test_settings,
    ) -> None:
        self._configure_runtime = configure_runtime
        self._install_settings = install_settings
        self._install_engine_patches = install_engine_patches
        self._restore_engine_patches = restore_engine_patches
        self._restore_settings = restore_settings
        self._state = "new"
        self._engine: Any | None = None
        self._session_module: Any | None = None
        self._settings_patch: tuple[Any, Any, Any] | None = None
        self._engine_patches: list[Any] | None = None
        self._config_resources: list[tuple[str, Any]] = []
        self._config: Any | None = None
        self._cleanup_complete = False

    def configure(self, config: Any) -> None:
        if self._state != "new":
            raise PostgresTestSafetyError(
                "PostgreSQL test harness supports one lifecycle per process; start a new process."
            )

        self._config = config
        self._state = "initializing"
        try:
            self._engine, self._session_module = self._configure_runtime()
            self._settings_patch = self._install_settings()
            self._engine_patches = self._install_engine_patches()
            self._attach_config_resources(config)
        except BaseException as error:
            cleanup_failed = self._cleanup()
            self._state = "failed"
            self._cleanup_complete = True
            if not isinstance(error, Exception):
                raise
            if cleanup_failed:
                raise PostgresTestSafetyError(
                    "PostgreSQL test harness initialization failed and cleanup was incomplete."
                ) from None
            if isinstance(error, PostgresTestSafetyError):
                raise
            raise PostgresTestSafetyError(
                "PostgreSQL test harness could not complete initialization."
            ) from None

        self._state = "active"

    def unconfigure(self) -> None:
        if self._cleanup_complete:
            return
        if self._state == "new":
            self._state = "completed"
            self._cleanup_complete = True
            return

        cleanup_failed = self._cleanup()
        self._state = "completed" if not cleanup_failed else "failed"
        self._cleanup_complete = True
        if cleanup_failed:
            raise PostgresTestSafetyError(
                "PostgreSQL test harness cleanup was incomplete."
            ) from None

    def _attach_config_resources(self, config: Any) -> None:
        values = (
            ("_liman_postgres_test_engine", self._engine),
            ("_liman_postgres_test_session_module", self._session_module),
            ("_liman_postgres_engine_factory_patches", self._engine_patches),
            ("_liman_postgres_settings_patch", self._settings_patch),
        )
        if any(hasattr(config, name) for name, _ in values):
            raise PostgresTestSafetyError(
                "PostgreSQL test harness configuration contains stale lifecycle state."
            )

        for name, value in values:
            try:
                setattr(config, name, value)
                if getattr(config, name, None) is not value:
                    raise RuntimeError("Pytest resource registration did not stick.")
            except BaseException:
                if getattr(config, name, None) is value:
                    self._config_resources.append((name, value))
                raise
            self._config_resources.append((name, value))

    def _cleanup(self) -> bool:
        """Attempt every cleanup action and leave the session provider disabled."""

        failed = False
        provider = None
        if self._session_module is not None:
            provider = getattr(
                self._session_module,
                "__liman_guarded_session_provider__",
                None,
            )
        if provider is not None:
            try:
                provider.disable()
            except Exception:
                failed = True

        if self._engine is not None:
            try:
                self._engine.dispose()
            except Exception:
                failed = True

        if self._engine_patches is not None:
            try:
                self._restore_engine_patches(self._engine_patches)
            except Exception:
                failed = True

        if self._settings_patch is not None:
            try:
                self._restore_settings(self._settings_patch)
            except Exception:
                failed = True

        for name, value in reversed(self._config_resources):
            try:
                if self._config is not None and getattr(self._config, name, None) is value:
                    delattr(self._config, name)
            except Exception:
                failed = True
        self._config_resources.clear()
        return failed

_PLUGIN_LIFECYCLE = _PluginLifecycle()


def pytest_configure(config: Any) -> None:
    _PLUGIN_LIFECYCLE.configure(config)


def pytest_unconfigure(config: Any) -> None:
    # Keep the argument in the hook signature; the lifecycle owns the exact
    # config object whose attributes it installed.
    del config
    _PLUGIN_LIFECYCLE.unconfigure()

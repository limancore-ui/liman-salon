from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.postgres_safety import (
    PostgresTestSafetyError,
    block_unapproved_engine_creation,
    configure_guarded_postgres_runtime,
    install_guarded_get_db_override,
    install_guarded_session_module,
    install_isolated_test_settings,
    require_guard_for_postgres_test_file,
    restore_engine_creation,
    restore_isolated_test_settings,
)
from tests.postgres_safety_plugin import _PluginLifecycle


def test_guarded_session_module_denies_application_global_database_access() -> None:
    engine = Mock()
    db_session = Mock()
    session_constructor = Mock(return_value=db_session)
    sessionmaker_factory = Mock(return_value=session_constructor)

    module = install_guarded_session_module(
        engine,
        modules={},
        sessionmaker_factory=sessionmaker_factory,
    )

    sessionmaker_factory.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    with pytest.raises(PostgresTestSafetyError, match="Application-global"):
        module.SessionLocal()
    with pytest.raises(PostgresTestSafetyError, match="Application-global"):
        module.engine.connect()
    with pytest.raises(PostgresTestSafetyError, match="must be overridden"):
        module.get_db()
    engine.connect.assert_not_called()


def test_fastapi_override_uses_the_guarded_engine_session_factory() -> None:
    engine = Mock()
    db_session = Mock()
    session_constructor = Mock(return_value=db_session)
    sessionmaker_factory = Mock(return_value=session_constructor)
    module = install_guarded_session_module(
        engine,
        modules={},
        sessionmaker_factory=sessionmaker_factory,
    )
    application = SimpleNamespace(dependency_overrides={})

    previous = install_guarded_get_db_override(application, module)

    assert previous == {}
    assert application.dependency_overrides == {
        module.get_db: module.guarded_get_db,
    }
    dependency = application.dependency_overrides[module.get_db]
    session_generator = dependency()
    assert next(session_generator) is db_session
    with pytest.raises(StopIteration):
        next(session_generator)
    db_session.commit.assert_called_once()
    db_session.close.assert_called_once()


@pytest.mark.parametrize(
    "loaded_module",
    (
        "app.db",
        "app.db.session",
        "app.main",
        "app.api.deps",
        "app.core.security",
        "app.services.media.deps",
    ),
)
def test_runtime_rejects_early_application_import_before_engine_factory(
    loaded_module: str,
) -> None:
    engine_factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="before application imports"):
        configure_guarded_postgres_runtime(
            modules={loaded_module: object()},
            engine_factory=engine_factory,
        )

    engine_factory.assert_not_called()


def test_runtime_installs_session_shim_after_guarded_engine_creation() -> None:
    engine = Mock()
    engine_factory = Mock(return_value=engine)
    sessionmaker_factory = Mock(return_value=Mock())
    modules: dict[str, object] = {}

    result_engine, session_module = configure_guarded_postgres_runtime(
        environ={},
        engine_factory=engine_factory,
        modules=modules,
        sessionmaker_factory=sessionmaker_factory,
    )

    assert result_engine is engine
    engine_factory.assert_called_once_with(environ={})
    sessionmaker_factory.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    assert modules["app.db.session"] is session_module
    engine.connect.assert_not_called()


def test_runtime_disposes_engine_when_session_shim_initialization_fails() -> None:
    engine = Mock()
    modules: dict[str, object] = {}

    with pytest.raises(RuntimeError, match="synthetic sessionmaker failure"):
        configure_guarded_postgres_runtime(
            environ={},
            engine_factory=Mock(return_value=engine),
            modules=modules,
            sessionmaker_factory=Mock(side_effect=RuntimeError("synthetic sessionmaker failure")),
        )

    engine.dispose.assert_called_once()
    assert "app.db.session" not in modules


def test_session_shim_registration_rolls_back_partial_module_insertion() -> None:
    class InsertThenRaise(dict):
        def __init__(self):
            super().__init__()
            self.failed_once = False

        def __setitem__(self, name, value):
            super().__setitem__(name, value)
            if name == "app.db.session" and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("synthetic module registration failure")

    modules = InsertThenRaise()
    with pytest.raises(PostgresTestSafetyError, match="could not install the session shim"):
        install_guarded_session_module(Mock(), modules=modules)

    assert "app.db.session" not in modules


def test_unapproved_sqlalchemy_engine_factory_is_blocked_and_restored() -> None:
    engine_factory = Mock()
    sqlalchemy_module = SimpleNamespace(create_engine=engine_factory)

    patches = block_unapproved_engine_creation(
        target_modules=(sqlalchemy_module,),
    )
    with pytest.raises(PostgresTestSafetyError, match="Direct SQLAlchemy engine"):
        sqlalchemy_module.create_engine("synthetic-url")
    engine_factory.assert_not_called()

    restore_engine_creation(patches)
    assert sqlalchemy_module.create_engine is engine_factory


def test_engine_factory_restore_does_not_overwrite_a_later_value() -> None:
    original = Mock()
    later_value = Mock()
    sqlalchemy_module = SimpleNamespace(create_engine=original)

    patches = block_unapproved_engine_creation(target_modules=(sqlalchemy_module,))
    sqlalchemy_module.create_engine = later_value
    restore_engine_creation(patches)

    assert sqlalchemy_module.create_engine is later_value


def test_settings_patch_is_transactional_and_restore_is_conditional() -> None:
    original_loader = Mock()
    later_loader = Mock()

    class FailOnceOnSettingsPatch:
        def __init__(self):
            object.__setattr__(self, "failed_once", False)
            object.__setattr__(self, "get_settings", original_loader)

        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)
            if name == "get_settings" and not getattr(self, "failed_once", False):
                object.__setattr__(self, "failed_once", True)
                raise RuntimeError("synthetic settings assignment failure")

    failing_module = FailOnceOnSettingsPatch()
    with pytest.raises(PostgresTestSafetyError, match="could not install isolated settings"):
        install_isolated_test_settings(failing_module)
    assert failing_module.get_settings is original_loader

    settings_module = SimpleNamespace(get_settings=original_loader)
    patch = install_isolated_test_settings(settings_module)
    settings_module.get_settings = later_loader
    restore_isolated_test_settings(patch)
    assert settings_module.get_settings is later_loader


def test_real_sqlalchemy_factory_entry_points_are_blocked_without_engine_creation() -> None:
    import importlib

    import sqlalchemy
    from sqlalchemy import engine as sqlalchemy_engine

    create_module = importlib.import_module("sqlalchemy.engine.create")
    target_modules = (sqlalchemy, sqlalchemy_engine, create_module)
    originals = [module.create_engine for module in target_modules]
    patches = block_unapproved_engine_creation()

    try:
        for module in target_modules:
            with pytest.raises(PostgresTestSafetyError, match="Direct SQLAlchemy engine"):
                module.create_engine("sqlite://")
    finally:
        restore_engine_creation(patches)

    assert [module.create_engine for module in target_modules] == originals


def test_plugin_cleanup_disables_provider_restores_owned_patches_and_disposes_only_engine() -> None:
    engine = Mock()
    session_module = install_guarded_session_module(engine, modules={})
    provider = session_module.__liman_guarded_session_provider__
    original_loader = Mock()
    settings_module = SimpleNamespace(get_settings=original_loader)
    original_factory = Mock()
    sqlalchemy_module = SimpleNamespace(create_engine=original_factory)
    lifecycle = _PluginLifecycle(
        configure_runtime=Mock(return_value=(engine, session_module)),
        install_settings=lambda: install_isolated_test_settings(settings_module),
        install_engine_patches=lambda: block_unapproved_engine_creation(
            target_modules=(sqlalchemy_module,),
        ),
    )
    config = SimpleNamespace()

    lifecycle.configure(config)
    assert provider.enabled
    assert sqlalchemy_module.create_engine is not original_factory
    assert settings_module.get_settings is not original_loader

    lifecycle.unconfigure()

    assert not provider.enabled
    engine.dispose.assert_called_once()
    engine.drop_all.assert_not_called()
    engine.execute.assert_not_called()
    assert sqlalchemy_module.create_engine is original_factory
    assert settings_module.get_settings is original_loader
    assert not hasattr(config, "_liman_postgres_test_engine")
    assert not hasattr(config, "_liman_postgres_test_session_module")


def test_plugin_lifecycle_disables_real_provider_and_rejects_a_second_run() -> None:
    engine = Mock()
    modules: dict[str, object] = {}
    runtime = Mock(
        side_effect=lambda: configure_guarded_postgres_runtime(
            environ={},
            engine_factory=Mock(return_value=engine),
            modules=modules,
        ),
    )
    settings_module = SimpleNamespace(get_settings=Mock())
    lifecycle = _PluginLifecycle(
        configure_runtime=runtime,
        install_settings=lambda: install_isolated_test_settings(settings_module),
        install_engine_patches=lambda: [],
    )
    config = SimpleNamespace()

    lifecycle.configure(config)
    session_module = modules["app.db.session"]
    provider = session_module.__liman_guarded_session_provider__
    assert provider.enabled
    lifecycle.unconfigure()

    assert not provider.enabled
    assert modules["app.db.session"] is session_module
    engine.dispose.assert_called_once()
    with pytest.raises(PostgresTestSafetyError, match="one lifecycle per process"):
        lifecycle.configure(SimpleNamespace())
    runtime.assert_called_once()


@pytest.mark.parametrize("failure_stage", ("runtime", "settings", "engine_patches", "config"))
def test_plugin_initialization_failures_clean_every_installed_resource(failure_stage: str) -> None:
    engine = Mock()
    session_module = (
        None
        if failure_stage == "runtime"
        else install_guarded_session_module(engine, modules={})
    )
    runtime = Mock(
        side_effect=RuntimeError("synthetic runtime failure")
        if failure_stage == "runtime"
        else None,
        return_value=(engine, session_module),
    )
    original_loader = Mock()
    settings_module = SimpleNamespace(get_settings=original_loader)
    original_factory = Mock()
    first_module = SimpleNamespace(create_engine=original_factory)

    class FailOnceOnPatch(SimpleNamespace):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.failed_once = False

        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)
            if name == "create_engine" and not self.failed_once:
                object.__setattr__(self, "failed_once", True)
                raise RuntimeError("synthetic patch failure")

    second_original = Mock()
    second_module = FailOnceOnPatch(create_engine=second_original)
    def install_settings():
        if failure_stage == "settings":
            raise RuntimeError("synthetic settings failure")
        return install_isolated_test_settings(settings_module)

    def install_patches():
        if failure_stage == "engine_patches":
            return block_unapproved_engine_creation(
                target_modules=(first_module, second_module),
            )
        return block_unapproved_engine_creation(target_modules=(first_module,))

    lifecycle = _PluginLifecycle(
        configure_runtime=runtime,
        install_settings=install_settings,
        install_engine_patches=install_patches,
    )

    class FailDuringResourceAttach(SimpleNamespace):
        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)
            if failure_stage == "config" and name == "_liman_postgres_test_session_module":
                raise RuntimeError("synthetic config registration failure")

    config = FailDuringResourceAttach()
    with pytest.raises(PostgresTestSafetyError):
        lifecycle.configure(config)

    if session_module is not None:
        assert not session_module.__liman_guarded_session_provider__.enabled
    if failure_stage == "runtime":
        engine.dispose.assert_not_called()
    else:
        engine.dispose.assert_called_once()
    assert settings_module.get_settings is original_loader
    assert first_module.create_engine is original_factory
    if failure_stage == "engine_patches":
        assert second_module.create_engine is second_original
    assert not hasattr(config, "_liman_postgres_test_engine")
    assert not hasattr(config, "_liman_postgres_test_session_module")
    with pytest.raises(PostgresTestSafetyError, match="one lifecycle per process"):
        lifecycle.configure(SimpleNamespace())


def test_plugin_import_is_inert_for_mock_test_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    import tests.postgres_safety_plugin as plugin

    configure_runtime = Mock()
    monkeypatch.setattr(plugin, "configure_guarded_postgres_runtime", configure_runtime)

    assert configure_runtime.call_count == 0


def test_mock_files_need_no_guard_but_postgres_files_do() -> None:
    require_guard_for_postgres_test_file("test_mock_api.py", runtime_ready=False)
    require_guard_for_postgres_test_file("test_api_postgres.py", runtime_ready=True)

    with pytest.raises(PostgresTestSafetyError, match="pre-import safety plugin"):
        require_guard_for_postgres_test_file(
            "test_api_postgres.py",
            runtime_ready=False,
        )


def test_integration_settings_are_synthetic_and_do_not_call_application_loader() -> None:
    original_loader = Mock()
    config_module = SimpleNamespace(get_settings=original_loader)

    patch = install_isolated_test_settings(config_module)
    settings = config_module.get_settings()

    assert settings.app_name == "Liman Salon isolated PostgreSQL tests"
    assert not hasattr(settings, "database_url")
    original_loader.assert_not_called()
    restore_isolated_test_settings(patch)
    assert config_module.get_settings is original_loader

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional
import logging
import click

from flux.config import Configuration
from flux.decorators import task
from flux.output_storage import OutputStorage
from flux.executors import AbstractExecutor

logger = logging.getLogger("flux.plugins")

class Plugin(ABC):
    @abstractmethod
    def register(self) -> None:
        """Register the plugin with Flux."""
        pass

class TaskPlugin(Plugin):
    def __init__(self, name: str, func: Callable):
        self.name = name
        self.func = func

    def register(self) -> None:
        """Register a custom task as a Flux task."""
        decorated_task = task.with_options(name=self.name)(self.func)
        setattr(decorated_task, "__flux_plugin__", True)
        logger.info(f"Registered task plugin: {self.name}")

class ExecutorPlugin(Plugin):
    def __init__(self, name: str, executor_class: type[AbstractExecutor]):
        self.name = name
        self.executor_class = executor_class

    def register(self) -> None:
        """Register a custom executor."""
        logger.info(f"Registered executor plugin: {self.name}")

class StoragePlugin(Plugin):
    def __init__(self, name: str, storage_class: type[OutputStorage]):
        self.name = name
        self.storage_class = storage_class

    def register(self) -> None:
        """Register a custom storage backend."""
        logger.info(f"Registered storage plugin: {self.name}")

class PluginManager:
    def __init__(self):
        self.plugins: dict[str, Plugin] = {}
        self.plugin_dir = Path(Configuration.get().settings.home) / "plugins"
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    def load_plugins(self) -> None:
        """Load all plugins from the plugins directory."""
        for plugin_file in self.plugin_dir.glob("*.py"):
            try:
                module_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, Plugin):
                            self.plugins[attr.name] = attr
                            attr.register()
                            logger.info(f"Loaded plugin: {attr.name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {str(e)}")

    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self.plugins.get(name)

    @staticmethod
    def default() -> PluginManager:
        return PluginManager()

@click.group()
def plugin():
    """Manage Flux plugins."""
    pass

@plugin.command("add")
@click.argument("name")
@click.argument("filename")
def add_plugin(name: str, filename: str):
    """Add a new plugin to Flux."""
    try:
        plugin_file = Path(filename)
        if not plugin_file.exists():
            raise ValueError(f"File {filename} does not exist.")
        dest = PluginManager.default().plugin_dir / f"{name}.py"
        dest.write_text(plugin_file.read_text())
        click.echo(f"Added plugin '{name}' to {dest}")
        PluginManager.default().load_plugins()
    except Exception as e:
        click.echo(f"Error adding plugin: {str(e)}", err=True)

@plugin.command("list")
def list_plugins():
    """List all registered plugins."""
    plugins = PluginManager.default().plugins
    if not plugins:
        click.echo("No plugins found.")
        return
    for name in plugins:
        click.echo(f"- {name}")

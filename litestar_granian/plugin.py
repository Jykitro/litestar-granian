from importlib.util import find_spec
from typing import TYPE_CHECKING, Optional

from litestar.plugins import CLIPluginProtocol, InitPluginProtocol
from typing_extensions import TypeGuard

if TYPE_CHECKING:
    try:
        from rich_click import Group
    except ImportError:
        from click import Group
    from litestar.config.app import AppConfig
    from litestar.logging.config import BaseLoggingConfig, LoggingConfig
    from litestar.plugins.structlog import StructlogPlugin

STRUCTLOG_INSTALLED = find_spec("structlog") is not None


class GranianPlugin(InitPluginProtocol, CLIPluginProtocol):
    """Granian server plugin with enhanced logging setup."""

    __slots__ = ()

    def on_cli_init(self, cli: "Group") -> None:  # noqa: PLR6301
        """Add `granian` run command to litestar CLI."""
        from litestar.cli.main import litestar_group as cli

        from litestar_granian.cli import run_command

        cli.add_command(run_command)  # pyright: ignore[reportArgumentType]

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Enhance app logging configuration for Granian workers."""
        if is_logging_config(app_config.logging_config):
            _configure_stdlib_logging(app_config.logging_config)

        if STRUCTLOG_INSTALLED:
            structlog_plugin = _get_structlog_plugin(app_config)
            if structlog_plugin and is_logging_config(
                structlog_plugin._config.structlog_logging_config.standard_lib_logging_config
            ):
                _configure_structlog(structlog_plugin)

        return super().on_app_init(app_config)


# --------------------------------------------------------------------------- #
#                               Helpers
# --------------------------------------------------------------------------- #

def _get_structlog_plugin(app_config: "AppConfig") -> "Optional[StructlogPlugin]":
    from litestar.plugins.structlog import StructlogPlugin

    for plugin in app_config.plugins:
        if isinstance(plugin, StructlogPlugin) and hasattr(plugin, "_config"):
            return plugin
    return None


def is_structlog_plugin(plugin: "InitPluginProtocol") -> TypeGuard["StructlogPlugin"]:
    from litestar.plugins.structlog import StructlogPlugin

    return isinstance(plugin, StructlogPlugin) and hasattr(plugin, "_config")


def is_logging_config(config: "Optional[BaseLoggingConfig]") -> TypeGuard["LoggingConfig"]:
    from litestar.logging.config import LoggingConfig

    return config is not None and isinstance(config, LoggingConfig)


# --------------------------------------------------------------------------- #
#                           Logging Configuration
# --------------------------------------------------------------------------- #

def _configure_stdlib_logging(logging_config: "LoggingConfig") -> None:
    """Ensure `_granian` and `granian.access` loggers exist and are consistent."""
    default_formatter = {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }

    if "generic" not in logging_config.formatters:
        logging_config.formatters["generic"] = logging_config.formatters.get("standard", default_formatter)

    if "console" not in logging_config.handlers:
        logging_config.handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "generic",
        }

    for logger_name in ("_granian", "granian.access"):
        if logger_name not in logging_config.loggers:
            logging_config.loggers[logger_name] = {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            }

    logging_config.configure()


def _configure_structlog(structlog_plugin: "StructlogPlugin") -> None:
    """Configure structlog plugin with Granian-related loggers."""
    std_config = structlog_plugin._config.structlog_logging_config.standard_lib_logging_config
    assert std_config is not None, "Standard lib config missing in StructlogPlugin."

    default_formatter = {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }

    if "console" not in std_config.handlers:
        std_config.handlers["console"] = {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }

    if "standard" not in std_config.formatters:
        std_config.formatters["standard"] = default_formatter

    for logger_name in ("_granian", "granian.access"):
        if logger_name not in std_config.loggers:
            std_config.loggers[logger_name] = {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            }

    std_config.configure()

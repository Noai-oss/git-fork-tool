try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0"  # ty: ignore[invalid-assignment]

from .cli import cli  # noqa: E402

__all__ = ["__version__", "cli"]

"""
Client UI Package

This package contains reloadable UI components for the CLI client:
- formatters: Rich-based result formatters for tool outputs
- dialogs: InquirerPy-based interactive dialogs for user confirmations
"""

from .dialogs import DialogBuilder
from .formatters import ResultFormatter

__all__ = ["ResultFormatter", "DialogBuilder"]

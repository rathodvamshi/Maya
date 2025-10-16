"""Cohere support removed.

This module remains as a stub to avoid import errors if referenced indirectly.
All functions raise RuntimeError to make usage explicit in logs, but the codebase
should not import or call this module.
"""

def generate(*args, **kwargs):  # pragma: no cover
    raise RuntimeError("Cohere support removed")


def create_embedding(*args, **kwargs):  # pragma: no cover
    raise RuntimeError("Cohere support removed")

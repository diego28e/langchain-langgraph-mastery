"""mastery: the reusable package of the Modern LangChain & LangGraph Mastery course.

The package grows module by module. Code moves here when a second notebook
needs it, and every public function gets a unit test in ``tests/unit/``.

Module 00 adds:
    - ``mastery.config``: load ``.env``, check keys without revealing them,
      read course settings (model IDs) from one place.
    - ``mastery.groq_catalog``: list the models that are live on Groq today.
"""

from __future__ import annotations

__all__ = ["__version__"]

# Bumped when the public API of `mastery` changes (see CONVENTIONS.md §7).
__version__ = "0.1.0"

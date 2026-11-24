"""Opened-file token overlap.

Work identity is ``essay_writer.sources.same_source``. A bare title is not
that identity. This module keeps the filename check an opened PDF uses.
"""

from essay_writer.sources import slug, token_overlap

__all__ = ["token_overlap", "slug"]

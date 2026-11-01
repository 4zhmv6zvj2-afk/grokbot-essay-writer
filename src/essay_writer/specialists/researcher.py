"""Researcher specialist.

Dig, annotation, and known-path checks enter here. The functions stay defined
once in dig, research, research_packs, and known_paths. Cursor and Grok Build
call this entry. There is not a second dig.
"""

from __future__ import annotations

ROLE = "researcher"

_HOME = {
    "essay_dig": "essay_writer.dig",
    "consensus_status": "essay_writer.dig",
    "essay_research_summary": "essay_writer.research",
    "essay_research_full": "essay_writer.research",
    "ship_4a": "essay_writer.research_packs",
    "ship_4b": "essay_writer.research_packs",
    "bibliography_sources": "essay_writer.research_packs",
    "reconcile_before_4b": "essay_writer.research_packs",
    "real_4a_bibliography": "essay_writer.research_packs",
    "allow_research_path": "essay_writer.known_paths",
    "KNOWN_PATHS_LINE": "essay_writer.known_paths",
}


def annotation_notes(sources: list[dict[str, object]]) -> dict[str, str]:
    """Annotation text already stored on each source. Nothing is written."""
    notes: dict[str, str] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        ident = source.get("id")
        note = source.get("annotation")
        if isinstance(ident, str) and isinstance(note, str):
            notes[ident] = note
    return notes


def deliver_bibliography(essay_id: str) -> dict[str, object] | None:
    """Write the 4a pack from sources already stored. None when the list is empty."""
    from essay_writer.research_packs import bibliography_sources, ship_4a

    sources = bibliography_sources(essay_id)
    if not sources:
        return None
    return ship_4a(essay_id, sources, annotation_notes(sources))


def deliver_critical_reviews(essay_id: str) -> dict[str, object] | None:
    """Write the 4b zip from sources already stored. None when the list is empty."""
    from essay_writer.research_packs import bibliography_sources, ship_4b

    sources = bibliography_sources(essay_id)
    if not sources:
        return None
    return ship_4b(essay_id, sources, None)


def deliver_saved_sources(essay_id: str) -> bool:
    """Write the 4a and 4b files from sources already stored. False when none are stored.

    ship_4b is called with supplied None, so an existing review markdown stays.
    Sequence copy does not call this.
    """
    from essay_writer.research_packs import bibliography_sources, ship_4a, ship_4b

    sources = bibliography_sources(essay_id)
    if not sources:
        return False
    notes = annotation_notes(sources)
    ship_4a(essay_id, sources, notes)
    ship_4b(essay_id, sources, None)
    return True


def __getattr__(name: str):
    module_name = _HOME.get(name)
    if module_name is None:
        raise AttributeError(name)
    from importlib import import_module

    return getattr(import_module(module_name), name)

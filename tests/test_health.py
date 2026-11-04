import json

from essay_writer.health import essay_health
from essay_writer.server import HANDLERS


def test_health_lists_doors_and_packs(workspace):
    report = essay_health()
    assert report["ok"] is True
    assert report["alive"] is True
    assert report["read_only"] is True
    names = {door["tool"] for door in report["doors"]}
    assert names == set(HANDLERS)
    assert report["packs"] == []
    assert report["word"] == "docx-only"
    assert report["slack"] == "out"
    assert report["invent_forbid"] is True
    assert report["referencing"]["style"] == "harvard"
    assert "student" not in json.dumps(report["programme"]).casefold()


def test_health_sees_one_essay(workspace):
    (workspace / "uploads" / "MOD1004AA").mkdir()
    report = essay_health()
    assert report["essay_ids"] == ["MOD1004AA"]
    assert report["packs"][0]["stage"] == "open"

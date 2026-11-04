"""AC. Before Word, a short pack expands from gathered sentences into the brief band."""

from helpers import open_sequence, plant_gathered_source, write_upload

from essay_writer.gates import essay_gates, unquoted_exact
from essay_writer.paths import essay_dir
from essay_writer.specialists.writer import document_word_band, recover_short_word_band
from essay_writer.word import essay_pack_render_word, word_manifest

MODULE = "MOD1011AA"
USED = (
    "This article presents the author's development of a year-long module on "
    "Africa in Greco-Roman literature and its receptions."
)
UNUSED = (
    "It argues that the equivalence of curriculum diversification with "
    "decolonization can be pernicious in its tokenizing effects, and that a "
    "committed practice of decolonizing pedagogy cannot be limited to studying "
    "Africa in Greco-Roman texts, but should involve serious engagement with "
    "postcolonial and critical race theorists as well as African authors and "
    "authors from the African diaspora engaging meaningfully with the Greco-Roman "
    "traditions of displacement, identity, and place in Roman writing about Africa."
)
GATHERED = f"Smith, J. (2020). Chokepoints and crude.\n{USED} {UNUSED}\n"
PARAPHRASE = (
    "The gathered study sets out the author's development of a year-long module "
    "on Africa in Greco-Roman literature and its receptions."
)


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: essay\n"
        "Question: To what extent do Roman texts show Africa as a locus of displacement?\n"
        "Word count: 800 words (720 to 880).\n",
        encoding="utf-8",
    )


def _with_source(workspace):
    """One confirmed gathered source whose author and year are stored."""
    seq = open_sequence(MODULE)
    plant_gathered_source(seq)
    write_upload(workspace, essay_id=MODULE, name="smith.md", text=GATHERED)
    return seq


def _short_pack(seq: str, repeats: int = 22) -> dict:
    middle = " ".join([PARAPHRASE] * repeats)
    return {
        "essay_id": seq,
        "title": "Africa as a locus of Roman displacement",
        "referencing": "harvard",
        "assessment": "Individual essay",
        "genre": "essay",
        "conclusion": "open",
        "sections": [
            {
                "heading": "Introduction",
                "body": "This essay asks how far Roman writing treats Africa as a site of displacement.",
            },
            {"heading": "Africa in Roman writing", "body": middle},
            {
                "heading": "Conclusion",
                "body": "The essay therefore treats Africa as a Roman problem of place and self.",
            },
        ],
        "sources": [
            {
                "id": "src-1",
                "origin": "upload",
                "locator": f"uploads/{MODULE}/smith.md",
                "author": "Smith, J.",
                "year": "2020",
                "quote": USED,
            }
        ],
    }


def test_short_pack_recovers_into_the_brief_band_from_gathered_files(workspace):
    """A 600-word pack rises into 720–880 from an unused gathered sentence, not invention."""
    _brief()
    seq = _with_source(workspace)
    band = document_word_band(seq)
    assert band["min"] == 720
    assert band["max"] == 880
    payload = _short_pack(seq, repeats=28)
    before = " ".join(section["body"] for section in payload["sections"]).split()
    before_text = " ".join(section["body"] for section in payload["sections"])
    assert len(before) < 720
    recovered = recover_short_word_band(seq, payload)
    text = "\n".join(section["body"] for section in recovered["sections"])
    counted = len(text.split())
    assert 720 <= counted <= 880, counted
    assert "tokenizing" in text.casefold()
    assert USED not in text
    assert UNUSED not in text
    # Claim force stays. The stretch may reword, and it may not strengthen a
    # possibility into proof, a prohibition into a fact, or a recommendation
    # into a need.
    assert "cannot be limited" in text
    assert "should involve" in text
    assert "can be pernicious" in text
    assert "(Smith, 2020)" in text
    # The stretch names no process word of its own: the count stays where the
    # draft already had it, so appending adds none.
    assert text.casefold().count("gathered") == before_text.casefold().count("gathered")
    for drift in ("may prove", "is not limited", "needs serious"):
        assert drift not in text
    gathered = [GATHERED]
    assert unquoted_exact(text, gathered) == []
    gates = essay_gates(seq, recovered)
    word_band = next(item for item in gates["gates"] if item["name"] == "word-band")
    assert word_band["passed"] is True
    assert gates["plagiarism"]["passed"] is True

    prepared, report = word_manifest(seq, payload)
    assert report["word_count"]["inside"] is True
    assert 720 <= report["word_count"]["counted"] <= 880
    preview = essay_pack_render_word(seq, payload, "draft", stage="6")
    assert preview["ok"] is True, preview
    assert preview.get("refused") != "gates"
    assert preview["word_count"]["inside"] is True
    assert prepared["sections"][1]["heading"] == "Africa in Roman writing"
    cover = " ".join(preview.get("cover") or [])
    assert "Teaching partner" in cover
    assert "Awarding university" in cover


def _report_pack(seq: str, headings: list[str]) -> dict:
    """A short report pack whose sections carry the headings under test."""
    pack = _short_pack(seq, repeats=28)
    method = " ".join([PARAPHRASE] * 28)
    return {
        **pack,
        "genre": "report",
        "sections": [
            {"heading": heading, "body": method if index == 1 else "A short line."}
            for index, heading in enumerate(headings)
        ],
    }


def test_stretch_skips_a_section_whose_job_is_not_a_claim(workspace):
    """A report does not grow inside Methodology. Findings takes the sentence."""
    _brief()
    seq = _with_source(workspace)

    method_only = _report_pack(seq, ["Introduction", "Methodology", "Conclusion"])
    left = recover_short_word_band(seq, method_only)
    assert [section["body"] for section in left["sections"]] == [
        section["body"] for section in method_only["sections"]
    ]
    assert left["word_band_shortfall"]["low"] == 720

    with_findings = _report_pack(seq, ["Introduction", "Methodology", "Findings", "Conclusion"])
    grew = recover_short_word_band(seq, with_findings)
    assert grew["sections"][1]["body"] == with_findings["sections"][1]["body"]
    assert len(grew["sections"][2]["body"]) > len(with_findings["sections"][2]["body"])
    assert "tokenizing" in grew["sections"][2]["body"].casefold()

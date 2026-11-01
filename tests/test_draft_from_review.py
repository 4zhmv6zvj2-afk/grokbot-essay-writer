"""First draft is authored from 4b markdowns. One markdown per paper."""

from helpers import TOPIC, open_sequence, pack, source, write_upload

from essay_writer.draft_from_review import author_from_reviews
from essay_writer.research import essay_research_summary
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

QUOTE = "The Strait handles a large share of flows."
COVERS = (
    "Smith, J. (2020) Chokepoints and crude.\n"
    f"{QUOTE}\n"
    "The review judges aim, method, and a single-corridor limit.\n"
)
GAP_MD = (
    "Smith, J. (2020) Chokepoints and crude.\n"
    "The review judges aim, method, and a single-corridor limit.\n"
)
GAP = "fuel-price threat left unmeasured"
PASSAGE = f"{QUOTE}\n"


def _review(markdown: str, paper_id: str = "src-1") -> dict:
    return {"paper_id": paper_id, "markdown": markdown}


def _with_reviews(markdown: str = COVERS, **extra):
    body = pack()
    body["critical_reviews"] = [_review(markdown)]
    body.update(extra)
    return body


def _confirmed(workspace):
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert confirmed["stored"] is True
    return seq


def test_one_markdown_per_paper_and_quote_comes_from_it():
    result = author_from_reviews(
        [_review(COVERS)],
        [{"paper_id": "src-1", "quote": QUOTE}],
    )
    assert result["ok"] is True
    assert result["wrote"] is False
    assert result["stored"] is False
    assert result["sources"] == [
        {"paper_id": "src-1", "quote": QUOTE, "from": "critical-review"}
    ]


def test_a_second_markdown_for_the_same_paper_is_refused():
    result = author_from_reviews(
        [_review(COVERS), _review(COVERS + "A second note.\n")],
        [{"paper_id": "src-1", "quote": QUOTE}],
    )
    assert result["ok"] is False
    assert result["wrote"] is False
    assert result["issues"][0]["code"] == "critical-review"
    assert "one markdown per paper" in result["issues"][0]["reason"].casefold()


def test_missing_markdown_for_a_cited_paper_is_refused():
    result = author_from_reviews(
        [_review(COVERS, "src-2")],
        [{"paper_id": "src-1", "quote": QUOTE}],
    )
    assert result["ok"] is False
    assert "src-1" in result["issues"][0]["reason"]


def test_quote_outside_the_markdown_needs_a_real_gap():
    covered = author_from_reviews(
        [_review(GAP_MD)],
        [{"paper_id": "src-1", "quote": QUOTE}],
    )
    assert covered["ok"] is False
    assert covered["issues"][0]["code"] == "critical-review"

    already = author_from_reviews(
        [_review(COVERS)],
        [{"paper_id": "src-1", "quote": QUOTE}],
        [{"paper_id": "src-1", "gap": QUOTE, "passage": PASSAGE}],
    )
    assert already["ok"] is False
    assert "already in the critical-review markdown" in already["issues"][0]["reason"]

    no_gap = author_from_reviews(
        [_review(GAP_MD)],
        [{"paper_id": "src-1", "quote": QUOTE}],
        [{"paper_id": "src-1", "gap": "  ", "passage": PASSAGE}],
    )
    assert no_gap["ok"] is False

    opened = author_from_reviews(
        [_review(GAP_MD)],
        [{"paper_id": "src-1", "quote": QUOTE}],
        [{"paper_id": "src-1", "gap": GAP, "passage": PASSAGE}],
    )
    assert opened["ok"] is True
    assert opened["sources"][0]["from"] == "reopen"
    assert opened["sources"][0]["gap"] == GAP


def test_a_quote_in_neither_text_is_invent_forbid():
    result = author_from_reviews(
        [_review(GAP_MD)],
        [{"paper_id": "src-1", "quote": "A sentence nobody gathered."}],
        [{"paper_id": "src-1", "gap": GAP, "passage": "Unrelated passage from the paper."}],
    )
    assert result["ok"] is False
    assert result["wrote"] is False
    assert result["issues"][0]["code"] == "invent-forbid"


def test_validate_accepts_a_draft_from_the_markdown_and_still_requires_confirm(workspace):
    seq = _confirmed(workspace)
    body = _with_reviews()
    bare = pack()
    untouched = essay_pack_validate(seq, bare, "draft")
    assert untouched["passed"] is True

    draft = essay_pack_validate(seq, body, "draft")
    assert draft["ok"] is True
    assert draft["passed"] is True
    assert draft["stored"] is False
    assert draft["wrote"] is False

    changed = _with_reviews(COVERS + "One more limit.\n")
    jumped = essay_pack_validate(seq, changed, "confirm")
    assert jumped["ok"] is False
    assert jumped["refused"] == "confirm"
    assert jumped["stored"] is False

    recorded = essay_pack_validate(seq, body, "confirm")
    assert recorded["stored"] is True
    assert recorded["recorded_pass"] is True
    assert recorded["wrote"] is False


def test_author_from_without_markdowns_is_refused(workspace):
    seq = _confirmed(workspace)
    body = pack()
    body["author_from"] = "critical-review"
    refused = essay_pack_validate(seq, body, "draft")
    assert refused["ok"] is False
    assert refused["refused"] == "critical-review"
    assert refused["wrote"] is False
    assert refused["stored"] is False


def test_validate_refuses_two_markdowns_and_an_uncovered_quote(workspace):
    seq = _confirmed(workspace)
    doubled = pack()
    doubled["critical_reviews"] = [_review(COVERS), _review(COVERS + "Again.\n")]
    refused = essay_pack_validate(seq, doubled, "draft")
    assert refused["ok"] is False
    assert refused["refused"] == "critical-review"
    assert refused["stored"] is False
    assert refused["wrote"] is False

    uncovered = _with_reviews(GAP_MD)
    blocked = essay_pack_validate(seq, uncovered, "draft")
    assert blocked["refused"] == "critical-review"
    assert blocked["wrote"] is False

    invented = pack()
    invented["sources"] = [source()]
    invented["sources"][0]["quote"] = "This sentence was never gathered."
    invented["critical_reviews"] = [_review(COVERS)]
    fake = essay_pack_validate(seq, invented, "draft")
    assert fake["refused"] == "invent-forbid"
    assert fake["wrote"] is False
    assert fake["stored"] is False


def test_reopen_is_allowed_only_for_a_gap_and_word_is_not_written(workspace):
    seq = _confirmed(workspace)
    body = _with_reviews(GAP_MD)
    body["reopen"] = [{"paper_id": "src-1", "gap": GAP, "passage": PASSAGE}]
    draft = essay_pack_validate(seq, body, "draft")
    assert draft["passed"] is True
    assert draft["wrote"] is False
    preview = essay_pack_render_word(seq, body, "draft")
    assert preview["wrote"] is False
    assert preview["ok"] is True

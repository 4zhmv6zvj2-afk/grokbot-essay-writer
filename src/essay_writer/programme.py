"""Programme facts the cover may print. No student identity."""

PROGRAMME = {
    "award": "Awarding university",
    "partner": "Teaching partner",
    "title": "Undergraduate programme",
    "code": "PROG01",
}

# Examples only. object id matching the module pattern is a legal essay id.
MODULE_EXAMPLES = ("MOD1011AA", "MOD1008AA", "RPT1008AA", "MOD1004AA")

STYLE_ID = "harvard"

REFERENCING = {
    "style": STYLE_ID,
    "doc": "docs/referencing-harvard.md",
    "kb1": "KB1 subject note for this module, kept with Essay-writer/<essay_id>/",
}


def referencing_record() -> dict[str, object]:
    """Style record. EndNote and CSL are read from the checked handbook file."""
    from essay_writer.handbook import read_handbook

    record: dict[str, object] = dict(REFERENCING)
    checked = read_handbook()
    record["endnote"] = checked["endnote"]
    record["csl"] = checked["csl"]
    record["csl_reason"] = checked["csl_reason"]
    record["handbook"] = checked["handbook"]
    record["handbook_checked"] = checked["checked"]
    return record

STUDENT_KEYS = frozenset(
    {"student_name", "student_number", "student_id", "student_no", "student"}
)

PAID_RESOLVERS = frozenset(
    {
        "scopus",
        "ebsco",
        "proquest",
        "jstor",
        "sciencedirect",
        "web of science",
        "wos",
        "lexis",
        "heinonline",
    }
)

FREE_RESOLVERS = frozenset(
    {
        "crossref",
        "openalex",
        "doi.org",
        "unpaywall",
    }
)

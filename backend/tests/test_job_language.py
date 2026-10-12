"""Tests for posting-language detection and the Language filter.

The rules under test: a language is only reported when the text can carry it (short or
empty text is "unknown", never a wrong guess), every stored job gets one without any
source's help, and a facet count equals what clicking that entry returns.
"""
import pytest

from backend.analyzer.language import detect_job_language
from backend.models.db import Job

ENGLISH = (
    "We are looking for a Senior Data Engineer to build ingestion pipelines on GCP using "
    "Airflow, BigQuery and Terraform. You will work with stakeholders across the business."
)
GERMAN = (
    "Wir suchen einen Senior Data Engineer für den Aufbau von Datenpipelines auf der Google "
    "Cloud. Zu Ihren Aufgaben gehört die Entwicklung mit Airflow und BigQuery."
)
GERMAN_WITH_JARGON = (
    "Als Product Owner im Cloud Engineering Team verantwortest du das Backlog, Sprint "
    "Planning, Stakeholder Management und die Roadmap für unsere Data Platform. Remote möglich."
)
FRENCH = (
    "Nous recherchons un ingénieur de données senior pour construire des pipelines sur "
    "Google Cloud avec Airflow et BigQuery."
)


# ── the detector ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    (ENGLISH, "en"),
    (GERMAN, "de"),
    (GERMAN_WITH_JARGON, "de"),
    (FRENCH, "fr"),
])
def test_detects_the_language_of_a_description(text, expected):
    assert detect_job_language("Data Engineer", text) == expected


@pytest.mark.parametrize("description", [None, "", "   ", "<p> </p>", "12345 - 67890"])
def test_no_text_is_unknown(description):
    assert detect_job_language("Data Engineer (m/w/d)", description) is None


def test_a_short_description_is_unknown_instead_of_a_guess():
    # "Data Engineer (m/w/d)" alone is read as Afrikaans by the detector
    assert detect_job_language("Data Engineer (m/w/d)", "Wir suchen Dich!") is None


def test_the_title_pads_a_short_description():
    assert detect_job_language(
        "Senior Data Engineer for ingestion pipelines on Google Cloud", "Apply now, remote possible."
    ) == "en"


def test_markup_and_links_do_not_count_as_text():
    html = f"<div><p>{GERMAN}</p><a href='https://example.com/a/very/long/path'>apply</a></div>"
    assert detect_job_language("Engineer", html) == "de"


def test_the_answer_is_stable_across_calls():
    assert len({detect_job_language("x", GERMAN_WITH_JARGON) for _ in range(20)}) == 1


def test_a_chinese_variant_collapses_to_its_language():
    chinese = "我们正在寻找一名高级数据工程师，负责在谷歌云上使用大数据工具构建数据管道和分析平台。" * 2
    assert detect_job_language("Data Engineer", chinese) == "zh"


# ── the mapper hook: every stored job gets a language ────────────────────────

def _job(db, index, title="Engineer", description=None, **extra):
    from backend.scraper._shared.dedup import make_external_id

    url = "https://example.com/lang/%d" % index
    job = Job(external_id=make_external_id("Acme", f"{title} {index}", url), company="Acme",
              title=f"{title} {index}", url=url, status="new", description=description, **extra)
    db.add(job)
    return job


def test_a_new_job_is_given_its_language(test_db):
    job = _job(test_db, 1, description=GERMAN)
    test_db.commit()
    assert job.language == "de"


def test_a_job_without_a_description_is_left_unknown(test_db):
    job = _job(test_db, 2)
    test_db.commit()
    assert job.language is None


def test_a_language_a_source_set_is_kept(test_db):
    job = _job(test_db, 3, description=GERMAN, language="en")
    test_db.commit()
    assert job.language == "en"


def test_a_description_filled_in_later_is_detected_then(test_db):
    job = _job(test_db, 4)
    test_db.commit()
    assert job.language is None
    job.description = ENGLISH
    test_db.commit()
    assert job.language == "en"


def test_an_unrelated_update_does_not_redetect(test_db):
    job = _job(test_db, 5, description=GERMAN)
    test_db.commit()
    job.language = "nl"          # as a manual correction would
    job.seen = True
    test_db.commit()
    assert job.language == "nl"


# ── the filter and its facet ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _first_run(test_db, request):
    """First-run mode, so the auth middleware lets the requests through (see
    test_jobs_location_filter for why the app has to be up first)."""
    if "api_client" in request.fixturenames:
        request.getfixturevalue("api_client")
    from backend.models.db import Setting
    row = test_db.query(Setting).filter(Setting.key == "dashboard_api_key").first()
    if row is None:
        test_db.add(Setting(key="dashboard_api_key", value=""))
    else:
        row.value = ""
    test_db.commit()


@pytest.fixture
def posted(test_db):
    """3 English, 2 German, 1 French, 2 with no way to tell."""
    for index, text in enumerate([ENGLISH] * 3 + [GERMAN] * 2 + [FRENCH] + [None] * 2):
        _job(test_db, 100 + index, description=text)
    test_db.commit()
    return test_db


def _titles(api_client, query):
    rows = api_client.get(f"/api/jobs?status=new&{query}").json()
    return rows["jobs"] if isinstance(rows, dict) else rows


@pytest.mark.parametrize("value,expected", [
    ("en", 3), ("de", 2), ("fr", 1), ("unknown", 2),
    ("en,de", 5), ("de,unknown", 4), ("nl", 0),
])
def test_the_filter_returns_what_it_names(api_client, posted, value, expected):
    assert len(_titles(api_client, f"language={value}")) == expected


def test_no_language_filter_returns_everything(api_client, posted):
    assert len(_titles(api_client, "")) == 8


def test_the_facet_counts_sum_to_the_total(api_client, posted):
    counts = {x["name"]: x["count"]
              for x in api_client.get("/api/jobs/facets?status=new").json()["languages"]}
    assert counts == {"en": 3, "de": 2, "fr": 1, "unknown": 2}


def test_the_facet_lists_the_busiest_language_first_and_unknown_last(api_client, posted):
    names = [x["name"] for x in api_client.get("/api/jobs/facets?status=new").json()["languages"]]
    assert names == ["en", "de", "fr", "unknown"]


def test_a_facet_count_equals_what_clicking_it_returns(api_client, posted):
    for entry in api_client.get("/api/jobs/facets?status=new").json()["languages"]:
        assert entry["count"] == len(_titles(api_client, f"language={entry['name']}"))


def test_the_facet_lifts_its_own_filter_but_not_the_others(api_client, posted):
    # with German picked, English still lists (so the pick can be swapped), counted
    # under the other active filters
    counts = {x["name"]: x["count"] for x in
              api_client.get("/api/jobs/facets?status=new&language=de").json()["languages"]}
    assert counts["en"] == 3 and counts["de"] == 2


def test_a_picked_language_with_no_jobs_stays_listed_at_zero(api_client, posted):
    counts = {x["name"]: x["count"] for x in
              api_client.get("/api/jobs/facets?status=new&language=nl").json()["languages"]}
    assert counts["nl"] == 0


def test_a_job_reports_its_language(api_client, posted):
    languages = {j["language"] for j in _titles(api_client, "")}
    assert languages == {"en", "de", "fr", None}

"""The score breakdown is shown out of the scale the schema gave each category."""
from backend.analyzer.cv_scorer import breakdown_maxima

OLD = '{\n  "scores": {CV_NAMES_HERE: 0-100},\n  "breakdown": {"skills": 0-20, "experience": 0-20, "domain": 0-20, "role": 0-20, "requirements": 0-20},\n  "summary": "x"\n}'
NEW = '''{
  "scores": {CV_NAMES_HERE: 0-100},
  "breakdown": {"language": 0-50, "skills": 0-10, "experience": 0-10, "domain": 0-10, "role": 0-10, "requirements": 0-10},
  "keyword_coverage_pct": 0-100
}'''


def test_each_category_gets_its_own_scale():
    assert breakdown_maxima(NEW) == {"language": 50, "skills": 10, "experience": 10,
                                     "domain": 10, "role": 10, "requirements": 10}


def test_the_default_schema_is_all_twenties():
    assert breakdown_maxima(OLD) == {k: 20 for k in ("skills", "experience", "domain", "role", "requirements")}


def test_other_zero_to_n_ranges_are_not_read_as_categories():
    assert "scores" not in breakdown_maxima(NEW) and "keyword_coverage_pct" not in breakdown_maxima(NEW)


def test_no_breakdown_line_means_no_scales():
    assert breakdown_maxima('{"scores": {}}') == {}
    assert breakdown_maxima("") == {}
    assert breakdown_maxima(None) == {}

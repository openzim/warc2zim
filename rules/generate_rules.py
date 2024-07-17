import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment

rules_src = Path(__file__).with_name("rules.yaml")
if not rules_src.exists():
    # This skip is usefull mostly for CI operations when installing only Python deps
    print("Skipping rules generation, rule file is missing")
    sys.exit()

FUZZY_RULES = yaml.safe_load(rules_src.read_text())["fuzzyRules"]

for rule in FUZZY_RULES:
    if "name" not in rule:
        raise SystemExit("Fuzzy rule is missing a name")
    if "tests" not in rule or len(rule["tests"]) == 0:
        raise SystemExit("Fuzzy rule is missing test cases")


PY2JS_RULE_RX = re.compile(r"\\(\d)", re.ASCII)

# Do not escape anything, we want to generate code as-is, it won't be interpreted as
# HTML anyway
JINJA_ENV = Environment(autoescape=False)  # noqa: S701

### Generate Javascript code

js_code_template = """// THIS IS AN AUTOMATICALLY GENERATED FILE, DO NOT MODIFY DIRECTLY

export const fuzzyRules = [
{% for rule in FUZZY_RULES %}  {
    match: '{{ rule['match'] }}',
    replace: '{{ rule['replace'] }}',
  },
{% endfor %}
];

"""

js_parent = Path(__file__).joinpath("../../javascript/src").resolve()
if not js_parent.exists():
    # This skip is usefull mostly for CI operations when working on the Python part
    print("Skipping JS rules generation, target folder is missing")
else:
    (js_parent / "fuzzyRules.js").write_text(
        JINJA_ENV.from_string(js_code_template).render(
            FUZZY_RULES=[
                {
                    "match": rule["pattern"].replace("\\", "\\\\"),
                    "replace": PY2JS_RULE_RX.sub(r"$\1", rule["replace"]),
                }
                for rule in FUZZY_RULES
            ]
        )
    )
    print("JS rules generation completed successfully")

### Generate Javascript tests

js_test_template = """// THIS IS AN AUTOMATICALLY GENERATED FILE, DO NOT MODIFY DIRECTLY

import test from 'ava';

import { applyFuzzyRules } from '../src/wombatSetup.js';

{% for rule in FUZZY_RULES %}
{% for test in rule['tests'] %}
test('fuzzyrules_{{rule['name']}}_{{loop.index}}', (t) => {
  t.is(
    applyFuzzyRules(
      '{{test['raw_url']}}',
    ),
    '{{test['raw_url'] if test['unchanged'] else test['fuzzified_url']}}',
  );
});
{% endfor %}
{% endfor %}
"""

js_parent = Path(__file__).joinpath("../../javascript/test").resolve()
if not js_parent.exists():
    # This skip is usefull mostly for CI operations when working on the Python part
    print("Skipping JS tests generation, target folder is missing")
else:
    (js_parent / "fuzzyRules.js").write_text(
        JINJA_ENV.from_string(js_test_template).render(
            FUZZY_RULES=[
                {
                    "name": rule["name"],
                    "tests": rule["tests"],
                    "match": rule["pattern"].replace("\\", "\\\\"),
                    "replace": PY2JS_RULE_RX.sub(r"$\1", rule["replace"]),
                }
                for rule in FUZZY_RULES
            ]
        )
    )
    print("JS tests generation completed successfully")

### Generate Python code

py_code_template = """# THIS IS AN AUTOMATICALLY GENERATED FILE, DO NOT MODIFY DIRECTLY

FUZZY_RULES = [
{% for rule in FUZZY_RULES %}  {
    "pattern": r"{{ rule['pattern'] }}",
    "replace": r"{{ rule['replace'] }}",
  },
{% endfor %}
]
"""

py_parent = Path(__file__).joinpath("../../src/warc2zim").resolve()
if not py_parent.exists():
    # This skip is usefull mostly for CI operations when working on the JS part
    print("Skipping Python rules generation, target folder is missing")
else:
    (py_parent / "rules.py").absolute().write_text(
        JINJA_ENV.from_string(py_code_template).render(FUZZY_RULES=FUZZY_RULES)
    )
    print("Python rules generation completed successfully")

### Generate Python tests

py_test_template = """# THIS IS AN AUTOMATICALLY GENERATED FILE, DO NOT MODIFY DIRECTLY

import pytest

from warc2zim.url_rewriting import apply_fuzzy_rules

from .utils import ContentForTests

{% for rule in FUZZY_RULES %}
@pytest.fixture(
    params=[
{% for test in rule['tests'] %}
{% if test['unchanged'] %}
        ContentForTests(
            "{{ test['raw_url'] }}",
        ),
{% else %}
        ContentForTests(
            "{{ test['raw_url'] }}",
            "{{ test['fuzzified_url'] }}",
        ),
{% endif %}
{% endfor %}
    ]
)
def {{ rule['name'] }}_case(request):
    yield request.param


def test_fuzzyrules_{{ rule['name'] }}({{ rule['name'] }}_case):
    assert (
        apply_fuzzy_rules({{ rule['name'] }}_case.input_str)
        == {{ rule['name'] }}_case.expected_str
    )
{% endfor %}

"""

py_parent = Path(__file__).joinpath("../../tests").resolve()
if not py_parent.exists():
    # This skip is usefull mostly for CI operations when working on the JS part
    print("Skipping Python tests generation, target folder is missing")
else:
    (py_parent / "test_fuzzy_rules.py").absolute().write_text(
        JINJA_ENV.from_string(py_test_template).render(FUZZY_RULES=FUZZY_RULES)
    )
    print("Python tests generation completed successfully")

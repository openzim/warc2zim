import json
import re
import sys
from pathlib import Path

from jinja2 import Environment

rules_src = Path(__file__).with_name("rules.json")
if not rules_src.exists():
    # This skip is usefull mostly for CI operations when installing only Python deps
    print("Skipping rules generation, rule file is missing")
    sys.exit()

FUZZY_RULES = json.loads(rules_src.read_text())["fuzzyRules"]

PY2JS_RULE_RX = re.compile(r"\\(\d)", re.ASCII)

# Do not escape anything, we want to generate code as-is, it won't be interpreted as
# HTML anyway
JINJA_ENV = Environment(autoescape=False)  # noqa: S701

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

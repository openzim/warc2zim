import json
import re
from pathlib import Path

from jinja2 import Environment

FUZZY_RULES = json.loads((Path(__file__).parent / "rules.json").read_text())[
    "fuzzyRules"
]

PY2JS_RULE_RX = re.compile(r"\\(\d)", re.ASCII)

# Do not escape anything, we want to generate code as-is, it won't be interpreted as
# HTML anyway
JINJA_ENV = Environment(autoescape=False)  # noqa: S701

js_code_template = """// THIS IS AN AUTOMATICALLY GENERATED FILE, DO NOT MODIFY DIRECTLY

export const fuzzyRules = [
{% for rule in FUZZY_RULES %}  {
    match: "{{ rule['match'] }}",
    replace: "{{ rule['replace'] }}",
  },
{% endfor %}
];
"""

(
    Path(__file__).parent.parent / "javascript" / "src" / "fuzzyRules.js"
).absolute().write_text(
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

(Path(__file__).parent.parent / "src" / "warc2zim" / "rules.py").absolute().write_text(
    JINJA_ENV.from_string(py_code_template).render(FUZZY_RULES=FUZZY_RULES)
)

import re
import sys
from pathlib import Path

from warc2zim.constants import logger
from warc2zim.url_rewriting import ZimPath


def notify(_: ZimPath):
    pass


def main(path_to_log: str, regex_to_remove: str):
    """Print all lines of path_to_log not matching regex_to_remove"""

    content = Path(path_to_log)

    compiled_regex_to_remove = re.compile(regex_to_remove)
    with open(content) as fh:
        while line := fh.readline():
            if compiled_regex_to_remove.match(line):
                continue
            print(line[:-1])  # noqa: T201


if __name__ == "__main__":
    if len(sys.argv) < 2:  # noqa: PLR2004
        logger.error(
            "Incorrect number of arguments\n"
            f"Usage: {sys.argv[0]} <path_to_log> <regex_to_remove>\n"
        )
        sys.exit(1)

    args = sys.argv[1:]
    main(*args)

import tempfile

import pytest
from warcio.statusandheaders import StatusAndHeaders
from zimscraperlib.rewriting.url_rewriting import ZimPath

from warc2zim.converter import Converter
from warc2zim.main import _create_arguments_parser


@pytest.mark.parametrize(
    "inputs, warc_files",
    [
        pytest.param([], [], id="empty_array"),
        pytest.param(["foo.warc.gz"], ["foo.warc.gz"], id="one_file"),
        pytest.param(
            [
                "rec-f9c30d949953-20240724035746176-0.warc.gz",
                "rec-f9c30d949953-20240724045846176-0.warc.gz",
            ],
            None,  # no change
            id="two_already_sorted",
        ),
        pytest.param(
            [
                "rec-f9c30d949953-20240724045846176-0.warc.gz",
                "rec-f9c30d949953-20240724035746176-0.warc.gz",
            ],
            [
                "rec-f9c30d949953-20240724035746176-0.warc.gz",
                "rec-f9c30d949953-20240724045846176-0.warc.gz",
            ],
            id="two_not_sorted",
        ),
        pytest.param(
            [
                "aaaa/rec-f9c30d949953-20240724045846176-0.warc.gz",
                "bbb/rec-f9c30d949953-20240724035746176-0.warc.gz",
            ],
            [
                "bbb/rec-f9c30d949953-20240724035746176-0.warc.gz",
                "aaaa/rec-f9c30d949953-20240724045846176-0.warc.gz",
            ],
            id="two_not_sorted_in_random_unsorted_dirs",
        ),
    ],
)
def test_sort_warc_files(inputs, warc_files):
    parser = _create_arguments_parser()
    tmpdir = tempfile.mkdtemp()
    args = parser.parse_args(["--name", "foo", "--output", tmpdir])
    args.inputs = inputs
    conv = Converter(args)
    assert conv.warc_files == (warc_files if warc_files else inputs)


class _FakeRecord:
    def __init__(self, headers: list[tuple[str, str]] | None):
        self.http_headers = (
            StatusAndHeaders("200 OK", headers) if headers is not None else None
        )


@pytest.mark.parametrize(
    "path, mimetype, headers, expected",
    [
        pytest.param(
            "example.com/download?id=123",
            "application/pdf",
            [("Content-Disposition", 'attachment; filename="book.pdf"')],
            "example.com/download?id=123/book.pdf",
            id="appends_filename",
        ),
        pytest.param(
            "example.com/download/book.pdf",
            "application/pdf",
            [("Content-Disposition", 'attachment; filename="book.pdf"')],
            None,
            id="already_ends_with_filename",
        ),
        pytest.param(
            "example.com/index.html",
            "text/html",
            [("Content-Disposition", 'attachment; filename="index.html"')],
            None,
            id="ignores_text",
        ),
        pytest.param(
            "example.com/script.js",
            "application/javascript",
            [("Content-Disposition", 'attachment; filename="script.js"')],
            None,
            id="ignores_javascript",
        ),
        pytest.param(
            "example.com/data.json",
            "application/json",
            [("Content-Disposition", 'attachment; filename="data.json"')],
            None,
            id="ignores_json",
        ),
        pytest.param(
            "example.com/download?id=123",
            "application/pdf",
            None,
            None,
            id="no_headers",
        ),
    ],
)
def test_get_download_zim_path(path, mimetype, headers, expected):
    record = _FakeRecord(headers)
    result = Converter.get_download_zim_path(record, ZimPath(path), mimetype)  # pyright: ignore[reportArgumentType]
    assert result == (ZimPath(expected) if expected else None)

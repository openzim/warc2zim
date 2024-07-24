import tempfile

import pytest

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

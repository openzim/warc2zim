import pytest

from warc2zim.main import main


@pytest.mark.parametrize(
    "title, is_valid",
    [
        pytest.param("A title", True, id="a_valid_title"),
        pytest.param("A very very very very long title", False, id="an_invalid_title"),
    ],
)
def test_title_validation(title, is_valid):
    args = ["--name", "test", "--title", title, "--output", "./"]
    if is_valid:
        assert main(args) == 100
    else:
        with pytest.raises(ValueError, match="Title is too long"):
            main(args)


@pytest.mark.parametrize(
    "description, is_valid",
    [
        pytest.param("A description", True, id="a_valid_description"),
        pytest.param(
            "A " + "".join(["very " for i in range(20)]) + "long description",
            False,
            id="an_invalid_description",
        ),
    ],
)
def test_description_validation(description, is_valid):
    args = ["--name", "test", "--description", description, "--output", "./"]
    if is_valid:
        assert main(args) == 100
    else:
        with pytest.raises(ValueError, match="Description is too long"):
            main(args)


@pytest.mark.parametrize(
    "long_description, is_valid",
    [
        pytest.param("A long description", True, id="a_valid_long_description"),
        pytest.param(
            "A " + "".join(["very " for i in range(800)]) + "long description",
            False,
            id="an_invalid_long_description",
        ),
    ],
)
def test_long_description_validation(long_description, is_valid):
    args = [
        "--name",
        "test",
        "--long-description",
        long_description,
        "--output",
        "./",
    ]
    if is_valid:
        assert main(args) == 100
    else:
        with pytest.raises(ValueError, match="Description is too long"):
            main(args)


@pytest.mark.parametrize(
    "tags, is_valid",
    [
        pytest.param(["tag1", "tag2"], True, id="valid_tags"),
        # NOTA: there is no tests for invalid tags, since it is not currently possible
    ],
)
def test_tags_validation(tags, is_valid):
    args = ["--name", "test", "--tags", ";".join(tags), "--output", "./"]
    if is_valid:
        assert main(args) == 100

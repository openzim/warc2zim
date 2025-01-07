import os

ALLOWED_EXT = (".arc", ".arc.gz", ".warc", ".warc.gz")


# =================================================================
def iter_file_or_dir(inputs: list[str]):
    for input_ in inputs:
        if not isinstance(input_, str) or not os.path.isdir(input_):
            yield input_
            continue

        for root, _, files in os.walk(input_):
            for filename in files:
                if filename.endswith(ALLOWED_EXT):
                    full_path = os.path.join(root, filename)
                    yield full_path

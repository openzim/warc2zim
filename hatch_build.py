import urllib.request
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

root_dir = Path(__file__).parent

WOMBAT_SOURCE_URL = "https://cdn.jsdelivr.net/npm/@webrecorder/wombat@3.7.0/dist/"


class GetJsDepsHook(BuildHookInterface):
    def initialize(self, version, build_data):
        self.download_wombat("wombat.js")
        return super().initialize(version, build_data)

    def download_wombat(self, name):
        print("Downloading " + WOMBAT_SOURCE_URL + name)  # noqa: T201
        with urllib.request.urlopen(  # nosec # noqa: S310
            WOMBAT_SOURCE_URL + name
        ) as response:
            root_dir.joinpath("src", "warc2zim", "statics").mkdir(
                parents=True, exist_ok=True
            )
            with open(
                root_dir.joinpath("src", "warc2zim", "statics", name), "wb"
            ) as fh:
                fh.write(response.read())

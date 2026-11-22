from zimscraperlib.logging import getLogger

# Shared logger with default log level at this stage
logger = getLogger("warc2zim")

# MIME types handled by the HTML rewriter
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")

# Unambiguous binary MIME types that can safely override bad server headers
ALLOWED_OVERRIDE_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

# Defaults for mandatory ZIM metadata fields.
DEFAULT_NAME = "warc2zim"
DEFAULT_TITLE = "Untitled"
DEFAULT_DESCRIPTION = "-"
DEFAULT_CREATOR = "-"
DEFAULT_PUBLISHER = "openZIM"

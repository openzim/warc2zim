from zimscraperlib.logging import getLogger

# Shared logger with default log level at this stage
logger = getLogger("warc2zim")

# MIME types handled by the HTML rewriter
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")

import base64
import json
import sys

from urllib.parse import unquote_plus, urlencode
from io import BytesIO

from multipart import MultipartParser
from warcio.utils import to_native_str

from cdxj_indexer.amf import amf_parse


MAX_QUERY_LENGTH = 4096


# ============================================================================
def append_method_query_from_req_resp(req, resp):
    len_ = req.http_headers.get_header("Content-Length")
    content_type = req.http_headers.get_header("Content-Type")
    stream = req.buffered_stream
    stream.seek(0)

    url = req.rec_headers.get_header("WARC-Target-URI")
    method = req.http_headers.protocol
    return append_method_query(method, content_type, len_, stream, url)


# ============================================================================
def append_method_query(method, content_type, len_, stream, url):
    # if method == 'GET':
    #    return '', ''

    if method == "POST" or method == "PUT":
        query = query_extract(content_type, len_, stream, url)
    else:
        query = ""

    if "?" not in url:
        append_str = "?"
    else:
        append_str = "&"

    append_str += "__wb_method=" + method
    if query:
        append_str += "&" + query

    return query, append_str


# ============================================================================
def query_extract(mime, length, stream, url):
    """
    Extract a url-encoded form POST/PUT from stream
    content length, return None
    Attempt to decode application/x-www-form-urlencoded or multipart/*,
    otherwise read whole block and b64encode
    """
    query_data = b""

    try:
        length = int(length)
    except (ValueError, TypeError):
        if length is None:
            length = 8192
        else:
            return

    while length > 0:
        buff = stream.read(length)

        length -= len(buff)

        if not buff:
            break

        query_data += buff

    if not mime:
        mime = ""

    query = ""

    def handle_binary(query_data):
        query = base64.b64encode(query_data)
        query = to_native_str(query)
        query = "__wb_post_data=" + query
        return query

    if mime.startswith("application/x-www-form-urlencoded"):
        try:
            query = to_native_str(query_data.decode("utf-8"))
            query = unquote_plus(query)
        except UnicodeDecodeError:
            query = handle_binary(query_data)

    elif mime.startswith("multipart/"):
        try:
            boundary = mime.split("boundary=")[1]
            parser = MultipartParser(BytesIO(query_data), boundary, charset="utf8")
        except (ValueError, IndexError):
            # Content-Type multipart/form-data may lack "boundary" info
            query = handle_binary(query_data)
        else:
            values = []
            for part in parser:
                values.append((part.name, part.value))

            query = urlencode(values, True)

    elif mime.startswith("application/json"):
        try:
            query = json_parse(query_data)
        except Exception as e:
            if query_data:
                try:
                    sys.stderr.write(
                        "Error parsing: " + query_data.decode("utf-8") + "\n"
                    )
                except:
                    pass

            query = ""

    elif mime.startswith("text/plain"):
        try:
            query = json_parse(query_data)
        except Exception as e:
            query = handle_binary(query_data)

    elif mime.startswith("application/x-amf"):
        query = amf_parse(query_data)
    else:
        query = handle_binary(query_data)

    if query:
        query = query[:MAX_QUERY_LENGTH]

    return query


def json_parse(string):
    data = {}
    dupes = {}

    def get_key(n):
        if n not in data:
            return n

        if n not in dupes:
            dupes[n] = 1

        dupes[n] += 1
        return n + "." + str(dupes[n]) + "_"

    def _parser(json_obj, name=""):
        if isinstance(json_obj, dict):
            for n, v in json_obj.items():
                _parser(v, n)

        elif isinstance(json_obj, list):
            for v in json_obj:
                _parser(v, name)

        elif name:
            data[get_key(name)] = str(json_obj)

    try:
        _parser(json.loads(string))
    except json.decoder.JSONDecodeError:
        if b"\n" in string:
            for line in string.split(b"\n"):
                _parser(json.loads(line))
        else:
            raise

    return urlencode(data)

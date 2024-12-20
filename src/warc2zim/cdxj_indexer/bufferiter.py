import hashlib
import shutil
import tempfile

from cdxj_indexer.postquery import append_method_query_from_req_resp


BUFF_SIZE = 1024 * 64


# ============================================================================
def buffering_record_iter(
    record_iter, post_append=False, digest_reader=None, url_key_func=None
):
    prev_record = None

    for record in record_iter:
        buffer_record_content(record)

        record.file_offset = record_iter.get_record_offset()
        record.file_length = record_iter.get_record_length()

        if digest_reader:
            curr = digest_reader.tell()
            digest_reader.seek(record.file_offset)
            record_digest, digest_length = digest_block(
                digest_reader, record.file_length
            )
            digest_reader.seek(curr)

            if digest_length != record.file_length:
                raise Exception(
                    "Digest block mismatch, expected {0}, got {1}".format(
                        record.file_length,
                        digest_length,
                    )
                )

            record.record_digest = record_digest

        req, resp = concur_req_resp(prev_record, record)

        if not req or not resp:
            if prev_record:
                yield prev_record
                prev_record.buffered_stream.close()
            prev_record = record
            continue

        join_req_resp(req, resp, post_append, url_key_func)

        yield prev_record
        prev_record.buffered_stream.close()
        yield record
        record.buffered_stream.close()
        prev_record = None

    if prev_record:
        yield prev_record
        prev_record.buffered_stream.close()


# ============================================================================
def concur_req_resp(rec_1, rec_2):
    if not rec_1 or not rec_2:
        return None, None

    if rec_1.rec_headers.get_header("WARC-Target-URI") != rec_2.rec_headers.get_header(
        "WARC-Target-URI"
    ):
        return None, None

    if rec_2.rec_headers.get_header(
        "WARC-Concurrent-To"
    ) != rec_1.rec_headers.get_header("WARC-Record-ID"):
        return None, None

    if rec_1.rec_type == "response" and rec_2.rec_type == "request":
        req = rec_2
        resp = rec_1

    elif rec_1.rec_type == "request" and rec_2.rec_type == "response":
        req = rec_1
        resp = rec_2

    else:
        return None, None

    return req, resp


# ============================================================================
def buffer_record_content(record):
    spool = tempfile.SpooledTemporaryFile(BUFF_SIZE)
    shutil.copyfileobj(record.content_stream(), spool)
    spool.seek(0)
    record.buffered_stream = spool


# ============================================================================
def join_req_resp(req, resp, post_append, url_key_func=None):
    if req.http_headers is None:
        return

    resp.req = req

    method = req.http_headers.protocol
    if post_append and method.upper() in ("POST", "PUT"):
        url = req.rec_headers.get_header("WARC-Target-URI")
        query, append_str = append_method_query_from_req_resp(req, resp)
        resp.method = method.upper()
        resp.requestBody = query
        resp.urlkey = url + append_str
        if url_key_func:
            resp.urlkey = url_key_func(resp.urlkey)
        req.urlkey = resp.urlkey


# ============================================================================
def digest_block(reader, length):
    count = 0
    hasher = hashlib.sha256()

    while length > 0:
        buff = reader.read(min(BUFF_SIZE, length))
        if not buff:
            break
        hasher.update(buff)
        length -= len(buff)
        count += len(buff)

    return "sha256:" + hasher.hexdigest(), count

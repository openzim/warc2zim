from io import BytesIO

from pyamf import AMF3
from pyamf.remoting import Request, Envelope, encode

from cdxj_indexer.postquery import append_method_query
from cdxj_indexer.amf import amf_parse


# ============================================================================
class MethodQueryCanonicalizer:
    def __init__(self, method, content_type, req_len, req_stream):
        self.method = method
        self.content_type = content_type
        self.req_len = req_len
        self.req_stream = req_stream

    def append_query(self, url):
        self.req_stream.seek(0)
        query_only, full_string = append_method_query(
            self.method, self.content_type, self.req_len, self.req_stream, url
        )
        return url + full_string


# ============================================================================
class TestPostQueryExtract(object):
    @classmethod
    def setup_class(cls):
        cls.post_data = b"foo=bar&dir=%2Fbaz"
        cls.binary_post_data = (
            b"\x816l`L\xa04P\x0e\xe0r\x02\xb5\x89\x19\x00fP\xdb\x0e\xb0\x02,"
        )

    def test_post_extract_1(self):
        mq = MethodQueryCanonicalizer(
            "POST",
            "application/x-www-form-urlencoded",
            len(self.post_data),
            BytesIO(self.post_data),
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&foo=bar&dir=/baz"
        )

        assert (
            mq.append_query("http://example.com/?123=ABC")
            == "http://example.com/?123=ABC&__wb_method=POST&foo=bar&dir=/baz"
        )

    def test_post_extract_json(self):
        post_data = b'{"a": "b", "c": {"a": 2}, "d": "e"}'
        mq = MethodQueryCanonicalizer(
            "POST", "application/json", len(post_data), BytesIO(post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&a=b&a.2_=2&d=e"
        )

    def test_post_extract_json_top_list(self):
        post_data = (
            b'[{"a": "b", "c": {"a": 2}}, {"d": "e"}, "ignored", false, null, 0]'
        )
        mq = MethodQueryCanonicalizer(
            "POST", "application/json", len(post_data), BytesIO(post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&a=b&a.2_=2&d=e"
        )

    def test_post_extract_json_lines(self):
        post_data = b'{"a": "b"}\n{"c": {"a": 2}, "d": "e"}'
        mq = MethodQueryCanonicalizer(
            "POST", "application/json", len(post_data), BytesIO(post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&a=b&a.2_=2&d=e"
        )

    def test_put_extract_method(self):
        mq = MethodQueryCanonicalizer(
            "PUT",
            "application/x-www-form-urlencoded",
            len(self.post_data),
            BytesIO(self.post_data),
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=PUT&foo=bar&dir=/baz"
        )

    def test_post_extract_non_form_data_1(self):
        mq = MethodQueryCanonicalizer(
            "POST",
            "application/octet-stream",
            len(self.post_data),
            BytesIO(self.post_data),
        )

        # base64 encoded data
        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&__wb_post_data=Zm9vPWJhciZkaXI9JTJGYmF6"
        )

    def test_post_extract_non_form_data_2(self):
        mq = MethodQueryCanonicalizer(
            "POST", "text/plain", len(self.post_data), BytesIO(self.post_data)
        )

        # base64 encoded data
        assert (
            mq.append_query("http://example.com/pathbar?id=123")
            == "http://example.com/pathbar?id=123&__wb_method=POST&__wb_post_data=Zm9vPWJhciZkaXI9JTJGYmF6"
        )

    def test_post_extract_length_invalid_ignore(self):
        mq = MethodQueryCanonicalizer(
            "POST", "application/x-www-form-urlencoded", 0, BytesIO(self.post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST"
        )

        mq = MethodQueryCanonicalizer(
            "POST", "application/x-www-form-urlencoded", "abc", BytesIO(self.post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST"
        )

    def test_post_extract_length_too_short(self):
        mq = MethodQueryCanonicalizer(
            "POST",
            "application/x-www-form-urlencoded",
            len(self.post_data) - 4,
            BytesIO(self.post_data),
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&foo=bar&dir=%2"
        )

    def test_post_extract_length_too_long(self):
        mq = MethodQueryCanonicalizer(
            "POST",
            "application/x-www-form-urlencoded",
            len(self.post_data) + 4,
            BytesIO(self.post_data),
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&foo=bar&dir=/baz"
        )

    def test_post_extract_malformed_form_data(self):
        mq = MethodQueryCanonicalizer(
            "POST",
            "application/x-www-form-urlencoded",
            len(self.binary_post_data),
            BytesIO(self.binary_post_data),
        )

        # base64 encoded data
        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&__wb_post_data=gTZsYEygNFAO4HICtYkZAGZQ2w6wAiw="
        )

    def test_post_extract_no_boundary_in_multipart_form_mimetype(self):
        mq = MethodQueryCanonicalizer(
            "POST", "multipart/form-data", len(self.post_data), BytesIO(self.post_data)
        )

        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=POST&__wb_post_data=Zm9vPWJhciZkaXI9JTJGYmF6"
        )

    def test_options(self):
        mq = MethodQueryCanonicalizer("OPTIONS", "", 0, BytesIO())
        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=OPTIONS"
        )

    def test_head(self):
        mq = MethodQueryCanonicalizer("HEAD", "", 0, BytesIO())
        assert (
            mq.append_query("http://example.com/")
            == "http://example.com/?__wb_method=HEAD"
        )

    def test_amf_parse(self):
        mq = MethodQueryCanonicalizer("POST", "application/x-amf", 0, BytesIO())

        req = Request(target="t", body="")
        ev_1 = Envelope(AMF3)
        ev_1["/0"] = req

        req = Request(target="t", body="alt_content")
        ev_2 = Envelope(AMF3)
        ev_2["/0"] = req

        assert amf_parse(encode(ev_1).getvalue()) != amf_parse(encode(ev_2).getvalue())

from aptly_ctl.exceptions import AptlyApiError


class TestAptlyApiError:
    def test_empty_body(self):
        exc = AptlyApiError(404)
        assert exc.status == 404
        assert not exc.msg
        assert not exc.errors
        assert str(exc) == "404 Not Found"

    def test_unexpected_body(self):
        for body, error in [
            (b"Some error", "400 Bad Request: Some error"),
            (b'{"key": "value"}', '400 Bad Request: {"key": "value"}'),
            (b'["some error"]', '400 Bad Request: ["some error"]'),
        ]:
            exc = AptlyApiError(400, body)
            assert exc.status == 400
            assert exc.msg == body.decode("utf-8")
            assert not exc.errors
            assert str(exc) == error

    def test_json_single_error(self):
        error = b'{"error": "Some error", "meta": "some description"}'
        for body in [error, b"[" + error + b"]"]:
            exc = AptlyApiError(404, body)
            assert exc.status == 404
            assert exc.msg == body.decode("utf-8")
            assert len(exc.errors) == 1
            assert str(exc) == "Some error (some description)"

    def test_json_multiple_errors(self):
        body = b"""[
        {"error": "Some error 1", "meta": "some description 1"},
        {"error": "Some error 2"}
        ]"""
        exc = AptlyApiError(400, body)
        assert exc.status == 400
        assert exc.msg == body.decode("utf-8")
        assert len(exc.errors) == 2
        assert (
            str(exc)
            == "Multiple errors: Some error 1 (some description 1); Some error 2"
        )

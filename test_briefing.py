import io
import json
import unittest
from unittest import mock
import urllib.error

import briefing


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class CallLlmTests(unittest.TestCase):
    def test_retries_rate_limit_then_succeeds(self):
        response = {
            "choices": [{"message": {"content": "digest"}}],
        }
        rate_limited = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "7"},
            fp=io.BytesIO(b"slow down"),
        )

        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with mock.patch(
                "briefing.urllib.request.urlopen",
                side_effect=[rate_limited, FakeResponse(response)],
            ) as urlopen:
                with mock.patch("briefing.time.sleep") as sleep:
                    result = briefing.call_llm("system", "user")

        self.assertEqual(result, "digest")
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(7.0)

    def test_raises_after_retry_budget_exhausted(self):
        rate_limited = urllib.error.HTTPError(
            url="https://openrouter.ai/api/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b"still limited"),
        )

        with mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            with mock.patch(
                "briefing.urllib.request.urlopen",
                side_effect=[rate_limited] * (briefing.OPENROUTER_MAX_RETRIES + 1),
            ):
                with mock.patch("briefing.time.sleep"):
                    with self.assertRaises(RuntimeError) as ctx:
                        briefing.call_llm("system", "user")

        self.assertIn("OpenRouter 429", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

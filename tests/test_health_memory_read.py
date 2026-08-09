import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import health_memory_read  # noqa: E402


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class HealthMemoryReadTests(unittest.TestCase):
    def setUp(self):
        self.config = health_memory_read.HealthMemoryConfig(
            base_url="https://kinelo.example",
            api_token="test-secret-placeholder",
            service_account_id="svc-hermes",
            organization_id="org-1",
            subject_person_id="person-1",
            runtime="hermes",
        )

    def test_build_request_is_memory_read_only(self):
        request = health_memory_read.build_request(self.config, 99, "req-1")

        self.assertEqual(request["domain"], "memory")
        self.assertEqual(request["limit"], 20)
        self.assertEqual(request["context"]["scopes"], ["memory:read"])
        self.assertEqual(request["provenance"]["requestId"], "req-1")

    def test_redact_request_removes_identifiers(self):
        request = health_memory_read.build_request(self.config, 5, "req-2")

        redacted = health_memory_read.redact_request(request)

        self.assertEqual(redacted["subjectPersonId"], "<subject>")
        self.assertEqual(redacted["context"]["organizationId"], "<organization>")
        self.assertNotIn("secret-not-for-output", json.dumps(redacted))

    @patch.object(health_memory_read.urllib.request, "urlopen")
    def test_fetch_context_returns_contract(self, urlopen):
        urlopen.return_value = FakeResponse(
            {
                "success": True,
                "data": {
                    "context": {
                        "schemaVersion": "health-memory-context.v1",
                        "items": [],
                    }
                },
            }
        )

        context = health_memory_read.fetch_context(
            self.config,
            health_memory_read.build_request(self.config, 5, "req-3"),
        )

        self.assertEqual(context["schemaVersion"], "health-memory-context.v1")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://kinelo.example/api/kernel/v0")
        self.assertEqual(request.get_header("X-hermes-api-key"), "test-secret-placeholder")


if __name__ == "__main__":
    unittest.main()

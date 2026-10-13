import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test")

from gtm_agent import gtm_agent as engine


class SendProspectEmailTests(unittest.TestCase):
    def send_email(self, prospect, runtime=None):
        return engine.send_prospect_email.func(
            prospect=prospect,
            subject="An introduction",
            body="Let's connect.",
            runtime=runtime or SimpleNamespace(config={"metadata": {}}),
            from_rep={"name": "Sales Rep", "email": "rep@example.com"},
        )

    def test_blocks_disqualified_source_record(self):
        with patch.object(engine.data_service, "get_prospect_record", return_value={"disqualified": True}):
            result = self.send_email({"prospect_id": "LEAD-50003", "email": "lead@example.com"})

        self.assertEqual(
            result,
            {"status": "blocked", "error": "Prospect is disqualified; email not sent."},
        )

    def test_blocks_missing_source_record(self):
        with patch.object(engine.data_service, "get_prospect_record", return_value=None):
            result = self.send_email({"prospect_id": "LEAD-MISSING", "email": "lead@example.com"})

        self.assertEqual(
            result,
            {"status": "blocked", "error": "Prospect record not found; email not sent."},
        )

    def test_sends_for_eligible_source_record(self):
        with patch.object(engine.data_service, "get_prospect_record", return_value={"disqualified": False}):
            result = self.send_email({"prospect_id": "LEAD-12853", "email": "lead@example.com"})

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["to"], "lead@example.com")

    def test_request_to_email_disqualified_prospect_is_blocked_and_explained(self):
        tool_results = []

        def invoke(inputs, config):
            self.assertIn("Email LEAD-50003", inputs["messages"][0]["content"])
            self.assertIn("plainly explain that to the rep", engine.SYSTEM_PROMPT)
            result = engine.send_prospect_email.func(
                prospect={
                    "prospect_id": "LEAD-50003",
                    "name": "Disqualified Prospect",
                    "email": "lead@example.com",
                },
                subject="Pricing deck",
                body="Here is our pricing deck.",
                runtime=SimpleNamespace(config=config),
                from_rep={"name": "Sales Rep", "email": "rep@example.com"},
            )
            tool_results.append(result)
            reply = "I couldn't send the email because this prospect is disqualified."
            return {"messages": [SimpleNamespace(content=reply)]}

        with patch.object(engine.gtm_agent, "invoke", side_effect=invoke):
            result = engine.run_agent("Email LEAD-50003 to send over our pricing deck.", user_id="rep_sbrown")

        self.assertEqual(tool_results, [{"status": "blocked", "error": "Prospect is disqualified; email not sent."}])
        self.assertNotIn('"status": "sent"', json.dumps(tool_results))
        self.assertIn("disqualified", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()

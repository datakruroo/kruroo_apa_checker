import os
from unittest import TestCase
from unittest.mock import patch

import config


class LlmProviderConfigTests(TestCase):
    def test_openai_provider_keeps_existing_defaults(self):
        env = {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "openai-test-key",
            "OPENAI_MODEL": "gpt-test",
            "REPORT_WRITER_MODEL": "gpt-report-test",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "openrouter/model",
            "OPENROUTER_REPORT_WRITER_MODEL": "openrouter/report-model",
        }

        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(config.get_llm_provider(), "openai")
            self.assertEqual(config.get_llm_key(), "openai-test-key")
            self.assertEqual(config.get_model(), "gpt-test")
            self.assertEqual(config.get_report_writer_model(), "gpt-report-test")

    def test_openrouter_provider_uses_openrouter_key_and_models(self):
        env = {
            "LLM_PROVIDER": "openrouter",
            "OPENAI_API_KEY": "openai-test-key",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
            "OPENROUTER_MODEL": "anthropic/claude-test",
            "OPENROUTER_REPORT_WRITER_MODEL": "google/gemini-test",
        }

        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(config.get_llm_provider(), "openrouter")
            self.assertEqual(config.get_llm_key(), "openrouter-test-key")
            self.assertEqual(config.get_model(), "anthropic/claude-test")
            self.assertEqual(config.get_report_writer_model(), "google/gemini-test")

            client = config.create_llm_client()
            self.assertEqual(str(client.base_url), "https://openrouter.ai/api/v1/")

    def test_openrouter_report_writer_model_falls_back_to_openrouter_model(self):
        env = {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "openrouter-test-key",
            "OPENROUTER_MODEL": "openai/gpt-test",
            "OPENROUTER_REPORT_WRITER_MODEL": "",
        }

        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(config.get_report_writer_model(), "openai/gpt-test")

    def test_unknown_provider_falls_back_to_openai(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown"}, clear=False):
            self.assertEqual(config.get_llm_provider(), "openai")

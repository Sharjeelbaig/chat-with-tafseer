import unittest
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from agent.graph import SESSION_MESSAGE_LIMIT, tafseer_agent
from agent.nodes import invoke_llm
from main import app


def build_ayah_response(resource_id=169, verse_key="1:1", text="<p>Sample tafseer text</p>"):
    return {
        "tafsir": {
            "resource_id": resource_id,
            "resource_name": "Ibn Kathir (Abridged)",
            "language_id": 38,
            "slug": "en-tafisr-ibn-kathir",
            "translated_name": {"name": "Ibn Kathir (Abridged)", "language_name": "english"},
            "verses": {verse_key: {"id": 1}},
            "text": text,
        }
    }


class BaseEndpointTestCase(unittest.TestCase):
    def setUp(self):
        tafseer_agent.reset()
        self.client = TestClient(app)


class GetTafseerTests(BaseEndpointTestCase):
    @patch("services.quran_service.requests.get")
    def test_get_tafseer_success(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"tafsirs": [{"verse_key": "1:1", "text": "Sample"}]}
        mock_get.return_value = mock_response

        response = self.client.get("/tafseer/169/chapter/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tafsirs"][0]["verse_key"], "1:1")
        mock_get.assert_called_once_with(
            "https://api.quran.com/api/v4/tafsirs/169/by_chapter/1",
            params={},
            timeout=15,
        )

    @patch("services.quran_service.requests.get")
    def test_get_tafseer_missing_resource_returns_404(self, mock_get):
        mock_response = Mock(status_code=404)
        mock_response.json.return_value = {"status": 404, "error": "Tafsir not found"}
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        response = self.client.get("/tafseer/999999/chapter/1")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Tafsir not found")

    @patch("services.quran_service.requests.get")
    def test_get_tafseer_invalid_chapter_returns_404(self, mock_get):
        mock_response = Mock(status_code=404)
        mock_response.json.return_value = {
            "status": 404,
            "error": "Surah number or slug is invalid. Please select valid slug or surah number from 1-114.",
        }
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        response = self.client.get("/tafseer/169/chapter/999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "Surah number or slug is invalid. Please select valid slug or surah number from 1-114.",
        )

    @patch("services.quran_service.requests.get")
    def test_get_tafseer_upstream_failure_returns_502(self, mock_get):
        mock_get.side_effect = requests.RequestException("connection failed")

        response = self.client.get("/tafseer/169/chapter/1")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Failed to fetch tafseer data from upstream Quran API")

    @patch("services.quran_service.requests.get")
    def test_get_tafseer_non_404_http_error_returns_502(self, mock_get):
        mock_response = Mock(status_code=500)
        mock_response.json.return_value = {"status": 500, "message": "Internal upstream error"}
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        response = self.client.get("/tafseer/169/chapter/1")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Internal upstream error")


class DocsRoutesTests(BaseEndpointTestCase):
    def test_root_serves_docs_overview_html(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Chat with Tafseer", response.text)
        self.assertIn("Build verse-grounded tafseer experiences", response.text)

    def test_send_message_page_serves_html(self):
        response = self.client.get("/send_message.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Send a verse-grounded tafseer message.", response.text)

    def test_resource_ids_page_serves_html(self):
        response = self.client.get("/resource_ids.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Tafseer Resource IDs", response.text)

    def test_verse_keys_page_serves_html(self):
        response = self.client.get("/verse_keys.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Verse Key Guide", response.text)

    def test_docs_stylesheet_is_served(self):
        response = self.client.get("/assets/styles/docs.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.headers["content-type"])
        self.assertIn("IBM Plex Sans", response.text)

    def test_llms_txt_is_served(self):
        response = self.client.get("/llms.txt")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        self.assertIn("POST /chat", response.text)


class ChatEndpointTests(BaseEndpointTestCase):
    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_chat_success_returns_explicit_verse_response(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response(text="<p>Hello <strong>world</strong></p>")
        mock_llm_invoke.return_value = Mock(content="It says hello world.")

        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "chat-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "It says hello world.",
                "resource_id": 169,
                "verse_key": "1:1",
                "chapter_number": 1,
            },
        )
        mock_get_tafseer.assert_called_once_with(169, "1:1")

    def test_chat_requires_explicit_resource_and_verse(self):
        response = self.client.post("/chat", json={"message": "What does it say?"})

        self.assertEqual(response.status_code, 422)

    def test_chat_rejects_invalid_verse_key_format(self):
        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "invalid", "message": "What does it say?", "thread_id": "chat-2"},
        )

        self.assertEqual(response.status_code, 422)

    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_chat_surfaces_upstream_404(self, mock_get_tafseer):
        mock_response = Mock(status_code=404)
        mock_response.json.return_value = {"status": 404, "error": "Tafsir not found"}
        mock_get_tafseer.side_effect = requests.HTTPError(response=mock_response)

        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "chat-3"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Tafsir not found")

    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_chat_surfaces_quran_transport_failure(self, mock_get_tafseer):
        mock_get_tafseer.side_effect = requests.RequestException("connection failed")

        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "chat-4"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Failed to fetch tafseer data from upstream Quran API")

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_chat_surfaces_model_unavailable_as_503(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response()
        mock_llm_invoke.side_effect = RuntimeError("model 'qwen2.5:3b' not found, try pulling it first")

        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "chat-5"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Configured Ollama model is unavailable")

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_same_thread_same_verse_reuses_cached_tafseer(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response(text="<p>Context one</p>")
        mock_llm_invoke.side_effect = [Mock(content="Answer one"), Mock(content="Answer two")]

        first = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "same-verse"},
        )
        second = self.client.post(
            "/chat",
            json={
                "resource_id": 169,
                "verse_key": "1:1",
                "message": "Can you summarize that?",
                "thread_id": "same-verse",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(mock_get_tafseer.call_count, 1)
        self.assertEqual(mock_llm_invoke.call_count, 2)
        second_call_messages = mock_llm_invoke.call_args_list[1].args[0]
        self.assertEqual(len(second_call_messages), 2)
        self.assertIn("User: What does it say?", second_call_messages[0].content)
        self.assertIn("Assistant: Answer one", second_call_messages[0].content)
        self.assertEqual(second_call_messages[1].content, "Can you summarize that?")

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_same_thread_follow_up_keeps_older_question_in_system_context(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response(text="<p>Context one</p>")
        mock_llm_invoke.side_effect = [
            Mock(content="Answer one"),
            Mock(content="Answer two"),
            Mock(content="Answer three"),
            Mock(content="Answer four"),
            Mock(content="Answer five"),
        ]

        responses = []
        for message in [
            "First question",
            "Second question",
            "Third question",
            "Fourth question",
            "What was my first question?",
        ]:
            responses.append(
                self.client.post(
                    "/chat",
                    json={"resource_id": 169, "verse_key": "1:1", "message": message, "thread_id": "long-thread"},
                )
            )

        self.assertTrue(all(response.status_code == 200 for response in responses))
        fifth_call_messages = mock_llm_invoke.call_args_list[4].args[0]
        self.assertEqual(len(fifth_call_messages), 2)
        self.assertIn("User: First question", fifth_call_messages[0].content)
        self.assertIn("Assistant: Answer four", fifth_call_messages[0].content)
        self.assertEqual(fifth_call_messages[1].content, "What was my first question?")

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_same_thread_different_verse_resets_context(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.side_effect = [
            build_ayah_response(verse_key="1:1", text="<p>First verse context</p>"),
            build_ayah_response(verse_key="1:2", text="<p>Second verse context</p>"),
        ]
        mock_llm_invoke.side_effect = [Mock(content="Answer one"), Mock(content="Answer two")]

        first = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "switch-verse"},
        )
        second = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:2", "message": "And this verse?", "thread_id": "switch-verse"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(mock_get_tafseer.call_count, 2)
        second_call_messages = mock_llm_invoke.call_args_list[1].args[0]
        self.assertEqual(len(second_call_messages), 2)
        self.assertIn("Second verse context", second_call_messages[0].content)
        self.assertNotIn("First verse context", second_call_messages[0].content)
        self.assertNotIn("What does it say?", second_call_messages[0].content)

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_same_thread_session_history_is_pruned(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response(text="<p>Context one</p>")
        mock_llm_invoke.side_effect = [Mock(content=f"Answer {index}") for index in range(1, 21)]

        for index in range(1, 21):
            response = self.client.post(
                "/chat",
                json={
                    "resource_id": 169,
                    "verse_key": "1:1",
                    "message": f"Question {index}",
                    "thread_id": "pruned-thread",
                },
            )
            self.assertEqual(response.status_code, 200)

        self.assertLessEqual(len(tafseer_agent._sessions["pruned-thread"]["messages"]), SESSION_MESSAGE_LIMIT)

    @patch("agent.nodes.invoke_llm")
    @patch("agent.nodes.quran_service.get_tafseer_by_ayah")
    def test_chat_prompt_uses_cleaned_tafseer_text(self, mock_get_tafseer, mock_llm_invoke):
        mock_get_tafseer.return_value = build_ayah_response(text="<h1>Title</h1><p>Hello <strong>world</strong></p>")
        mock_llm_invoke.return_value = Mock(content="It says hello world.")

        response = self.client.post(
            "/chat",
            json={"resource_id": 169, "verse_key": "1:1", "message": "What does it say?", "thread_id": "clean-text"},
        )

        self.assertEqual(response.status_code, 200)
        system_message = mock_llm_invoke.call_args.args[0][0]
        self.assertIn("Title Hello world", system_message.content)
        self.assertNotIn("<h1>", system_message.content)
        self.assertNotIn("<strong>", system_message.content)


class ModelInvocationTests(unittest.TestCase):
    @patch("agent.nodes.llm")
    def test_invoke_llm_retries_transient_bad_gateway(self, mock_llm):
        mock_llm.invoke.side_effect = [RuntimeError("502 Bad Gateway"), Mock(content="Recovered answer")]

        response = invoke_llm([HumanMessage(content="What does it say?")])

        self.assertEqual(response.content, "Recovered answer")
        self.assertEqual(mock_llm.invoke.call_count, 2)


class ListSurahsTests(BaseEndpointTestCase):
    def _build_chapters_response(self):
        return {
            "chapters": [
                {
                    "id": 1,
                    "name_arabic": "الفاتحة",
                    "name_simple": "Al-Fatihah",
                    "verses_count": 7,
                },
                {
                    "id": 2,
                    "name_arabic": "البقرة",
                    "name_simple": "Al-Baqarah",
                    "verses_count": 286,
                },
            ]
        }

    @patch("services.quran_service.requests.get")
    def test_list_surahs_returns_all_fields(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = self._build_chapters_response()
        mock_get.return_value = mock_response

        response = self.client.get("/surahs")

        self.assertEqual(response.status_code, 200)
        surahs = response.json()
        self.assertEqual(len(surahs), 2)
        self.assertEqual(surahs[0], {
            "number": 1,
            "name_arabic": "الفاتحة",
            "name_english": "Al-Fatihah",
            "ayahs": 7,
        })
        self.assertEqual(surahs[1]["number"], 2)
        self.assertEqual(surahs[1]["ayahs"], 286)

    @patch("services.quran_service.requests.get")
    def test_list_surahs_hits_correct_upstream_url(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = self._build_chapters_response()
        mock_get.return_value = mock_response

        self.client.get("/surahs")

        mock_get.assert_called_once_with(
            "https://api.quran.com/api/v4/chapters",
            params={},
            timeout=15,
        )

    @patch("services.quran_service.requests.get")
    def test_list_surahs_upstream_failure_returns_502(self, mock_get):
        mock_get.side_effect = requests.RequestException("connection failed")

        response = self.client.get("/surahs")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Failed to fetch surah list from upstream Quran API")

    @patch("services.quran_service.requests.get")
    def test_list_surahs_upstream_http_error_returns_502(self, mock_get):
        mock_response = Mock(status_code=500)
        mock_response.json.return_value = {"status": 500, "message": "Upstream error"}
        mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        response = self.client.get("/surahs")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Upstream error")


if __name__ == "__main__":
    unittest.main()

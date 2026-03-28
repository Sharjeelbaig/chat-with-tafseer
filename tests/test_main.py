import unittest
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient

from main import app


class GetTafseerTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

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


if __name__ == "__main__":
    unittest.main()

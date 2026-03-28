import requests

API_BASE_URL = "https://api.quran.com/api/v4"
REQUEST_TIMEOUT_SECONDS = 15


class Quran:
    def __init__(self):
        self.base_url = API_BASE_URL

    def get_tafseer_by_chapter(self, resource_id, chapter_number):
        response = requests.get(
            f"{self.base_url}/tafsirs/{resource_id}/by_chapter/{chapter_number}",
            params={},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

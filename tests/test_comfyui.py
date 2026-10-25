import os
import unittest
from unittest.mock import patch

from worker import comfyui


class ComfyUIClientTests(unittest.TestCase):
    def test_rejects_remote_hosts(self):
        with patch.dict(os.environ, {"COMFYUI_URL": "https://example.invalid"}, clear=False):
            with self.assertRaises(comfyui.ComfyUIError):
                comfyui.health()

    @patch("worker.comfyui._request")
    def test_queue_returns_prompt_id(self, request):
        request.return_value = {"prompt_id": "abc-123"}
        with patch.dict(os.environ, {"COMFYUI_URL": "http://127.0.0.1:8188"}, clear=False):
            self.assertEqual(comfyui.queue({"1": {"class_type": "EmptyLatentImage"}}), "abc-123")
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()

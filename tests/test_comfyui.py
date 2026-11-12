import os
import unittest
from unittest.mock import patch

from worker import comfyui


class ComfyUIClientTests(unittest.TestCase):
    def test_accepts_only_a_loopback_origin(self):
        for url in ("http://127.0.0.1:8188/history", "http://localhost:8188?debug=1"):
            with self.subTest(url=url), patch.dict(os.environ, {"COMFYUI_URL": url}):
                with self.assertRaises(comfyui.ComfyUIError):
                    comfyui.health()
        with patch.dict(os.environ, {"COMFYUI_URL": "http://localhost:8188/"}):
            self.assertEqual(comfyui._base_url(), "http://127.0.0.1:8188")

    @patch("worker.comfyui._request")
    def test_completed_failure_is_not_returned_as_output(self, request):
        request.return_value = {"job": {"status": {"completed": True, "status_str": "error"}}}
        with self.assertRaisesRegex(comfyui.ComfyUIError, "workflow failed"):
            comfyui.wait("job")

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

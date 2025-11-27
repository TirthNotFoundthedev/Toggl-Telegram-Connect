import unittest
from unittest.mock import MagicMock, patch
import os
import json

# Set dummy env vars before importing main
os.environ["TELEGRAM_BOT_TOKEN"] = "123:dummy"
os.environ["SUPABASE_URL"] = "https://dummy.supabase.co"
os.environ["SUPABASE_KEY"] = "dummy"

from main import telegram_webhook_handler

class TestGCFHandler(unittest.TestCase):
    @patch('main.get_application')
    @patch('main.Update')
    def test_handler_success(self, mock_update_cls, mock_get_app):
        # Mock the application and its bot
        mock_app = MagicMock()
        mock_app.bot = MagicMock()
        # Mock process_update to be an async function (coroutine)
        async def async_mock(*args, **kwargs):
            return None
        mock_app.process_update.side_effect = async_mock
        
        mock_get_app.return_value = mock_app

        # Mock Update.de_json
        mock_update_instance = MagicMock()
        mock_update_cls.de_json.return_value = mock_update_instance

        # Mock the request
        mock_request = MagicMock()
        mock_request.is_json = True
        mock_request.get_json.return_value = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "date": 1600000000,
                "chat": {"id": 123, "type": "private"},
                "text": "/status"
            }
        }

        # Call the handler
        response = telegram_webhook_handler(mock_request)
        
        # Assertions
        self.assertEqual(response, "ok")
        mock_app.process_update.assert_called_once_with(mock_update_instance)

if __name__ == '__main__':
    unittest.main()

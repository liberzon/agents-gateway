import unittest
from datetime import datetime

from workspace_suite.transformers.gmail_link_transformer import transform_gmail_to_link_data


class TestGmailLinkTransformer(unittest.TestCase):
    def test_basic_email_transformation(self):
        """Test basic email transformation without attachments."""
        raw_message = {
            "id": "18c5a1b2f3d4e5f6",
            "threadId": "18c5a1b2f3d4e5f6",
            "labelIds": ["INBOX"],
            "snippet": "Hi, let's meet tomorrow at 2pm",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice Smith <alice@example.com>"},
                    {"name": "Subject", "value": "Meeting tomorrow"},
                    {"name": "Date", "value": "Mon, 28 Oct 2025 10:30:00 -0700"},
                ]
            },
            "internalDate": "1730139000000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertEqual(result.message_id, "18c5a1b2f3d4e5f6")
        self.assertEqual(result.gmail_link, "https://mail.google.com/mail/u/0/#inbox/18c5a1b2f3d4e5f6")
        self.assertEqual(result.subject, "Meeting tomorrow")
        self.assertEqual(result.from_address, "alice@example.com")
        self.assertEqual(result.from_name, "Alice Smith")
        self.assertEqual(result.snippet, "Hi, let's meet tomorrow at 2pm")
        self.assertEqual(result.labels, ["INBOX"])
        self.assertFalse(result.is_unread)
        self.assertEqual(result.attachments, [])
        self.assertEqual(result.thread_id, "18c5a1b2f3d4e5f6")

    def test_email_with_attachments(self):
        """Test email transformation with multiple attachments."""
        raw_message = {
            "id": "msg123",
            "threadId": "thread123",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Please review the attached documents",
            "payload": {
                "headers": [
                    {"name": "From", "value": "bob@example.com"},
                    {"name": "Subject", "value": "Documents for review"},
                    {"name": "Date", "value": "Tue, 29 Oct 2025 14:00:00 -0700"},
                ],
                "parts": [
                    {"partId": "0", "mimeType": "text/plain", "filename": "", "body": {"size": 123}},
                    {
                        "partId": "1",
                        "mimeType": "application/pdf",
                        "filename": "document.pdf",
                        "body": {"attachmentId": "ANGjdJ8..."},
                    },
                    {
                        "partId": "2",
                        "mimeType": "image/jpeg",
                        "filename": "photo.jpg",
                        "body": {"attachmentId": "ANGjdJ9..."},
                    },
                ],
            },
            "internalDate": "1730225000000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertEqual(result.message_id, "msg123")
        self.assertEqual(result.subject, "Documents for review")
        self.assertEqual(result.from_address, "bob@example.com")
        self.assertIsNone(result.from_name)  # No name in From header
        self.assertTrue(result.is_unread)
        self.assertEqual(len(result.attachments), 2)

        # Check first attachment
        self.assertEqual(result.attachments[0].filename, "document.pdf")
        self.assertEqual(result.attachments[0].mime_type, "application/pdf")
        self.assertEqual(result.attachments[0].part_id, "1")

        # Check second attachment
        self.assertEqual(result.attachments[1].filename, "photo.jpg")
        self.assertEqual(result.attachments[1].mime_type, "image/jpeg")
        self.assertEqual(result.attachments[1].part_id, "2")

    def test_unread_email(self):
        """Test unread status detection."""
        raw_message = {
            "id": "msg456",
            "labelIds": ["INBOX", "UNREAD", "IMPORTANT"],
            "snippet": "Urgent message",
            "payload": {
                "headers": [
                    {"name": "From", "value": "urgent@example.com"},
                    {"name": "Subject", "value": "Urgent"},
                    {"name": "Date", "value": "Wed, 30 Oct 2025 09:00:00 -0700"},
                ]
            },
            "internalDate": "1730304000000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertTrue(result.is_unread)
        self.assertIn("UNREAD", result.labels)
        self.assertIn("IMPORTANT", result.labels)

    def test_from_header_parsing_with_name(self):
        """Test From header parsing with name and email."""
        raw_message = {
            "id": "msg789",
            "snippet": "Test",
            "payload": {
                "headers": [
                    {"name": "From", "value": "John Doe <john.doe@example.com>"},
                    {"name": "Subject", "value": "Test"},
                    {"name": "Date", "value": "Thu, 31 Oct 2025 12:00:00 -0700"},
                ]
            },
            "internalDate": "1730401200000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertEqual(result.from_name, "John Doe")
        self.assertEqual(result.from_address, "john.doe@example.com")

    def test_from_header_parsing_email_only(self):
        """Test From header parsing with email only."""
        raw_message = {
            "id": "msg101",
            "snippet": "Test",
            "payload": {
                "headers": [
                    {"name": "From", "value": "noreply@example.com"},
                    {"name": "Subject", "value": "Test"},
                    {"name": "Date", "value": "Fri, 01 Nov 2025 15:00:00 -0700"},
                ]
            },
            "internalDate": "1730498400000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertIsNone(result.from_name)
        self.assertEqual(result.from_address, "noreply@example.com")

    def test_date_parsing_fallback(self):
        """Test date parsing fallback to internalDate when Date header is missing."""
        raw_message = {
            "id": "msg202",
            "snippet": "Test",
            "payload": {
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Subject", "value": "Test"},
                    # No Date header
                ]
            },
            "internalDate": "1730139000000",  # Oct 28, 2025 10:30:00 UTC
        }

        result = transform_gmail_to_link_data(raw_message)

        # Check that date was parsed from internalDate
        self.assertIsInstance(result.date, datetime)
        # Verify it's approximately correct (within a day to handle timezone differences)
        expected_timestamp = 1730139000  # seconds
        actual_timestamp = int(result.date.timestamp())
        self.assertAlmostEqual(actual_timestamp, expected_timestamp, delta=86400)

    def test_no_subject(self):
        """Test email without subject header."""
        raw_message = {
            "id": "msg303",
            "snippet": "Test",
            "payload": {
                "headers": [
                    {"name": "From", "value": "test@example.com"},
                    {"name": "Date", "value": "Sat, 02 Nov 2025 10:00:00 -0700"},
                    # No Subject header
                ]
            },
            "internalDate": "1730577600000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertEqual(result.subject, "(No subject)")

    def test_empty_payload(self):
        """Test email with minimal/empty payload."""
        raw_message = {
            "id": "msg404",
            "labelIds": [],
            "snippet": "",
            "payload": {},
            "internalDate": "1730139000000",
        }

        result = transform_gmail_to_link_data(raw_message)

        self.assertEqual(result.message_id, "msg404")
        self.assertEqual(result.subject, "(No subject)")
        self.assertEqual(result.from_address, "")
        self.assertIsNone(result.from_name)
        self.assertEqual(result.snippet, "")
        self.assertEqual(result.labels, [])
        self.assertFalse(result.is_unread)
        self.assertEqual(result.attachments, [])


if __name__ == "__main__":
    unittest.main()

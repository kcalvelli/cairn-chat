"""Tests for media detection, download, and UserMessage types."""

import base64

import pytest

from axios_ai_bot.media import (
    EXTENSION_MIME_MAP,
    MediaAttachment,
    UserMessage,
    _localize_upload_url,
    filename_from_url,
    mime_type_from_content_type,
    mime_type_from_url,
    unsupported_type_message,
)


class TestMediaAttachment:
    """Tests for MediaAttachment dataclass."""

    def test_image_attachment(self):
        """Test creating an image attachment."""
        data = b"\xff\xd8\xff\xe0"  # JPEG magic bytes
        att = MediaAttachment(data=data, mime_type="image/jpeg", filename="photo.jpg")
        assert att.is_image
        assert not att.is_document
        assert att.size == 4
        assert att.mime_type == "image/jpeg"

    def test_document_attachment(self):
        """Test creating a PDF attachment."""
        data = b"%PDF-1.4"
        att = MediaAttachment(data=data, mime_type="application/pdf", filename="doc.pdf")
        assert not att.is_image
        assert att.is_document
        assert att.size == 8

    def test_to_claude_content_block_image(self):
        """Test converting image attachment to Claude content block."""
        data = b"fake-image-data"
        att = MediaAttachment(data=data, mime_type="image/png", filename="test.png")
        block = att.to_claude_content_block()

        assert block["type"] == "image"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "image/png"
        assert block["source"]["data"] == base64.b64encode(data).decode("utf-8")

    def test_to_claude_content_block_document(self):
        """Test converting PDF attachment to Claude content block."""
        data = b"fake-pdf-data"
        att = MediaAttachment(data=data, mime_type="application/pdf", filename="doc.pdf")
        block = att.to_claude_content_block()

        assert block["type"] == "document"
        assert block["source"]["type"] == "base64"
        assert block["source"]["media_type"] == "application/pdf"

    def test_to_claude_content_block_unsupported(self):
        """Test that unsupported MIME types raise ValueError."""
        att = MediaAttachment(data=b"data", mime_type="audio/ogg", filename="voice.ogg")
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            att.to_claude_content_block()


class TestUserMessage:
    """Tests for UserMessage dataclass."""

    def test_text_only_message(self):
        """Test text-only message returns plain string."""
        msg = UserMessage(text="Hello world")
        assert not msg.has_attachments
        content = msg.to_claude_content()
        assert content == "Hello world"
        assert isinstance(content, str)

    def test_image_message_no_caption(self):
        """Test image message without caption."""
        att = MediaAttachment(data=b"img", mime_type="image/jpeg", filename="photo.jpg")
        msg = UserMessage(text="", attachments=[att])
        assert msg.has_attachments

        content = msg.to_claude_content()
        assert isinstance(content, list)
        assert len(content) == 1  # Just the image block, no text
        assert content[0]["type"] == "image"

    def test_image_message_with_caption(self):
        """Test image message with caption."""
        att = MediaAttachment(data=b"img", mime_type="image/jpeg", filename="photo.jpg")
        msg = UserMessage(text="What plant is this?", attachments=[att])

        content = msg.to_claude_content()
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "image"
        assert content[1]["type"] == "text"
        assert content[1]["text"] == "What plant is this?"

    def test_pdf_message(self):
        """Test PDF document message."""
        att = MediaAttachment(data=b"pdf", mime_type="application/pdf", filename="doc.pdf")
        msg = UserMessage(text="Summarize this", attachments=[att])

        content = msg.to_claude_content()
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "document"
        assert content[1]["type"] == "text"

    def test_empty_text_no_attachments(self):
        """Test empty text with no attachments returns empty string."""
        msg = UserMessage(text="")
        assert not msg.has_attachments
        assert msg.to_claude_content() == ""


class TestMimeTypeDetection:
    """Tests for MIME type detection utilities."""

    def test_mime_from_url_jpeg(self):
        """Test JPEG URL detection."""
        assert mime_type_from_url("https://example.com/photo.jpg") == "image/jpeg"
        assert mime_type_from_url("https://example.com/photo.jpeg") == "image/jpeg"

    def test_mime_from_url_png(self):
        """Test PNG URL detection."""
        assert mime_type_from_url("https://example.com/image.png") == "image/png"

    def test_mime_from_url_pdf(self):
        """Test PDF URL detection."""
        assert mime_type_from_url("https://example.com/doc.pdf") == "application/pdf"

    def test_mime_from_url_with_query_params(self):
        """Test URL with query parameters."""
        assert mime_type_from_url("https://example.com/photo.jpg?token=abc") == "image/jpeg"

    def test_mime_from_url_unknown(self):
        """Test unknown file extension."""
        assert mime_type_from_url("https://example.com/file.zip") is None

    def test_mime_from_content_type(self):
        """Test Content-Type header parsing."""
        assert mime_type_from_content_type("image/jpeg") == "image/jpeg"
        assert mime_type_from_content_type("image/jpeg; charset=utf-8") == "image/jpeg"
        assert mime_type_from_content_type("application/pdf") == "application/pdf"

    def test_mime_from_content_type_unsupported(self):
        """Test unsupported Content-Type."""
        assert mime_type_from_content_type("audio/ogg") is None
        assert mime_type_from_content_type("application/zip") is None


class TestFilenameExtraction:
    """Tests for filename extraction from URLs."""

    def test_simple_url(self):
        """Test simple URL filename."""
        assert filename_from_url("https://example.com/photo.jpg") == "photo.jpg"

    def test_url_with_path(self):
        """Test URL with path components."""
        assert filename_from_url("https://example.com/upload/abc/photo.jpg") == "photo.jpg"

    def test_url_with_query(self):
        """Test URL with query parameters."""
        assert filename_from_url("https://example.com/photo.jpg?token=abc") == "photo.jpg"

    def test_url_no_filename(self):
        """Test URL without filename."""
        assert filename_from_url("https://example.com/") == "attachment"


class TestUnsupportedTypeMessage:
    """Tests for unsupported file type messages."""

    def test_zip_file(self):
        """Test message for .zip file."""
        msg = unsupported_type_message("https://example.com/archive.zip")
        assert ".zip" in msg
        assert "images" in msg
        assert "PDFs" in msg

    def test_exe_file(self):
        """Test message for .exe file."""
        msg = unsupported_type_message("https://example.com/program.exe")
        assert ".exe" in msg

    def test_no_extension(self):
        """Test message for URL without extension."""
        msg = unsupported_type_message("https://example.com/file")
        assert "this type of" in msg


class TestLocalizeUploadUrl:
    """Tests for _localize_upload_url."""

    def test_rewrites_https_5281_to_http_5280(self):
        url = "https://chat.example.ts.net:5281/upload/abc123/photo.jpg"
        result = _localize_upload_url(url)
        assert result == "http://chat.example.ts.net:5280/upload/abc123/photo.jpg"

    def test_leaves_other_urls_unchanged(self):
        url = "https://example.com/image.jpg"
        assert _localize_upload_url(url) == url

    def test_leaves_http_urls_unchanged(self):
        url = "http://localhost:5280/upload/abc123/photo.jpg"
        assert _localize_upload_url(url) == url

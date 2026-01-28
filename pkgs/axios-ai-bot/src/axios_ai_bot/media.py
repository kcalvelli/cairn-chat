"""Media detection, download, and message types for multimodal XMPP messages."""

import base64
import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Supported MIME types for Claude
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
DOCUMENT_MIME_TYPES = {"application/pdf"}
SUPPORTED_MIME_TYPES = IMAGE_MIME_TYPES | DOCUMENT_MIME_TYPES

# Claude's limits
MAX_IMAGE_SIZE = 3_932_160  # 3.75 MB
MAX_DOCUMENT_SIZE = 33_554_432  # 32 MB

# File extension to MIME type mapping
EXTENSION_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

# Regex for detecting URLs in message body
URL_PATTERN = re.compile(r"^(https?://\S+)$")


@dataclass
class MediaAttachment:
    """A media attachment downloaded from an XMPP file upload."""

    data: bytes
    mime_type: str
    filename: str

    @property
    def is_image(self) -> bool:
        return self.mime_type in IMAGE_MIME_TYPES

    @property
    def is_document(self) -> bool:
        return self.mime_type in DOCUMENT_MIME_TYPES

    @property
    def size(self) -> int:
        return len(self.data)

    def to_claude_content_block(self) -> dict:
        """Convert to a Claude API content block.

        Returns:
            A dict suitable for inclusion in Claude's messages API content list.
        """
        b64_data = base64.b64encode(self.data).decode("utf-8")

        if self.is_image:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": self.mime_type,
                    "data": b64_data,
                },
            }
        elif self.is_document:
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": self.mime_type,
                    "data": b64_data,
                },
            }
        else:
            raise ValueError(f"Unsupported MIME type: {self.mime_type}")


@dataclass
class UserMessage:
    """A structured message from the user, possibly with media attachments.

    This replaces the raw `str` message throughout the pipeline.
    """

    text: str
    attachments: list[MediaAttachment] = field(default_factory=list)

    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0

    def to_claude_content(self) -> str | list[dict]:
        """Convert to Claude API message content.

        Returns:
            A plain string for text-only messages, or a list of content blocks
            for messages with attachments.
        """
        if not self.has_attachments:
            return self.text

        # Build content blocks: attachments first, then text
        blocks: list[dict] = []
        for attachment in self.attachments:
            blocks.append(attachment.to_claude_content_block())

        if self.text:
            blocks.append({"type": "text", "text": self.text})

        return blocks


def detect_media_url(msg) -> str | None:
    """Detect a media URL in an XMPP message.

    Checks for OOB (Out-of-Band) data first, then falls back to
    checking if the message body is a single URL.

    Args:
        msg: A slixmpp Message stanza

    Returns:
        The media URL if detected, or None
    """
    # Check OOB element (XEP-0066)
    try:
        oob_url = msg["oob"]["url"]
        if oob_url:
            logger.debug(f"Found OOB URL: {oob_url}")
            return str(oob_url)
    except (KeyError, AttributeError):
        pass

    # Check if body is a single URL (common pattern for file uploads)
    body = str(msg.get("body", "") or "")
    match = URL_PATTERN.match(body.strip())
    if match:
        url = match.group(1)
        # Only treat as media if it looks like a file upload URL
        # (has a file extension we recognize)
        lower_url = url.lower()
        for ext in EXTENSION_MIME_MAP:
            if lower_url.endswith(ext) or f"{ext}?" in lower_url:
                logger.debug(f"Found media URL in body: {url}")
                return url
        logger.debug(f"URL in body but not a recognized media extension: {url}")

    return None


def get_caption(msg, media_url: str | None) -> str:
    """Extract caption text from a message that contains media.

    If the body is just the media URL, the caption is empty.
    If the body contains additional text beyond the URL, that's the caption.

    Args:
        msg: A slixmpp Message stanza
        media_url: The detected media URL (to strip from body)

    Returns:
        Caption text, possibly empty
    """
    body = str(msg.get("body", "") or "").strip()

    if not body or not media_url:
        return body

    # If body is just the URL, no caption
    if body == media_url:
        return ""

    # If body contains URL + extra text, strip the URL for the caption
    caption = body.replace(media_url, "").strip()
    return caption


def mime_type_from_url(url: str) -> str | None:
    """Guess MIME type from URL file extension.

    Args:
        url: The file URL

    Returns:
        MIME type string or None if unrecognized
    """
    lower_url = url.lower().split("?")[0]  # Strip query params
    for ext, mime in EXTENSION_MIME_MAP.items():
        if lower_url.endswith(ext):
            return mime
    return None


def mime_type_from_content_type(content_type: str) -> str | None:
    """Extract and validate MIME type from Content-Type header.

    Args:
        content_type: The Content-Type header value

    Returns:
        MIME type string if supported, None otherwise
    """
    # Content-Type may include charset: "image/jpeg; charset=utf-8"
    mime = content_type.split(";")[0].strip().lower()
    if mime in SUPPORTED_MIME_TYPES:
        return mime
    return None


def filename_from_url(url: str) -> str:
    """Extract filename from URL.

    Args:
        url: The file URL

    Returns:
        Filename string
    """
    path = url.split("?")[0].split("/")[-1]
    return path or "attachment"


def _localize_upload_url(url: str) -> str:
    """Rewrite external upload URL to local Prosody HTTP.

    Tailscale Serve forwards TCP on port 5280 to Prosody HTTP on localhost.
    The bot runs on the same host, so it downloads directly from Prosody
    on localhost without going through Tailscale Serve.
    """
    if ":5280/" in url:
        # Extract path from URL and rewrite to localhost Prosody HTTP
        path = url.split(":5280", 1)[1]  # everything after :5280
        return f"http://127.0.0.1:5280{path}"
    return url


async def download_media(url: str, verify_ssl: bool = False) -> MediaAttachment | None:
    """Download media from a URL and create a MediaAttachment.

    Args:
        url: URL to download from
        verify_ssl: Whether to verify SSL certificates (False for self-signed)

    Returns:
        MediaAttachment if successful, None if download fails or unsupported type
    """
    download_url = _localize_upload_url(url)
    if download_url != url:
        logger.debug(f"Rewrote upload URL for local download: {download_url}")
    try:
        async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
            response = await client.get(download_url)
            response.raise_for_status()

            # Determine MIME type from Content-Type header first, then URL
            content_type = response.headers.get("content-type", "")
            mime_type = mime_type_from_content_type(content_type)
            if not mime_type:
                mime_type = mime_type_from_url(url)

            if not mime_type:
                logger.warning(f"Unsupported media type from {url}: {content_type}")
                return None

            data = response.content
            filename = filename_from_url(url)

            # Check size limits
            if mime_type in IMAGE_MIME_TYPES and len(data) > MAX_IMAGE_SIZE:
                logger.warning(
                    f"Image too large ({len(data)} bytes > {MAX_IMAGE_SIZE}), "
                    f"skipping: {filename}"
                )
                return None

            if mime_type in DOCUMENT_MIME_TYPES and len(data) > MAX_DOCUMENT_SIZE:
                logger.warning(
                    f"Document too large ({len(data)} bytes > {MAX_DOCUMENT_SIZE}), "
                    f"skipping: {filename}"
                )
                return None

            logger.info(f"Downloaded media: {filename} ({mime_type}, {len(data)} bytes)")
            return MediaAttachment(data=data, mime_type=mime_type, filename=filename)

    except httpx.HTTPError as e:
        logger.error(f"Failed to download media from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading {url}: {e}")
        return None


def unsupported_type_message(url: str) -> str:
    """Generate a user-friendly message for unsupported file types.

    Args:
        url: The file URL

    Returns:
        Error message string
    """
    filename = filename_from_url(url)
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1]

    supported = "images (JPEG, PNG, GIF, WebP) and PDFs"
    return (
        f"I can understand {supported}, but I can't process {ext or 'this type of'} files."
    )

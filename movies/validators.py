from django.core.exceptions import ValidationError
from urllib.parse import parse_qs, urlparse
import re

YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def get_youtube_video_id(value):
    if not value:
        return ""

    parsed_url = urlparse(value)
    hostname = parsed_url.hostname or ""

    if parsed_url.scheme not in ("http", "https"):
        return ""

    if hostname in ("www.youtube.com", "youtube.com"):
        if parsed_url.path == "/watch":
            video_id = parse_qs(parsed_url.query).get("v", [""])[0]
        elif parsed_url.path.startswith("/embed/"):
            video_id = parsed_url.path.split("/embed/", 1)[1].split("/", 1)[0]
        else:
            return ""
    elif hostname == "youtu.be":
        video_id = parsed_url.path.strip("/").split("/", 1)[0]
    else:
        return ""

    if YOUTUBE_VIDEO_ID_RE.match(video_id):
        return video_id

    return ""

def validate_youtube_url(value):
    if not get_youtube_video_id(value):
        raise ValidationError(
            "Enter a valid YouTube trailer URL."
        )

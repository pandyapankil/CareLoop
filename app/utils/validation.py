import re
import os
from html.parser import HTMLParser


_ALLOWED_TAGS = frozenset(
    {
        "b",
        "i",
        "u",
        "em",
        "strong",
        "p",
        "br",
        "ul",
        "ol",
        "li",
        "span",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "hr",
        "a",
        "sub",
        "sup",
    }
)

_ALLOWED_FILE_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".dcm",
        ".dicom",
    }
)

_MAX_FILE_SIZE = 10 * 1024 * 1024


class _HTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result: list[str] = []
        self._open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _ALLOWED_TAGS:
            safe_attrs: list[str] = []
            for name, value in attrs:
                if name == "href" and tag == "a":
                    val = value or ""
                    if val.startswith(("http://", "https://", "mailto:")):
                        safe_attrs.append(f'href="{val}"')
                elif name in ("style", "class"):
                    safe_attrs.append(f'{name}="{value or ""}"')
            attr_str = (" " + " ".join(safe_attrs)) if safe_attrs else ""
            self.result.append(f"<{tag}{attr_str}>")
            self._open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _ALLOWED_TAGS and tag in self._open_tags:
            self.result.append(f"</{tag}>")
            self._open_tags.remove(tag)

    def handle_data(self, data: str) -> None:
        self.result.append(data)

    def handle_entityref(self, name: str) -> None:
        self.result.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.result.append(f"&#{name};")

    def get_output(self) -> str:
        return "".join(self.result)


def sanitize_html(text: str) -> str:
    if not text:
        return text
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(text)
    return sanitizer.get_output()


_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def validate_email(email: str) -> bool:
    if not email or len(email) > 320:
        return False
    return bool(_EMAIL_RE.match(email.strip()))


_PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)\.]{7,20}$")


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7 or len(digits) > 15:
        return False
    return bool(_PHONE_RE.match(phone.strip()))


def truncate(text: str, max_length: int) -> str:
    if not text or len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    truncated = text[: max_length - 3]
    last_space = truncated.rfind(" ")
    if last_space > max_length // 4:
        truncated = truncated[:last_space]
    return truncated + "..."


def validate_file_upload(
    filename: str,
    file_size: int,
    allowed_types: list[str] | None = None,
) -> tuple[bool, str]:
    if not filename:
        return False, "Filename is required"

    ext = os.path.splitext(filename)[1].lower()
    allowed = set(
        t.lower()
        for t in (
            allowed_types if allowed_types is not None else _ALLOWED_FILE_EXTENSIONS
        )
    )

    if ext not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        return False, f"File type '{ext}' is not allowed. Allowed types: {allowed_str}"

    if file_size > _MAX_FILE_SIZE:
        max_mb = _MAX_FILE_SIZE // (1024 * 1024)
        return False, f"File size exceeds maximum of {max_mb}MB"

    if file_size < 0:
        return False, "Invalid file size"

    return True, "OK"


_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    if not filename:
        return filename
    name = os.path.basename(filename)
    name = _FILENAME_RE.sub("_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_. ")
    if not name:
        name = "upload"
    return name

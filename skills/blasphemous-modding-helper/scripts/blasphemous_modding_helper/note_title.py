"""Canonical title rules shared by local notes and promotion validation."""


def is_canonical_title_scalar(scalar: str) -> bool:
    return (
        bool(scalar)
        and scalar == scalar.strip()
        and "\t" not in scalar
        and scalar[:1] not in ("'", '"', "[", "{", "&", "*", "!", "|", ">", "@", "%", "`")
        and not scalar.startswith(("#", "- ", "? ", ": "))
        and ": " not in scalar
        and " #" not in scalar
    )

"""Preflight, review, and explicitly promote Blasphemous 1 knowledge candidates."""

import argparse
import difflib
import hashlib
import io
import os
import re
import sys
import tempfile
import warnings
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import generate_modding_knowledge_index as indexer


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CODE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)]*)\)")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\](?:\s*(?:\([^)]*\)|\[[^]]*\]))?")
MARKDOWN_IMAGE_LINK = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\s*\((?P<destination><[^>]+>|[^)\s]+)"
    r"(?P<title>\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\)"
)
HTML_IMAGE = re.compile(r"(?i)<\s*img\b")
SCREENSHOT_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SCREENSHOT_BYTES = 1_572_864
BLOCKED_SUFFIXES = {
    ".3ds", ".assets", ".assetbundle", ".asset", ".bank", ".bin", ".bundle", ".cia",
    ".cs", ".cso", ".data", ".dll", ".dmp", ".dump", ".exe", ".gb", ".gba", ".gbc",
    ".gif", ".img", ".iso", ".jpg", ".jpeg", ".log", ".manifest", ".mp3", ".n64",
    ".nds", ".nes", ".ogg", ".pak", ".png", ".psd", ".raw", ".resource", ".rom",
    ".sfc", ".smc", ".tga", ".txt", ".v64", ".wad", ".wav", ".webp", ".wem", ".z64",
}
BLOCKED_DIRECTORIES = {"assets", "decompiled", "dump", "dumps", "extracted-assets", "log", "logs"}
LOG_LEVEL = r"(?:fatal|error|warning|message|info|debug|trace)"
# shortcut: match BepInEx [level: source] and timestamped severity lines, expand for other formats.
MARKDOWN_LOG_PREFIX = re.compile(r"^(?:\s*(?:>\s*|(?:[-+*]|\d+[.)])\s+|`{1,3}\s*))*")
LOG_LINE = re.compile(
    rf"^\s*(?:\[{LOG_LEVEL}\b\s*:\s*[^\]]+\]|"
    rf"\d{{4}}[.-]\d{{2}}[.-]\d{{2}}[ T]\d{{2}}:\d{{2}}:\d{{2}}(?:[.,]\d+)?\s*"
    rf"(?:\[{LOG_LEVEL}\b[^\]]*\]|{LOG_LEVEL}\b)"
    rf"|\[\d{{2}}:\d{{2}}:\d{{2}}(?:\.\d+)?\]\s*\[?{LOG_LEVEL}\b)",
    re.IGNORECASE,
)
PRIVATE_PATH = re.compile(r"(?i)(?:\b[A-Z]:[\\/]+Users[\\/]+[^/\\\s]+|/(?:Users|home)/[^/\s]+|~[/\\])")
SECRET_VALUE = re.compile(
    r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|passwd|secret|authorization)"
    r"\b\s*[:=]\s*(?!\[?(?:redacted|placeholder|example|dummy)\b)['\"]?[A-Za-z0-9_./+=:-]{6,}"
)
TOKEN_VALUE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")


class CandidateError(ValueError):
    pass


def _candidate_path(repository_root, value):
    root = Path(repository_root).resolve()
    knowledge_root = root / "docs" / "modding-knowledge"
    candidates_root = knowledge_root / "candidates"
    if any(indexer._is_link_or_junction(path) for path in (root / "docs", knowledge_root, candidates_root)):
        raise CandidateError("docs/modding-knowledge/candidates must not contain symlinked directories")

    path = Path(value)
    if not path.is_absolute():
        path = root / path
    if indexer._is_link_or_junction(path):
        raise CandidateError("candidate notes must not be symlinks or junctions")
    try:
        path = path.resolve(strict=True)
        candidate_root = candidates_root.resolve(strict=True)
    except OSError as error:
        raise CandidateError(f"candidate path is unavailable: {value}") from error
    if path.parent != candidate_root:
        raise CandidateError("candidate notes must be direct children of docs/modding-knowledge/candidates")
    if path.suffix != ".md":
        raise CandidateError("candidate inputs must be Markdown notes; raw artifacts are not accepted")
    if not path.is_file():
        raise CandidateError("candidate path must be a regular file")
    return root, knowledge_root, path


def _check_fenced_code(text, label):
    lines = text.splitlines()
    active = None
    start = 0
    warnings = []
    for number, line in enumerate(lines, 1):
        if active is None:
            opening = CODE_FENCE.match(line)
            if opening:
                active = (opening.group(1)[0], len(opening.group(1)))
                start = number
            continue

        marker, minimum = active
        if re.fullmatch(r" {0,3}" + re.escape(marker) + r"{" + str(minimum) + r",}\s*", line):
            length = number - start - 1
            if length > 150:
                raise CandidateError(f"{label}: code block at line {start} has {length} lines; maximum is 150")
            if length > 60:
                warnings.append(f"{label}: code block at line {start} has {length} lines (>60)")
            active = None

    if active is not None:
        raise CandidateError(f"{label}: unclosed fenced code block at line {start}")
    return warnings


def _check_screenshots(text, label, note_path, repository_root):
    if HTML_IMAGE.search(text):
        raise CandidateError(f"{label}: screenshots must use relative Markdown image links")

    knowledge_root = repository_root / "docs" / "modding-knowledge"
    screenshot_root = knowledge_root / "screenshots"
    images = []
    image_starts = set()
    for match in MARKDOWN_IMAGE.finditer(text):
        image_link = MARKDOWN_IMAGE_LINK.match(text, match.start())
        if image_link is None:
            raise CandidateError(f"{label}: screenshots must use relative Markdown image links")
        destination = image_link.group("destination")
        target = destination[1:-1] if destination.startswith("<") and destination.endswith(">") else destination
        try:
            parsed = urlsplit(target)
        except ValueError as error:
            raise CandidateError(f"{label}: malformed screenshot link") from error
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not parsed.path or "\\" in parsed.path:
            raise CandidateError(f"{label}: screenshots must use a relative local path")
        decoded_path = unquote(parsed.path)
        suffix = Path(decoded_path).suffix.casefold()
        if suffix not in SCREENSHOT_SUFFIXES:
            raise CandidateError(f"{label}: screenshot links must use PNG, JPEG, or WebP images")

        target_path = Path(os.path.abspath(note_path.parent / decoded_path))
        try:
            screenshot_relative = target_path.relative_to(screenshot_root)
        except ValueError as error:
            raise CandidateError(f"{label}: screenshots must be stored under docs/modding-knowledge/screenshots") from error
        current = screenshot_root
        if indexer._is_link_or_junction(current):
            raise CandidateError(f"{label}: screenshot paths must not use symlinked directories")
        for part in screenshot_relative.parts:
            current /= part
            if indexer._is_link_or_junction(current):
                raise CandidateError(f"{label}: screenshot paths must not use symlinks")
        if not target_path.is_file():
            raise CandidateError(f"{label}: screenshot does not exist: {target_path.relative_to(repository_root).as_posix()}")
        with target_path.open("rb") as stream:
            raw = stream.read(MAX_SCREENSHOT_BYTES)
        size = len(raw)
        if size >= MAX_SCREENSHOT_BYTES:
            raise CandidateError(f"{label}: each screenshot must be strictly below 1.5 MiB")
        try:
            from PIL import Image
        except ImportError as error:
            raise CandidateError(
                f"{label}: screenshot validation requires Pillow; install ci/requirements-image-validation.txt"
            ) from error
        expected_format = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}[suffix]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as decoded_image:
                    if decoded_image.format != expected_format:
                        raise CandidateError(f"{label}: screenshot bytes do not match the image extension")
                    decoded_image.verify()
                with Image.open(io.BytesIO(raw)) as decoded_image:
                    if decoded_image.format != expected_format:
                        raise CandidateError(f"{label}: screenshot bytes do not match the image extension")
                    decoded_image.load()
        except CandidateError:
            raise
        except (OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise CandidateError(f"{label}: screenshot is not a complete, valid image") from error
        canonical_path = target_path.relative_to(knowledge_root).as_posix()
        canonical_destination = quote(canonical_path, safe="/-._~")
        if destination.startswith("<") and destination.endswith(">"):
            canonical_destination = f"<{canonical_destination}>"
        image_starts.add(match.start())
        images.append(
            {
                "destination_start": image_link.start("destination"),
                "destination_end": image_link.end("destination"),
                "destination": destination,
                "canonical_destination": canonical_destination,
                "relative": target_path.relative_to(repository_root).as_posix(),
                "canonical_path": canonical_path,
                "raw": raw,
                "size": size,
            }
        )
    return images, image_starts


def _check_prohibited_content(text, label, note_path, repository_root):
    if any(ord(character) < 32 and character not in "\r\n\t" or ord(character) == 127 for character in text):
        raise CandidateError(f"{label}: terminal control characters are not accepted")
    if PRIVATE_PATH.search(text):
        raise CandidateError(f"{label}: private or user-specific paths must be removed before review")
    if SECRET_VALUE.search(text) or TOKEN_VALUE.search(text):
        raise CandidateError(f"{label}: credential-like content must be redacted before review")
    images, image_starts = _check_screenshots(text, label, note_path, repository_root)
    if any(LOG_LINE.match(MARKDOWN_LOG_PREFIX.sub("", line, count=1)) for line in text.splitlines()):
        raise CandidateError(f"{label}: raw log excerpts are not accepted")
    for match in MARKDOWN_LINK.finditer(text):
        if match.start() in image_starts:
            continue
        target = unquote(match.group(1).strip())
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        elif target:
            target = target.split(maxsplit=1)[0]
        try:
            parsed = urlsplit(target)
        except ValueError as error:
            raise CandidateError(f"{label}: malformed Markdown link") from error
        if parsed.scheme.casefold() == "data":
            raise CandidateError(f"{label}: embedded assets are not accepted")
        if parsed.scheme.casefold() == "file":
            raise CandidateError(f"{label}: private file URLs are not accepted")
        target_path = target if re.fullmatch(r"[a-z]", parsed.scheme, flags=re.IGNORECASE) else parsed.path
        path_parts = {part.casefold() for part in target_path.replace("\\", "/").split("/")}
        suffix = Path(target_path).suffix.casefold()
        if suffix in BLOCKED_SUFFIXES or path_parts & BLOCKED_DIRECTORIES:
            raise CandidateError(f"{label}: links to raw logs, game files, extracted assets, or dumps are not accepted")
    return images


def preflight_candidates(repository_root, values):
    root = Path(repository_root).resolve()
    candidates = []
    seen = set()
    for value in values:
        root, knowledge_root, path = _candidate_path(root, value)
        relative = path.relative_to(root).as_posix()
        if relative in seen:
            raise CandidateError(f"candidate was named more than once: {relative}")
        seen.add(relative)
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as error:
            raise CandidateError(f"{relative}: candidate must be readable UTF-8 text") from error
        metadata = indexer.parse_note(path, root)
        if metadata["status"] != "candidate":
            raise CandidateError(f"{relative}: preflight accepts only status: candidate notes")
        images = _check_prohibited_content(text, relative, path, root)
        warnings = _check_fenced_code(text, relative)
        if len(raw) > 120 * 1024:
            warnings.append(f"{relative}: note is {len(raw)} bytes (>120 KiB)")
        canonical_path = knowledge_root / path.name
        if canonical_path.exists() or indexer._is_link_or_junction(canonical_path):
            raise CandidateError(f"{relative}: canonical destination already exists: {canonical_path.relative_to(root).as_posix()}")
        candidates.append(
            {
                "path": path,
                "relative": relative,
                "raw": raw,
                "text": text,
                "metadata": metadata,
                "images": images,
                "warnings": warnings,
            }
        )

    _preview_indexes(root, candidates)
    return candidates


def _verified_text(candidate):
    text = candidate["text"]
    for image in reversed(candidate["images"]):
        text = (
            text[: image["destination_start"]]
            + image["canonical_destination"]
            + text[image["destination_end"] :]
        )
    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "---":
            break
        if lines[index].startswith("status: candidate"):
            lines[index] = lines[index].replace("candidate", "verified", 1)
            return "".join(lines)
    raise CandidateError(f"{candidate['relative']}: candidate status field could not be promoted")


def _preview_indexes(repository_root, candidates):
    root = Path(repository_root).resolve()
    entries = indexer.build_entries(root)
    titles = {entry["title"].casefold() for entry in entries}
    for candidate in candidates:
        title = candidate["metadata"]["title"]
        if title.casefold() in titles:
            raise CandidateError(f"verified note title already exists: {title}")
        titles.add(title.casefold())
        entries.append(
            {
                "title": title,
                "status": "verified",
                "date": candidate["metadata"]["date"],
                "path": f"docs/modding-knowledge/{candidate['path'].name}",
            }
        )
    entries.sort(key=lambda entry: (entry["title"].casefold(), entry["path"]))
    return indexer.render_indexes(entries)


def _review_fingerprint(candidates, indexes):
    digest = hashlib.sha256()
    parts = [
        b"candidate\0" + item["relative"].encode("utf-8") + b"\0" + item["raw"]
        for item in sorted(candidates, key=lambda candidate: candidate["relative"])
    ]
    parts.extend(
        b"screenshot\0" + image["relative"].encode("utf-8") + b"\0" + image["raw"]
        for item in sorted(candidates, key=lambda candidate: candidate["relative"])
        for image in item["images"]
    )
    parts.extend(
        b"index\0" + name.encode("utf-8") + b"\0" + content.encode("utf-8")
        for name, content in sorted(indexes.items())
    )
    digest.update(b"\0".join(parts))
    return digest.hexdigest()


def _print_preflight(candidates):
    print(f"Preflight passed for {len(candidates)} candidate(s).")
    for candidate in candidates:
        print(f"- {candidate['relative']} (sha256 {hashlib.sha256(candidate['raw']).hexdigest()})")
        for image in candidate["images"]:
            print(
                f"  Screenshot: {image['relative']} ({image['size']} bytes, "
                f"sha256 {hashlib.sha256(image['raw']).hexdigest()}); canonical link: {image['canonical_path']}"
            )
        for warning in candidate["warnings"]:
            print(f"  Warning: {warning}")
    print("Human review must check evidence, caller data, and privacy redactions; no content is redacted automatically.")
    if any(candidate["images"] for candidate in candidates):
        print("Review screenshots for minimal cropping, required privacy redactions, and confirmation they are not extracted assets.")


def _review(repository_root, candidates):
    root = Path(repository_root).resolve()
    knowledge_root = root / "docs" / "modding-knowledge"
    proposed = _preview_indexes(root, candidates)
    _print_preflight(candidates)
    print("\nExact candidate content (shown unchanged):")
    for candidate in candidates:
        print(f"\n--- {candidate['relative']} ---")
        print(candidate["text"], end="" if candidate["text"].endswith("\n") else "\n")
        print(f"--- end {candidate['relative']} ---")
    print("\nGenerated index changes for this exact note/batch:")
    for name, content in proposed.items():
        path = knowledge_root / name
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"{name} (current)",
            tofile=f"{name} (after approved promotion)",
        )
        rendered = "".join(diff)
        print(rendered if rendered else f"{name}: no change")
    print(f"\nReview SHA-256: {_review_fingerprint(candidates, proposed)}")
    print("\nReview every listed note, its evidence and limitations, generated indexes, and the adequacy of each privacy redaction.")


def _temporary_file(directory, content):
    descriptor, temporary_name = tempfile.mkstemp(prefix=".knowledge-promotion-", dir=directory)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    return temporary


def _atomic_write(path, content):
    temporary = _temporary_file(path.parent, content)
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def promote_candidates(repository_root, values, approved=False, review_sha256=None):
    if not approved:
        raise CandidateError("promotion requires explicit human approval and the --approve flag")
    root = Path(repository_root).resolve()
    candidates = preflight_candidates(root, values)
    knowledge_root = root / "docs" / "modding-knowledge"
    if any(indexer._is_link_or_junction(path) for path in (root / "docs", knowledge_root)):
        raise CandidateError("docs/modding-knowledge must not contain symlinked directories")

    current_entries = indexer.build_entries(root)
    current_indexes = indexer.render_indexes(current_entries)
    for name, content in current_indexes.items():
        path = knowledge_root / name
        if indexer._is_link_or_junction(path) or not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise CandidateError(f"{name} is stale; regenerate and review the current indexes before promotion")
    proposed = _preview_indexes(root, candidates)
    if not review_sha256 or review_sha256.casefold() != _review_fingerprint(candidates, proposed):
        raise CandidateError("candidate batch or generated indexes changed; review the exact batch again before promotion")
    if any(indexer._is_link_or_junction(knowledge_root / name) for name in proposed):
        raise CandidateError("generated index outputs must not be symlinks or junctions")
    index_backups = {}
    created_notes = []
    updated_indexes = []
    preserve_backups = set()
    try:
        for name in proposed:
            path = knowledge_root / name
            index_backups[name] = _temporary_file(knowledge_root, path.read_bytes())
        for candidate in candidates:
            target = knowledge_root / candidate["path"].name
            with target.open("xb") as stream:
                created_notes.append(target)
                stream.write(_verified_text(candidate).encode("utf-8"))
        for name, content in proposed.items():
            _atomic_write(knowledge_root / name, content.encode("utf-8"))
            updated_indexes.append(name)
    except Exception as error:
        rollback_failures = []
        for name in reversed(updated_indexes):
            backup = index_backups[name]
            try:
                os.replace(backup, knowledge_root / name)
            except OSError as rollback_error:
                preserve_backups.add(name)
                rollback_failures.append(f"{name} backup retained at {backup}: {rollback_error}")
        for path in reversed(created_notes):
            try:
                path.unlink()
            except OSError as rollback_error:
                rollback_failures.append(f"created note {path} could not be removed: {rollback_error}")
        if rollback_failures:
            raise CandidateError(
                f"promotion failed and rollback was incomplete: {'; '.join(rollback_failures)}"
            ) from error
        raise
    finally:
        for name, backup in index_backups.items():
            if name not in preserve_backups and backup.exists():
                try:
                    backup.unlink()
                except OSError as cleanup_error:
                    print(f"warning: could not remove temporary promotion backup {backup}: {cleanup_error}", file=sys.stderr)
    return [target.relative_to(root).as_posix() for target in created_notes]


def main(argv=None, repository_root=None):
    parser = argparse.ArgumentParser(description="Preflight, review, and explicitly promote knowledge-note candidates.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("preflight", "validate one or more candidate notes without writing files"),
        ("review", "show exact candidate content and proposed generated-index changes"),
        ("promote", "promote only the named, explicitly approved candidates"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("notes", nargs="+", help="repository-relative candidate note paths")
        if name == "promote":
            command.add_argument("--approve", action="store_true", help="confirm explicit human approval for exactly these notes")
            command.add_argument("--review-sha256", help="fingerprint printed by review for this exact note batch and its indexes")
    args = parser.parse_args(argv)
    root = Path(repository_root or REPOSITORY_ROOT).resolve()

    try:
        if args.command == "promote":
            promoted = promote_candidates(root, args.notes, approved=args.approve, review_sha256=args.review_sha256)
            for path in promoted:
                print(f"Promoted to verified canonical note: {path}")
            print("Generated INDEX.md and index.json for the approved note/batch; candidate drafts remain unchanged.")
            return 0
        candidates = preflight_candidates(root, args.notes)
        if args.command == "review":
            _review(root, candidates)
        else:
            _print_preflight(candidates)
        return 0
    except (CandidateError, indexer.NoteError, OSError, UnicodeError) as error:
        print(f"knowledge candidate error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

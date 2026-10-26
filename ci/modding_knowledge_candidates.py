"""Preflight, review, and explicitly promote Blasphemous 1 knowledge candidates."""

import argparse
import difflib
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

import generate_modding_knowledge_index as indexer


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CODE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)]*)\)")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\s*(?:\([^)]*\)|\[[^]]*\])")
BLOCKED_SUFFIXES = {
    ".3ds", ".assets", ".assetbundle", ".asset", ".bank", ".bin", ".bundle", ".cia",
    ".cs", ".cso", ".data", ".dll", ".dmp", ".dump", ".exe", ".gb", ".gba", ".gbc",
    ".gif", ".img", ".iso", ".jpg", ".jpeg", ".log", ".manifest", ".mp3", ".n64",
    ".nds", ".nes", ".ogg", ".pak", ".png", ".psd", ".raw", ".resource", ".rom",
    ".sfc", ".smc", ".tga", ".v64", ".wad", ".wav", ".webp", ".wem", ".z64",
}
BLOCKED_DIRECTORIES = {"assets", "decompiled", "dump", "dumps", "extracted-assets", "log", "logs"}
LOG_LINE = re.compile(
    r"(?i)^\s*(?:\d{4}[.-]\d{2}[.-]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s*"
    r"(?:\[[^\]]+\]|\[(?:info|warning|error|debug|trace)\]|(?:info|warning|error|debug|trace)\b)"
    r"|\[\d{2}:\d{2}:\d{2}(?:\.\d+)?\]\s*\[?(?:info|warning|error|debug|trace)\b)"
)
PRIVATE_PATH = re.compile(r"(?i)(?:\b[A-Z]:\\Users\\[^\\\s]+|/(?:Users|home)/[^/\s]+|~[/\\])")
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
    if any(path.is_symlink() for path in (root / "docs", knowledge_root, candidates_root)):
        raise CandidateError("docs/modding-knowledge/candidates must not contain symlinked directories")

    path = Path(value)
    if not path.is_absolute():
        path = root / path
    if path.is_symlink():
        raise CandidateError("candidate notes must not be symlinks")
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


def _check_prohibited_content(text, label):
    if any(ord(character) < 32 and character not in "\r\n\t" or ord(character) == 127 for character in text):
        raise CandidateError(f"{label}: terminal control characters are not accepted")
    if PRIVATE_PATH.search(text):
        raise CandidateError(f"{label}: private or user-specific paths must be removed before review")
    if SECRET_VALUE.search(text) or TOKEN_VALUE.search(text):
        raise CandidateError(f"{label}: credential-like content must be redacted before review")
    if MARKDOWN_IMAGE.search(text):
        raise CandidateError(f"{label}: embedded or extracted assets are not accepted")
    consecutive_log_lines = 0
    for line in text.splitlines():
        consecutive_log_lines = consecutive_log_lines + 1 if LOG_LINE.match(line) else 0
        if consecutive_log_lines >= 3:
            raise CandidateError(f"{label}: raw log excerpts are not accepted")
    for match in MARKDOWN_LINK.finditer(text):
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
        if parsed.scheme and parsed.scheme.casefold() not in ("http", "https", "mailto") and not re.fullmatch(
            r"[a-z]", parsed.scheme, flags=re.IGNORECASE
        ):
            continue
        target_path = target if re.fullmatch(r"[a-z]", parsed.scheme, flags=re.IGNORECASE) else parsed.path
        path_parts = {part.casefold() for part in target_path.replace("\\", "/").split("/")}
        suffix = Path(target_path).suffix.casefold()
        if suffix in BLOCKED_SUFFIXES or path_parts & BLOCKED_DIRECTORIES:
            raise CandidateError(f"{label}: links to raw logs, game files, extracted assets, or dumps are not accepted")


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
        _check_prohibited_content(text, relative)
        warnings = _check_fenced_code(text, relative)
        if len(raw) > 120 * 1024:
            warnings.append(f"{relative}: note is {len(raw)} bytes (>120 KiB)")
        canonical_path = knowledge_root / path.name
        if canonical_path.exists() or canonical_path.is_symlink():
            raise CandidateError(f"{relative}: canonical destination already exists: {canonical_path.relative_to(root).as_posix()}")
        candidates.append(
            {
                "path": path,
                "relative": relative,
                "raw": raw,
                "text": text,
                "metadata": metadata,
                "warnings": warnings,
            }
        )

    _preview_indexes(root, candidates)
    return candidates


def _verified_text(candidate):
    lines = candidate["text"].splitlines(keepends=True)
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
        b"index\0" + name.encode("utf-8") + b"\0" + content.encode("utf-8")
        for name, content in sorted(indexes.items())
    )
    digest.update(b"\0".join(parts))
    return digest.hexdigest()


def _print_preflight(candidates):
    print(f"Preflight passed for {len(candidates)} candidate(s).")
    for candidate in candidates:
        print(f"- {candidate['relative']} (sha256 {hashlib.sha256(candidate['raw']).hexdigest()})")
        for warning in candidate["warnings"]:
            print(f"  Warning: {warning}")
    print("Human review must check evidence, caller data, and privacy redactions; no content is redacted automatically.")


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


def _atomic_write(path, content):
    descriptor, temporary_name = tempfile.mkstemp(prefix=".knowledge-promotion-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
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
    if any(path.is_symlink() for path in (root / "docs", knowledge_root)):
        raise CandidateError("docs/modding-knowledge must not contain symlinked directories")

    current_entries = indexer.build_entries(root)
    current_indexes = indexer.render_indexes(current_entries)
    for name, content in current_indexes.items():
        path = knowledge_root / name
        if path.is_symlink() or not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise CandidateError(f"{name} is stale; regenerate and review the current indexes before promotion")
    proposed = _preview_indexes(root, candidates)
    if not review_sha256 or review_sha256.casefold() != _review_fingerprint(candidates, proposed):
        raise CandidateError("candidate batch or generated indexes changed; review the exact batch again before promotion")
    if any((knowledge_root / name).is_symlink() for name in proposed):
        raise CandidateError("generated index outputs must not be symlinks")
    promoted = []
    for candidate in candidates:
        target = knowledge_root / candidate["path"].name
        with target.open("xb") as stream:
            stream.write(_verified_text(candidate).encode("utf-8"))
        promoted.append(target.relative_to(root).as_posix())
    for name, content in proposed.items():
        _atomic_write(knowledge_root / name, content.encode("utf-8"))
    return promoted


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

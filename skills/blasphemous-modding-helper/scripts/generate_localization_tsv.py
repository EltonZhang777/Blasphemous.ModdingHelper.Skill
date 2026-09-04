"""Generate the checked-in Blasphemous 1 localization indexes."""

import argparse
import sys
from pathlib import Path


SEPARATOR = " -> Replace : "
LANGUAGE_FILES = {
    "zh": "Chinese_zh_base.txt",
    "en": "English_en_base.txt",
    "es": "Spanish_es_base.txt",
    "fr": "French_fr_base.txt",
    "de": "German_de_base.txt",
    "it": "Italian_it_base.txt",
    "ja": "Japanese_ja_base.txt",
    "ko": "Korean_ko_base.txt",
    "pt-BR": "Portuguese (Brazil)_pt-BR_base.txt",
    "ru": "Russian_ru_base.txt",
}
CORE_COLUMNS = ("key", "zh", "en", "es")
ALL_COLUMNS = (
    "key",
    "zh",
    "en",
    "es",
    "fr",
    "de",
    "it",
    "ja",
    "ko",
    "pt-BR",
    "ru",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPOSITORY_ROOT / ".temp" / "localization source"
DEFAULT_OUTPUT_DIR = (
    REPOSITORY_ROOT
    / "skills"
    / "blasphemous-modding-helper"
    / "references"
    / "localization"
)


class LocalizationInputError(ValueError):
    """Raised when an input corpus cannot produce aligned indexes."""


def parse_localization_file(path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise LocalizationInputError(f"{path.name}: input is not UTF-8") from error
    except OSError as error:
        raise LocalizationInputError(f"{path.name}: cannot read input: {error}") from error

    records = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line or SEPARATOR not in line:
            raise LocalizationInputError(
                f"{path.name}:{line_number}: malformed localization record"
            )
        key, value = line.split(SEPARATOR, 1)
        if not key or key != key.strip():
            raise LocalizationInputError(
                f"{path.name}:{line_number}: malformed localization key"
            )
        if key in records:
            raise LocalizationInputError(
                f"{path.name}:{line_number}: duplicate localization key {key!r}"
            )
        records[key] = value

    if not records:
        raise LocalizationInputError(f"{path.name}: input contains no records")
    return records


def load_localization_sources(input_dir):
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise LocalizationInputError(f"input directory not found: {input_dir}")

    expected_files = set(LANGUAGE_FILES.values())
    actual_files = {path.name for path in input_dir.glob("*.txt")}
    missing_files = sorted(expected_files - actual_files)
    unexpected_files = sorted(actual_files - expected_files)
    if missing_files or unexpected_files:
        details = []
        if missing_files:
            details.append("missing: " + ", ".join(missing_files))
        if unexpected_files:
            details.append("unexpected: " + ", ".join(unexpected_files))
        raise LocalizationInputError(
            "input directory must contain the ten expected language files ("
            + "; ".join(details)
            + ")"
        )

    sources = {
        language: parse_localization_file(input_dir / filename)
        for language, filename in LANGUAGE_FILES.items()
    }
    reference_keys = set(sources["zh"])
    for language, records in sources.items():
        language_keys = set(records)
        if language_keys != reference_keys:
            missing = sorted(reference_keys - language_keys)
            extra = sorted(language_keys - reference_keys)
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("extra: " + ", ".join(extra))
            raise LocalizationInputError(
                f"key set mismatch for {language} (" + "; ".join(details) + ")"
            )
    return sources


def write_index(output_path, sources, columns):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("\t".join(quote_tsv_field(value) for value in columns) + "\n")
        for key in sorted(sources["zh"]):
            row = [key] + [sources[language][key] for language in columns[1:]]
            stream.write("\t".join(quote_tsv_field(value) for value in row) + "\n")


def quote_tsv_field(value):
    if any(character in value for character in ('"', "\t", "\r", "\n")):
        return '"' + value.replace('"', '""') + '"'
    if value != value.strip():
        return '"' + value + '"'
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate the two Blasphemous 1 localization TSV indexes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--core-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "blasphemous1_zh-en-es.tsv",
    )
    parser.add_argument(
        "--all-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "blasphemous1_all.tsv",
    )
    return parser


def main(argv=None):
    arguments = build_parser().parse_args(argv)
    if arguments.core_output.resolve() == arguments.all_output.resolve():
        print("Error: core and all-language outputs must differ", file=sys.stderr)
        return 1
    try:
        sources = load_localization_sources(arguments.input_dir)
        write_index(arguments.core_output, sources, CORE_COLUMNS)
        write_index(arguments.all_output, sources, ALL_COLUMNS)
    except (LocalizationInputError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Generated {arguments.core_output}")
    print(f"Generated {arguments.all_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

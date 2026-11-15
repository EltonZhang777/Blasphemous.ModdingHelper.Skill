# ModdingAPI persistence save format

This reference describes the line-oriented files written by Blasphemous 1 ModdingAPI persistence. It is a save-analysis format reference; it does not grant configuration or profile access.

## File roles

| File | Role |
| --- | --- |
| `<Savegames>/app_settings_modded` | Global ModdingAPI persistence shared across save slots |
| `<Savegames>/app_settings_modded_backup` | Backup of global ModdingAPI persistence |
| `<Savegames>/<steam-id>/savegame_<slot>_modded.save` | Slot-scoped ModdingAPI persistence companion |
| `<Savegames>/<steam-id>/savegame_<slot>_modded.save_backup` | Backup of the slot-scoped ModdingAPI companion |
| `<Savegames>/app_settings` | Vanilla game global settings; not the ModdingAPI record stream |
| `<Savegames>/app_settings_backup` | Backup of vanilla game global settings |
| `<Savegames>/<steam-id>/savegame_<slot>.save` | Vanilla slot save; not the ModdingAPI record stream |
| `<Savegames>/<steam-id>/savegame_<slot>.save_backup` | Backup of a vanilla slot save |

The exact platform save root and any version-specific location remain host- and version-dependent and are outside the Save analysis scope. This reference adds no dependency on a ModdingAPI checkout. For one explicit file, the analyzer MUST identify the format from content and MUST NOT infer global or slot scope from the filename.

In directory analysis, the exact names in the table supply the expected role and format. A filename/content mismatch MUST retain that role and report the mismatch rather than silently reassigning the file. Only the documented `_backup` suffix is a supported backup marker.

`app_settings_modded` and the slot `_modded.save` companion are written only for Mods that implement ModdingAPI global or slot persistence. Their absence can mean no persistent Mod data exists; it MUST NOT be treated as proof that no Mods are installed.

## Grammar

The normal file is a sequence of identifier/payload record pairs:

```text
<mod identifier>
<single-line JSON payload>
<mod identifier>
<single-line JSON payload>
```

ModdingAPI writes the persistent Mod's identifier and its serialized data on consecutive lines. There is no header, schema version, record count, or end marker. The payload MUST occupy one physical line. The analyzer MUST preserve record order and MUST NOT deduplicate identifiers.

A valid JSON payload is definitive format evidence. When every payload is malformed, a complete pair is recognized only when its identifier is a conventional dot-separated ModdingAPI identifier or a GUID. Weaker text remains an unsupported format instead of being guessed as ModdingAPI data.

Duplicate identifiers can appear in a damaged, manually edited, or independently produced file. They remain separate records so the evidence does not invent one winning payload.

Blank lines are not part of the normal writer output. The analyzer MUST preserve and count them, then continue the next identifier/payload pair with the following nonblank line.

## Payload handling

| Record state | Evidence |
| --- | --- |
| Valid | Parsed standard JSON payload retained as structured data |
| Invalid | Identifier, payload line, raw payload text, JSON error, and source position retained |
| Blank | Blank line and its source position retained |
| Incomplete | Trailing identifier without a payload line retained |

The analyzer MUST reject non-standard JSON constants such as `NaN` and non-finite numbers. It MUST NOT repair an invalid payload, insert a missing payload, drop a malformed record, or merge duplicate identifiers.

Source positions are one-based physical line numbers. A valid or invalid record exposes `identifier_line` and `payload_line`; a blank record exposes `line`; an incomplete record exposes `identifier_line` and a null `payload_line`.

## Full artifact

The full ModdingAPI artifact is normalized record text:

```text
Example.Demo
{
    "saveAmount": 3,
    "saveValues": [
        "one",
        "two"
    ]
}
Example.Tail
```

Valid JSON payloads MUST use four-space indentation. Invalid payload text and incomplete trailing identifiers MUST remain in source order. The artifact has a trailing newline.

This full artifact is potentially invalid JSON and is not a single JSON document. A consumer MUST read the manifest and structured chunk first and MUST NOT parse the full record stream as one JSON value.

The structured chunk MUST expose an ordered `records` sequence with the record status and source positions. Valid records MUST expose a bounded payload shape rather than copy arbitrary payload values. Invalid records MUST expose a bounded raw-payload preview, its character count, and whether it was truncated. The full artifact remains the exact normalized record surface.

The manifest per-file entry MUST expose the format, role, parse status, valid and invalid counts, and artifact mappings.

## Malformed example

```text
Example.Broken
{"open": true

Example.Valid
{"ok": true}
Example.Incomplete
```

Evidence from this example is one invalid record, one blank line, one valid record, and one incomplete record. The full artifact retains all four entries in that order.

## Completion criteria

Completion evidence MUST include a manifest `format` of `moddingapi-records`, a structured chunk with every record in source order, and reported rather than repaired malformed or incomplete evidence.

Next action: return to [Save analysis](save-analysis.md) to report the selected input, record counts, run path, and any malformed evidence. Ask the user for another copy of the file only when the available evidence cannot answer the question.

# Reviewed semantic aliases

This document is the human-reviewed semantic layer for communication-blocking aliases. It maps community slang, translation variants, and selected code identifiers to canonical game concepts while keeping localization records unchanged.

## Rules

- Agent MUST search this document after the selected localization TSV and before controlled source analysis.
- One alias MAY map to multiple candidates. One concept MAY have multiple aliases and evidence keys. Agent MUST use context to resolve a candidate and MUST report ambiguity when context is insufficient.
- Agent MUST use light normalization only: case, surrounding whitespace, and common punctuation. Agent MUST preserve the original alias and translation wording in the result.
- `high` confidence MAY be applied directly when positive context matches. `medium` confidence MUST have an explicit mapping note. `low` confidence MUST remain a candidate only.
- Every accepted record MUST have localization evidence, gameplay/source evidence, or explicit human confirmation. AI proposals MUST receive explicit user confirmation before being written here.
- Supported `alias_type` values are `community_slang`, `translation_variant`, and `code_identifier`.
- This is a focused communication aid, not an encyclopedia. Agent MUST NOT mine every word in the localization corpus automatically. The deferred code-name-to-translation relationship table is outside this document.

## ALIAS-FERVOUR-01

- `concept_id`: `Tutorial/TUT5_CAPTION`
- `alias`: `蓝量`
- `language`: `zh`
- `alias_type`: `community_slang`
- `positive_context`: the user means the resource bar consumed by Prayers or combat techniques, or filled by attacks and executions
- `negative_context`: the user means a blue visual effect, item color, or another game's resource
- `evidence_keys`: `Tutorial/TUT5_CAPTION`, `Tutorial/TUT5_TEXT`, `Tutorial/TUT14_TEXT`, `PROPS/MSG_FERVOR_TUTORIAL_0`
- `confidence`: `medium`
- `note`: User-provided communication example; apply only with the resource context and show the official Fervour wording.

## ALIAS-FERVOUR-02

- `concept_id`: `Tutorial/TUT5_CAPTION`
- `alias`: `热情`
- `language`: `zh`
- `alias_type`: `translation_variant`
- `positive_context`: the word refers to a bar, amount, cost, regeneration, or gain associated with Prayers or attacks
- `negative_context`: the word describes narrative passion, devotion, or a character's emotion
- `evidence_keys`: `Tutorial/TUT5_CAPTION`, `Tutorial/TUT5_TEXT`, `Tutorial/TUT14_TEXT`, `UI_Inventory/LABEL_NO_FERVOYR`
- `confidence`: `medium`
- `note`: The Chinese localization uses this wording for the resource in UI and tutorial contexts, but also uses it in ordinary prose.

## ALIAS-FERVOUR-03

- `concept_id`: `Tutorial/TUT5_CAPTION`
- `alias`: `热诚`
- `language`: `zh`
- `alias_type`: `translation_variant`
- `positive_context`: the user uses the word as the resource represented by the Fervour bar or as the cost of a Prayer
- `negative_context`: the word describes a person's sincerity, zeal, or devotion in narrative text
- `evidence_keys`: `Tutorial/TUT5_CAPTION`, `Tutorial/TUT5_TEXT`, `PROPS/MSG_FERVOR_TUTORIAL_0`
- `confidence`: `medium`
- `note`: User-provided translation variant; the supplied corpus uses 热情 or 信仰 in the relevant Chinese records, so retain this as a context-bound variant.

## ALIAS-FERVOUR-04

- `concept_id`: `Tutorial/TUT5_CAPTION`
- `alias`: `fervor`
- `language`: `en`
- `alias_type`: `translation_variant`
- `positive_context`: the user means the resource bar, resource amount, Prayer cost, or resource gained from attacks
- `negative_context`: the user means passion, zeal, or fervour in ordinary narrative prose
- `evidence_keys`: `Tutorial/TUT5_CAPTION`, `Tutorial/TUT5_TEXT`, `PROPS/MSG_FERVOR_TUTORIAL_0`
- `confidence`: `medium`
- `note`: American-spelling variant of the supplied English Fervour wording; keep the source spelling visible.

## ALIAS-GUILT-01

- `concept_id`: `UI/GET_GUILTDROP_TEXT`
- `alias`: `尸体`
- `language`: `zh`
- `alias_type`: `community_slang`
- `positive_context`: the user connects the word to the object left after death, collecting or recovering it, guilt, or a penalty in the world
- `negative_context`: the user describes a literal body or corpse, burial, a dead character, or ordinary lore prose
- `evidence_keys`: `UI/GET_GUILTDROP_TEXT`, `Tutorial/TUT9_TEXT`
- `confidence`: `low`
- `note`: User-provided communication example; candidate only because the Chinese word also has an ordinary corpse meaning.

## ALIAS-CORPSE-01

- `concept_id`: `CONCEPT/CORPSE`
- `alias`: `尸体`
- `language`: `zh`
- `alias_type`: `community_slang`
- `positive_context`: the user describes a literal body, corpse, burial, or a character's physical remains in lore
- `negative_context`: the user means the recoverable Guilt Fragment left by the Penitent One's death
- `evidence_keys`: `CollectibleItem/CO11_DESCRIPTION`, `ST102_SANTOS/DLG_10203_1`
- `confidence`: `medium`
- `note`: Separate candidate preserves the ordinary prose meaning and prevents 尸体 from becoming a global Guilt Fragment synonym.

---
status: accepted
---

# Use a localization-first knowledge layer for Blasphemous 1 terms

The skill needs to identify Blasphemous terms from natural-language user requests without treating a model guess or a broad web search as the first source of truth. The supplied game-text extraction is the final Blasphemous 1 corpus and is approved for redistribution with this public skill.

## Decision

- Treat the supplied corpus as the source for localized wording, labels, translated names, and textual descriptions. Runtime behavior, mechanics, values, and code relationships remain the responsibility of game or Mod source analysis.
- Publish two UTF-8 wide-table indexes under `skills/blasphemous-modding-helper/references/localization/`:
  - `blasphemous1_zh-en-es.tsv` with columns `key`, `zh`, `en`, `es`;
  - `blasphemous1_all.tsv` with columns `key`, `zh`, `en`, `es`, `fr`, `de`, `it`, `ja`, `ko`, `pt-BR`, `ru`.
- Keep one row per localization key and preserve source values, including `@@`, tags, and parameter placeholders. Do not publish the original TXT files. The temporary converter and validation helpers are deleted after final acceptance because the supplied corpus is final and the original game will not be updated in scope.
- Add an on-demand `localization-lookup` sub-skill reached by the main skill. It is a read-only branch and does not require the Modding profile or source-code preferences. Other branches keep the existing preferences gate.
- Use direct text search with `rg`; do not add SQLite or a runtime lookup CLI. The agent searches the user's natural-language description, not an assumed complete localization key.
- Select the corpus from the request's language needs: use the Chinese/English/Spanish index by default, and load the all-language index only when the request language, translation target, or explicit comparison requires another language. Use the user's instruction language for explanations; use the requested target language for translated output.
- Search localized text first, then `semantic-aliases.md`, then route code-like or unresolved terms to `source-analyzer`. Missing or malformed indexes fail closed with an actionable error; the agent does not fill the gap with an unverified web guess.
- Maintain semantic aliases separately in `references/localization/semantic-aliases.md`. The later slang-library sub-issue covers only communication-blocking slang, abbreviations, translation variants, transliterations, and common misspellings; it is not an encyclopedia.
- Alias records use `concept_id`, `alias`, `language`, `alias_type`, `positive_context`, `negative_context`, `evidence_keys`, `confidence`, and `note`. Supported alias types are `community_slang`, `translation_variant`, and `code_identifier`.
- A concept may have multiple alias candidates and multiple evidence keys. Use a localization key as `concept_id` when it directly identifies the concept; otherwise create a separate concept ID and retain related keys as evidence.
- Context rules are natural-language conditions. Matching may normalize case, surrounding whitespace, and common punctuation, while preserving the original alias and translation wording. No regex classifier, vector store, or automatic corpus mining is added.
- High-confidence aliases may be applied directly; medium-confidence aliases require an explicit mapping note; low-confidence aliases remain candidates. Every accepted alias requires a localization key, source evidence, or an explicit human decision. AI may propose entries, but user confirmation is required before writing them.
- A source-code identifier may be related to a localized concept when current evidence supports the relationship. This may be explained to the user, but no persistent code-name-to-translation mapping table is created in this work.

## Considered Options

- Searching the raw or normalized text first keeps the evidence local, inspectable, and aligned with the user's supplied corpus.
- A SQLite database or runtime CLI would add an opaque execution boundary for a small, read-only text corpus without improving the agent's ability to inspect surrounding wording.
- Mixing semantic aliases into localization values would corrupt the distinction between what the game says and what the community says.
- Making the full corpus or the alias layer always loaded would spend context on languages and mappings that most requests do not need.

## Consequences

- The skill can recognize names and textual references from the final B1 corpus before using source analysis.
- Chinese, English, and Spanish provide the normal cross-check path; other languages remain available without inflating the default lookup context.
- Localized wording and runtime behavior remain separately attributable, so a translation mismatch does not silently become a gameplay claim.
- The semantic alias layer requires human curation and explicit ambiguity handling. The full slang library is implemented after the main localization pipeline as a follow-up sub-issue.
- A future ADR or follow-up change may add a code-name-to-translation relationship table if repeated source analysis shows that inference is insufficient.

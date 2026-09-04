# Blasphemous 1 localization lookup

Use this read-only branch for a natural-language request to identify, explain, compare, or translate a Blasphemous 1 term, name, UI phrase, or textual reference. It does not require `preferences.md`, a Modding profile, a source-code path, or a Python runtime.

## Procedure

1. Identify the user's instruction language. Use it for the explanation. Keep the source values in their original languages.
2. Confirm that `references/localization/blasphemous1_zh-en-es.tsv` exists and is readable. Its first line MUST be exactly:

   ```text
   key	zh	en	es
   ```

   A missing or malformed index is a closed failure. Report the exact path, the expected artifact, and the next maintenance action. Do not replace missing evidence with a web guess.
3. Extract distinctive words or phrases from the user's natural-language description. Search the TSV values directly with `rg`, for example:

   ```text
   rg -n -i --fixed-strings -- "distinctive phrase" skills/blasphemous-modding-helper/references/localization/blasphemous1_zh-en-es.tsv
   ```

   Search the description; do not require the user to provide a complete localization key. If the user supplies a key, use it as an additional search term, not as a prerequisite.
4. Treat matching rows as localization records. Report the key and the exact Chinese, English, and Spanish values for the relevant candidates. Preserve tags, placeholders, punctuation, and translation variants.
5. Separate evidence owners:
   - `Localization evidence`: wording, labels, translated names, and textual descriptions from the TSV.
   - `Gameplay evidence`: runtime behavior, mechanics, values, and code relationships. The localization row does not establish these facts.
6. If several rows match or the wording is ordinary prose, report candidates and the ambiguity. Do not force a canonical game concept from a weak text match. If no row matches, report that the core index has no direct match and request a more distinctive phrase or gameplay/source context.

Direct localized-text search is the first lookup stage. Later branches may add semantic aliases and controlled source-analysis fallback; an unmatched natural-language term is not an automatic source or web-search guess.

## Completion criteria

The branch is complete when it has either:

- returned one or more evidence-backed localization candidates with their keys and exact core-language values; or
- returned a closed, actionable failure for a missing/malformed index, or an explicit unresolved/candidate result without an unverified guess.

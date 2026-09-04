# Blasphemous 1 localization lookup

Use this read-only branch for a natural-language request to identify, explain, compare, or translate a Blasphemous 1 term, name, UI phrase, or textual reference. It does not require `preferences.md`, a Modding profile, a source-code path, or a Python runtime.

## Procedure

1. Identify the user's instruction language, requested source language, requested target language, and whether the user asks for a full comparison. Use the instruction language for the explanation. Keep source values in their original languages and keep translated output separate from the explanation.
2. Select the index:
   - Use `references/localization/blasphemous1_zh-en-es.tsv` as the core index by default.
   - Use `references/localization/blasphemous1_all.tsv` only when the request names a source language, target language, or comparison outside Chinese, English, and Spanish, or explicitly asks for a full comparison.
   - A request such as “用中文解释，再翻译成日文” keeps the explanation in Chinese and loads the all-language index for the Japanese translation output.
   - Do not load the all-language index for a default core-language request.
3. Confirm that the selected index exists and is readable. The core index first line MUST be exactly:

   ```text
   key	zh	en	es
   ```

   The all-language index first line MUST be exactly:

   ```text
   key	zh	en	es	fr	de	it	ja	ko	pt-BR	ru
   ```

   A missing or malformed index is a closed failure. Report the exact path, the expected artifact, and the next maintenance action. Do not replace missing evidence with a web guess.
4. Extract distinctive words or phrases from the user's natural-language description. Search the selected TSV values directly with `rg`, for example:

   ```text
   rg -n -i --fixed-strings -- "distinctive phrase" skills/blasphemous-modding-helper/references/localization/blasphemous1_zh-en-es.tsv
   ```

   Search the description; do not require the user to provide a complete localization key. If the user supplies a key, use it as an additional search term, not as a prerequisite.
5. Treat matching rows as localization records. Report the key and the exact values for the selected languages. For the core index, report Chinese, English, and Spanish. For an all-language request, report only the requested comparison or translation columns unless the user asks for every language. Preserve tags, placeholders, punctuation, and translation variants.
6. Separate evidence owners:
   - `Localization evidence`: wording, labels, translated names, and textual descriptions from the TSV.
   - `Gameplay evidence`: runtime behavior, mechanics, values, and code relationships. The localization row does not establish these facts.
7. If several rows match or the wording is ordinary prose, report candidates and the ambiguity. Do not force a canonical game concept from a weak text match. If no row matches, report that the selected index has no direct match and request a more distinctive phrase or gameplay/source context.

Direct localized-text search is the first lookup stage. Later branches may add semantic aliases and controlled source-analysis fallback; an unmatched natural-language term is not an automatic source or web-search guess.

## Completion criteria

The branch is complete when it has either:

- returned one or more evidence-backed localization candidates with their keys and exact core-language values; or
- returned a closed, actionable failure for a missing/malformed index, or an explicit unresolved/candidate result without an unverified guess.

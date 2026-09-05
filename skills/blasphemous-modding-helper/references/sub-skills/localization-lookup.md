# Blasphemous 1 localization lookup

Agent MUST use this read-only branch for a natural-language request to identify, explain, compare, or translate a Blasphemous 1 term, name, UI phrase, or textual reference. Agent MUST NOT require `preferences.md`, a Modding profile, a source-code path, or a Python runtime for this branch.

## Procedure

1. Agent MUST identify the user's instruction language, requested source language, requested target language, and whether the user asks for a full comparison. Agent MUST use the instruction language for the explanation, keep source values in their original languages, and keep translated output separate from the explanation.

   **Done when**: instruction, source, target, and comparison-language needs are explicit.

2. Agent MUST resolve the installed Skill root, then select the index relative to that root:
   - Agent MUST use `references/localization/blasphemous1_zh-en-es.tsv` as the core index by default.
   - Agent MUST use `references/localization/blasphemous1_all.tsv` when the instruction language, requested source language, requested target language, or an explicit full comparison requires a language outside Chinese, English, and Spanish.
   - A request such as “用中文解释，再翻译成日文” MUST keep the explanation in Chinese and load the all-language index for the Japanese translation output.
   - Agent MUST NOT load the all-language index for a request fully covered by the core languages.

   **Done when**: the selected index path matches every requested language need.

3. Agent MUST confirm that the selected index exists and is readable. The core index first line MUST be exactly:

   ```text
   key	zh	en	es
   ```

   The all-language index first line MUST be exactly:

   ```text
   key	zh	en	es	fr	de	it	ja	ko	pt-BR	ru
   ```

   A missing or malformed index MUST be a closed failure. Agent MUST report the exact path, expected artifact, and next maintenance action. Agent MUST NOT replace missing evidence with a web guess.

   **Done when**: the selected index is readable and its header is valid, or a closed failure is recorded.

4. Agent MUST extract distinctive words or phrases from the user's natural-language description and search the selected TSV values directly with `rg`, for example:

   ```text
   rg -n -i --fixed-strings -- "distinctive phrase" "<SkillRoot>/references/localization/blasphemous1_zh-en-es.tsv"
   ```

   Agent MUST search the description and MUST NOT require the user to provide a complete localization key. If the user supplies a key, agent MUST use it as an additional search term, not as a prerequisite.

   **Done when**: the selected index has been searched with terms derived from the request.

5. Agent MUST treat matching rows as localization records. Agent MUST report the key and exact values for the selected languages. For the core index, agent MUST report Chinese, English, and Spanish. For an all-language request, agent MUST report only the requested comparison or translation columns unless the user asks for every language. Agent MUST preserve tags, placeholders, punctuation, and translation variants.

   **Done when**: every reported localization candidate has its key and exact requested-language values.

6. Agent MUST separate evidence owners:
   - `Localization evidence`: wording, labels, translated names, and textual descriptions from the TSV.
   - `Gameplay evidence`: runtime behavior, mechanics, values, and code relationships. A localization row MUST NOT establish these facts.

   **Done when**: each claim is labeled with its evidence owner.

7. Agent MUST report candidates and ambiguity when several rows match or the wording is ordinary prose. Agent MUST NOT force a canonical game concept from a weak text match.
   - After the selected TSV search, agent MUST search [Semantic aliases](../localization/semantic-aliases.md), including when text matches are ambiguous. Agent MUST follow the matching, context, confidence, and confirmation rules in that document.
   - If no localization or alias evidence resolves the term, agent MUST route code-like identifiers, explicit source references, or unresolved terms requiring gameplay evidence to [Source analyzer](source-analyzer.md). Agent MUST follow that branch's source-path and preferences preflight.
   - Agent MUST report source-derived runtime behavior, mechanics, values, and code relationships as `Gameplay evidence`, and keep localization rows under `Localization evidence`.
   - If source evidence supports a relationship between a code identifier and a localized concept, agent MUST label it explicitly as an `Inference` and cite both sides. Agent MUST NOT create a persistent code-name-to-translation mapping table.
   - A natural-language term that remains unresolved and is not code-like MUST remain a candidate or actionable unresolved result. Agent MUST NOT turn it into an automatic source or web-search guess.

   **Done when**: the lookup has returned evidence-backed candidates, a controlled source-analysis result, or an explicit unresolved/candidate result without an unverified guess.

The lookup order MUST be localized text, semantic aliases, then controlled source analysis for code-like identifiers, explicit source references, or unresolved terms requiring gameplay evidence.

## Completion criteria

The branch is complete when it has either:

- returned one or more evidence-backed localization candidates with their keys and exact values for the selected requested languages; or
- returned a closed, actionable failure for a missing or malformed index, or an explicit unresolved/candidate result without an unverified guess.

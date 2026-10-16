# Blasphemous 1 localization lookup

The user-facing activation path is the top-level `blasphemous-modding-helper` Skill; the Agent selects this reference automatically.

Agent MUST use this read-only branch for a natural-language request to identify, explain, compare, or translate a Blasphemous 1 term, name, UI phrase, or textual reference. Agent MUST NOT require `config.yml`, a Modding profile, a source-code path, or a Python runtime for this branch.

## Read-only lookup delegation

This route follows the shared [Read-only evidence delegation](../read-only-evidence-delegation.md) contract and keeps its configuration-free exception. The main agent owns language and index selection, evidence synthesis, and any decision to escalate to source analysis.

- The main agent MAY delegate a full-language comparison, broad index search, or ambiguous multi-candidate lookup only when its evidence slice is read-only, clearly bounded, independently verifiable, and large enough to justify context isolation. A small targeted lookup SHOULD stay with the main agent.
- Before delegating, the main agent MUST complete Procedure steps 1–3: identify the instruction and requested languages, select the core or all-language index, and confirm its path, readability, and header. The child task MUST receive the exact question and search terms, the selected index's resolved path and identity (core or all-language), requested language columns, and the resolved path to `references/localization/semantic-aliases.md`; these are its only evidence sources. The child MUST NOT choose a different index or language scope.
- For every candidate, the child MUST preserve the exact localization key and requested-language TSV values, including tags, placeholders, punctuation, and variants. It MUST report all plausible candidates and ambiguity, and apply the existing semantic-alias matching, context, confidence, and confirmation rules. Alias results MUST preserve the original wording, language, type, relevant context, confidence, note, and evidence keys.
- The child MUST keep TSV results labeled as `Localization evidence`; localization wording MUST NOT establish runtime behavior, mechanics, values, or code relationships. The child MUST NOT perform or initiate source analysis. If the result needs gameplay evidence or remains an unresolved code-like identifier or explicit source reference, the child MUST return that gap to the main agent, which retains the source-route decision and its preflight.
- The child handoff MUST satisfy the shared contract with exact keys and values, the selected index and language scope, alias evidence, candidates, ambiguity, and missing evidence. The main agent SHOULD verify reported rows and aliases against those selected authorities before using them.

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
   - If no localization or alias evidence resolves the term, agent MUST route code-like identifiers, explicit source references, or unresolved terms requiring gameplay evidence to [Source analyzer](source-analyzer.md). Agent MUST follow that branch's source-path and configuration preflight.
   - Agent MUST report source-derived runtime behavior, mechanics, values, and code relationships as `Gameplay evidence`, and keep localization rows under `Localization evidence`.
   - If source evidence supports a relationship between a code identifier and a localized concept, agent MUST label it explicitly as an `Inference` and cite both sides. Agent MUST NOT create a persistent code-name-to-translation mapping table.
   - A natural-language term that remains unresolved and is not code-like MUST remain a candidate or actionable unresolved result. Agent MUST NOT turn it into an automatic source or web-search guess.

   **Done when**: the lookup has returned evidence-backed candidates, a controlled source-analysis result, or an explicit unresolved/candidate result without an unverified guess.

The lookup order MUST be localized text, semantic aliases, then controlled source analysis for code-like identifiers, explicit source references, or unresolved terms requiring gameplay evidence.

## Completion criteria

The branch is complete when it has either:

- returned one or more evidence-backed localization candidates with their keys and exact values for the selected requested languages; or
- returned a controlled source-analysis result with its required preflight and gameplay evidence; or
- returned a closed, actionable failure for a missing or malformed index, or an explicit unresolved/candidate result without an unverified guess.

Every lookup result MUST report `status`, completion evidence, the blocked reason when applicable, and the next action. The configuration-free exception does not remove this reporting requirement.

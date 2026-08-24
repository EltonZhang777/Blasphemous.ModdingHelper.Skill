# Requirement levels

This document is normative vocabulary contract for entire `blasphemous-modding-helper` Skill. It follows [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

At start of every Skill invocation, agent MUST read this document before applying another instruction from Skill. concrete rules live in branch documents and workflow references; this document defines how their requirement levels are interpreted.

## RFC 2119 keywords

These uppercase words and phrases have RFC 2119 meanings shown here:

| Keyword or phrase | Requirement level |
| --- | --- |
| `MUST`, `REQUIRED`, `SHALL` | An absolute requirement. The specified behavior is required. |
| `MUST NOT`, `SHALL NOT` | An absolute prohibition. The specified behavior is forbidden. |
| `SHOULD`, `RECOMMENDED` | A default recommendation. A valid circumstance MAY justify a different choice, but the agent MUST understand and carefully weigh the full implications first. |
| `SHOULD NOT`, `NOT RECOMMENDED` | A default against the specified behavior. A valid circumstance MAY make the behavior acceptable or useful, but the agent MUST understand and carefully weigh the full implications first. |
| `MAY`, `OPTIONAL` | A truly optional choice. The behavior MAY be included or omitted when no other requirement depends on it. |

Capitalization and exact keyword or phrase determine requirement level. Bold, code formatting, headings, and table placement have no effect on its meaning.

## Applying the vocabulary

- Authored normative instructions throughout `skills/blasphemous-modding-helper/` MUST use uppercase RFC 2119 vocabulary above. They MUST use keyword that matches actual force of rule and MUST NOT use informal synonym to express requirement.
- `MUST` and `MUST NOT` SHOULD be reserved for runtime correctness, API or interoperability constraints, safety, explicit scope boundaries, or another condition that is genuinely absolute. RFC 2119 imperatives MUST NOT be used merely to impose arbitrary implementation method.
- `SHOULD` or `SHOULD NOT` rule is not absolute requirement, but deviation still requires deliberate judgment. Agent MUST understand and weigh consequences before choosing it.
- Descriptive facts, headings, non-normative explanations, and illustrative example prose MAY omit RFC 2119 keyword. Examples MUST NOT be rewritten solely to add requirement-level word when example is not itself prescribing behavior.
- External documentation, source code, and verbatim quotations MUST retain their original wording. Their wording is not silently normalized to this contract; surrounding Skill text MAY identify material as external or quoted.
- Future changes that add or change normative requirement wording MUST scan complete installed Skill documentation for consistent RFC 2119 usage, including all Markdown under this Skill directory.
- Repository provides repeatable candidate scan in [audit_rfc2119.py](../scripts/audit_rfc2119.py). Maintainers SHOULD run it when changing requirement wording and MUST manually classify any reported factual or illustrative prose before release.

## Exception handling

Agent MUST NOT silently deviate from local `MUST`, `MUST NOT`, `SHOULD`, or `SHOULD NOT` rule. Before implementing such deviation, agent MUST:

1. Identify exact rule and requirement level being bypassed.
2. Explain reason, expected benefit, and relevant risks or compatibility impact.
3. Agent MUST ask user to confirm exception and wait for confirmation.
4. Agent MUST limit exception to confirmed case; default rule remains in force elsewhere.

Choosing option explicitly marked `MAY` or `OPTIONAL` is not itself exception. user-approved exception does not change meaning of RFC 2119 keywords or make exception new default.

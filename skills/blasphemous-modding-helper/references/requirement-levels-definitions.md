# Requirement levels

This document is the normative vocabulary contract for the entire `blasphemous-modding-helper` Skill. It follows [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

At the start of every Skill invocation, the agent MUST read this document before applying another instruction from the Skill. The concrete rules live in the branch documents and workflow references; this document defines how their requirement levels are interpreted.

## RFC 2119 keywords

The following uppercase words and phrases have the RFC 2119 meanings shown here:

| Keyword or phrase | Requirement level |
| --- | --- |
| `MUST`, `REQUIRED`, `SHALL` | An absolute requirement. The specified behavior is required. |
| `MUST NOT`, `SHALL NOT` | An absolute prohibition. The specified behavior is forbidden. |
| `SHOULD`, `RECOMMENDED` | A default recommendation. A valid circumstance MAY justify a different choice, but the agent MUST understand and carefully weigh the full implications first. |
| `SHOULD NOT`, `NOT RECOMMENDED` | A default against the specified behavior. A valid circumstance MAY make the behavior acceptable or useful, but the agent MUST understand and carefully weigh the full implications first. |
| `MAY`, `OPTIONAL` | A truly optional choice. The behavior MAY be included or omitted when no other requirement depends on it. |

Capitalization and the exact keyword or phrase determine the requirement level. Bold, code formatting, headings, and table placement have no effect on its meaning.

## Applying the vocabulary

- Authored normative instructions throughout `skills/blasphemous-modding-helper/` MUST use the uppercase RFC 2119 vocabulary above. They MUST use the keyword that matches the actual force of the rule and MUST NOT use an informal synonym to express a requirement.
- `MUST` and `MUST NOT` SHOULD be reserved for runtime correctness, API or interoperability constraints, safety, explicit scope boundaries, or another condition that is genuinely absolute. RFC 2119 imperatives MUST NOT be used merely to impose an arbitrary implementation method.
- A `SHOULD` or `SHOULD NOT` rule is not an absolute requirement, but a deviation still requires deliberate judgment. The agent MUST understand and weigh the consequences before choosing it.
- Descriptive facts, headings, non-normative explanations, and illustrative example prose MAY omit an RFC 2119 keyword. Examples MUST NOT be rewritten solely to add a requirement-level word when the example is not itself prescribing behavior.
- External documentation, source code, and verbatim quotations MUST retain their original wording. Their wording is not silently normalized to this contract; the surrounding Skill text MAY identify the material as external or quoted.
- Future changes that add or change normative requirement wording MUST scan the complete installed Skill documentation for consistent RFC 2119 usage, including all Markdown under this Skill directory.
- The repository provides a repeatable candidate scan in [audit_rfc2119.py](../scripts/audit_rfc2119.py). Maintainers SHOULD run it when changing requirement wording and MUST manually classify any reported factual or illustrative prose before release.

## Exception handling

An agent MUST NOT silently deviate from a local `MUST`, `MUST NOT`, `SHOULD`, or `SHOULD NOT` rule. Before implementing such a deviation, the agent MUST:

1. Identify the exact rule and requirement level being bypassed.
2. Explain the reason, expected benefit, and relevant risks or compatibility impact.
3. The agent MUST ask the user to confirm the exception and wait for confirmation.
4. The agent MUST limit the exception to the confirmed case; the default rule remains in force elsewhere.

Choosing an option explicitly marked `MAY` or `OPTIONAL` is not itself an exception. A user-approved exception does not change the meaning of the RFC 2119 keywords or make the exception a new default.

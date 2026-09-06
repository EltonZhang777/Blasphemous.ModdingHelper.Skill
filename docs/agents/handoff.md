# Local handoff records

`docs/handoff/` contains ignored, local continuation records. It is not Skill
authority and is not release-package input. Keep records redacted: no tokens,
credentials, session identifiers, or private machine paths.

## Status rule

Every handoff starts with exactly one status:

```text
Status: active
```

or:

```text
Status: historical snapshot
```

Records without one of these markers are historical by default. A historical
record is evidence tied to its recorded revision, not a current instruction.

## Active handoff minimum

An active record MUST identify:

- `Owner`: responsible role or person.
- `Baseline commit`: revision that bounds the evidence.
- `Evidence status`: checks run and their result.
- `Unresolved items`: open questions or missing evidence.
- `Owner decision`: accepted scope or explicit deferral.
- `Next gate`: exact check or decision needed to continue.

Use repository-relative links from `docs/handoff/`. Commands MUST name the
repository, branch or revision, and expected result. A historical command is
evidence only and MUST be labeled as such; do not present it as a command to
run against the current tree.

## Minimal template

```markdown
# Handoff: <subject>

Status: active

## Owner

<role or person>

## Baseline commit

`<full commit>`

## Evidence status

- `<check>`: `<result>`

## Unresolved items

- `<item>` or `none`

## Owner decision

<scope decision>

## Next gate

<exact check or decision>
```

Do not move local handoff or compression/review work into GitHub Actions.

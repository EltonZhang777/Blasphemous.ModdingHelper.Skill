---
status: accepted
---

# Keep native agent plugins outside the release gate

The distribution issue became coupled to native Claude and Codex marketplace routes, while this work only needs a reproducible Skill installer package and GitHub release archive. The npm package may contain the repository's plugin manifests because the approved `package.json` allowlist names those directories; that archive inclusion does not establish that either native plugin was published or that its marketplace route is supported.

## Decision

- Scope #153 and #156 to the npm installer tarball, GitHub release archive, and documented GitHub-backed Skill installation routes.
- Exclude native Claude and Codex plugin packaging, marketplace installation, and publication from those acceptance criteria.
- Keep `.claude-plugin/`, `.codex-plugin/`, and `.agents/plugins/` in the approved npm file allowlist as ancillary archive contents; their presence does not imply marketplace installation or publication.
- Do not publish npm or plugins within this spec.

## Consequences

- #156 can complete from local artifact and in-scope route evidence; it does not wait for a public npm version or native plugin publication.
- Native plugin distribution needs a separate scope and acceptance path.

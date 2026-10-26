---
title: The Fervour tutorial label has language variants
status: verified
date: 2026-10-26
---

# The Fervour tutorial label has language variants

## Applicable Blasphemous 1 version

The Blasphemous 1 localization corpus bundled with this Skill. The corpus does not record the game's build number, so this finding is not scoped to a specific game patch.

## Route

Use the read-only [Localization lookup](../../skills/blasphemous-modding-helper/references/sub-skills/localization-lookup.md) route and search the exact key `PROPS/MSG_FERVOR_TUTORIAL_0` when checking this tutorial wording.

## Evidence

Localization evidence: The `en` value in `skills/blasphemous-modding-helper/references/localization/blasphemous1_zh-en-es.tsv` is `Attack enemies to fill the Fervour bar.` The `es` value is `Ataca a enemigos para rellenar la barra de Fervor.`

## Verification result

Both language values were checked directly in the bundled TSV row for `PROPS/MSG_FERVOR_TUTORIAL_0`. This verifies the published localization text; no in-game UI run was performed.

## Limitations

This is localization evidence only. It does not establish Fervour mechanics or prove the same wording is used by every game build. Use the source or gameplay route for behavior claims.
# Manual Rewired keybinding guide

The agent MUST use this guide while the coordinator plans an input-dependent in-game test. The agent MUST inspect the relevant XML first and MUST consult in-game settings only under the fallback conditions below. The agent MUST NOT infer an effective mapping from a default, filename, or unrelated profile.

## Known XML sources

Mod keybinding XML files are under:

`<game root>\Modding\keybindings`

Saved keyboard and mouse settings are under the active Steam user's save directory:

`%USERPROFILE%\AppData\LocalLow\TheGameKitchen\Blasphemous\Savegames\<steam_id>\keybinding_settings_keyboard.xml`

`%USERPROFILE%\AppData\LocalLow\TheGameKitchen\Blasphemous\Savegames\<steam_id>\keybinding_settings_mouse.xml`

## Determine the effective mapping

1. The agent MUST identify the requested game action, active save/profile, and gameplay context.
2. The agent MUST inspect the relevant Mod and saved keyboard/mouse XML before opening in-game settings and MUST analyze whether the files reliably establish the effective mapping for that active profile, action, and context.
3. If XML is unreadable, malformed, cannot be analyzed, or leaves the effective mapping or precedence uncertain, the agent MUST consult in-game settings only if they show the same active profile, action, and context.
4. If neither the XML nor matching in-game settings reliably establishes the mapping, the agent MUST report it as unknown and ask the user. The agent MUST NOT guess or issue an input based on an assumed binding.

The official Rewired references are [Controller Maps](https://guavaman.com/projects/rewired/docs/ControllerMaps.html) and [User Data Store](https://guavaman.com/projects/rewired/docs/UserDataStore.html). They describe Rewired concepts; the game's files and matching active settings determine the mapping for this test.

## Completion criterion

The agent MUST report the action and context, which XML files or matching in-game settings were inspected, the effective mapping when established, and any unresolved mapping as unknown.

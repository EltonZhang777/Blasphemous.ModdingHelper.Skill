# ModdingAPI standards

This reference is the ModdingAPI branch selected by the [coding standards router](sub-skills/coding-standards.md). Before applying a rule, the agent MUST read [Requirement levels](requirement-levels-definitions.md). The branch covers ModdingAPI API use, BlasMod lifecycle responsibilities, service integration, upstream development-document routing, and ModLog behavior.

## Scope and authority

These rules MUST apply only to Mod-owned C# in the Caller Mod repository. Decompiled game source, upstream Mods, dependency or vendor code, generated output, and direct copies remain under the router's exclusion and preservation rules.

The caller's actual referenced ModdingAPI assembly MUST be the first authority for signatures, exposed members, overloads, access, and runtime behavior. The authority order is:

1. The assembly actually referenced by the caller's Mod, together with facts verified from the corresponding source when available.
2. Source for that exact referenced version.
3. Version-matched upstream ModdingAPI source.
4. The upstream development documentation routed below.
5. Examples in upstream documentation.

If two authorities disagree, the agent MUST inspect the caller's version and corresponding source before generating code. If the version or required API fact cannot be established, the agent MUST stop and request source analysis or ask the user; it MUST NOT guess from the current upstream branch.

For lifecycle and service questions, the current upstream source entry points are [`BlasMod.cs`](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/Blasphemous.ModdingAPI/BlasMod.cs) and [`ModServiceProvider.cs`](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/Blasphemous.ModdingAPI/ModServiceProvider.cs). These links provide a navigable upstream reference only; the caller's referenced assembly and matching source remain authoritative.

The routed development documents are a responsibility index, not a second API encyclopedia. The agent MUST read only the documents relevant to the task and MUST verify their claims against the higher-priority authorities above.

## ModdingAPI development-document route table

Every document currently under the upstream docs/development directory is listed here. A task signal in the second column MUST cause the agent to read the linked document when the task reaches that responsibility.

| Upstream document | Read when the task involves | Responsibility |
| --- | --- | --- |
| [main.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/main.md) | Navigating ModdingAPI development topics | Index of setup, lifecycle, persistence, logging, modules, and archived services |
| [setup.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/setup.md) | Creating or packaging a Mod project | Template commands, export layout, and resource folders |
| [mod.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/mod.md) | Deriving from BlasMod or registering services | Mod class callbacks and ModServiceProvider entry point |
| [execution.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/execution.md) | Ordering startup, initialization, save, or shutdown work | Manager and BlasMod event order |
| [persistence.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/persistence.md) | Global or slot save data | Persistence interfaces, reset, load, save, and storage responsibilities |
| [logging.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/logging.md) | Writing or reviewing ModLog calls | Upstream logging overview; the ModLog source below is authoritative for methods and effects |
| [config.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/config.md) | Loading or saving Mod configuration | ConfigHandler usage and configuration data |
| [files.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/files.md) | Loading Mod data, images, or other files | FileHandler and resource-loading responsibilities |
| [input.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/input.md) | Registering keybindings or reading input | InputHandler and input lifecycle |
| [localization.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/localization.md) | Registering or reading translated text | LocalizationHandler and language-change behavior |
| [console.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/console.md) | Adding console commands | ModCommand and command registration |
| [items.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/items.md) | Adding items or item effects | Item registration and item-specific extension points |
| [levels.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/levels.md) | Modifying or adding levels | Level modification surface; the upstream page is marked active development |
| [penitence.md](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/docs/development/penitence.md) | Adding penitences | Penitence registration and image/effect responsibilities |

The route table MUST be updated when the upstream development directory gains or removes a document. A stale page MAY provide context, but it MUST NOT override a conflicting assembly or source fact.

## BlasMod lifecycle

The current upstream BlasMod source exposes the following protected internal virtual callbacks. A caller's referenced version MUST be checked before any override is generated.

| Callback | Current timing | Mod responsibility (normative) |
| --- | --- | --- |
| OnPreInitialize() | Before managers initialize | When used, the Mod MUST perform only work safe before normal manager startup. This callback is version-gated. |
| OnInitialize() | After managers initialize | When used, the Mod MUST initialize Mod-local state and handlers that do not require every other Mod. |
| OnRegisterServices(ModServiceProvider provider) | After OnInitialize, while Mods can register services | When used, the Mod MUST register commands, items, levels, penitences, or other supported services through the provided service API. |
| OnAllInitialized() | After all managers and Mods finish initialization | When used, the Mod MUST perform cross-Mod setup and work that depends on all registered services being available. |
| OnDispose() | During shutdown, before managers dispose | When used, the Mod MUST perform only shutdown work the Mod actually requires. |
| OnUpdate() | Every frame after initialization | When used, the Mod MUST run only logic that cannot be event-driven and is genuinely per-frame. |
| OnLateUpdate() | At the end of every frame after initialization | When used, the Mod MUST run only per-frame logic that depends on normal updates having completed. |
| OnLevelPreloaded(string oldLevel, string newLevel) | Before a new level, including the main menu, loads | When used, the Mod MUST prepare only for a level transition before new-level objects are available. |
| OnLevelLoaded(string oldLevel, string newLevel) | After a new level, including the main menu, loads | When used, the Mod MUST locate or configure only objects that exist after the level is ready. |
| OnLevelUnloaded(string oldLevel, string newLevel) | When the old level, including the main menu, unloads | When used, the Mod MUST release or invalidate state tied to the unloaded level. |
| OnNewGame() | After data resets while starting a new game from the main menu | When used, the Mod MUST reset state that belongs to a new game. |
| OnLoadGame() | After data resets while loading an existing game from the main menu | When used, the Mod MUST reconcile state with the loaded save. |
| OnExitGame() | After quitting the current game and returning to the main menu | When used, the Mod MUST release game-session state before another session begins. |

The documented startup order is OnPreInitialize, manager Initialize, OnInitialize, OnRegisterServices, manager AllPreInitialized, manager AllInitialized, and OnAllInitialized; global data loading follows that startup sequence. During shutdown, global save precedes OnDispose and manager Dispose.

The agent MUST override only callbacks exposed by the caller's actual BlasMod version. OnPreInitialize MUST be removed from generated code when that version does not expose it. An override MUST use the actual legal accessibility and parameter signature.

A Mod MUST NOT generate empty overrides for callbacks it does not use. One-time initialization MUST NOT be placed in OnUpdate or OnLateUpdate, and cross-Mod setup MUST NOT run repeatedly from a per-frame callback. The agent MUST NOT add unconditional base calls; a base call is appropriate only when the referenced API contract or an existing non-empty base implementation requires it.

OnDispose occurs as part of final game shutdown, whose normal result is process termination. This standard MUST NOT require boilerplate subscription or resource cleanup solely because OnDispose exists. State requiring release between game sessions MUST be handled in OnExitGame or the owning lifecycle, and resources with an independent lifetime MUST be managed by their owner.

## Services and cross-Mod integration

The current ModServiceProvider source exposes RegisteringMod and the development examples use registration extensions on that provider. A Mod MUST use the actual referenced provider and extension signatures; it MUST NOT infer service methods from an outdated example.

Service registration MUST occur in OnRegisterServices. Work that consumes another Mod's registered service SHOULD occur in OnAllInitialized, after all Mods and managers have completed initialization. A Mod MUST NOT register the same one-time service every frame or use OnUpdate as a substitute for a missing service-order guarantee.

ConfigHandler, FileHandler, InputHandler, and LocalizationHandler are BlasMod-owned handlers. Their task-specific documents MUST be read before use, and their actual referenced members MUST be checked before code generation. Persistence interfaces MUST be routed through persistence.md and their load, save, and reset contracts MUST be verified against the caller's referenced version.

The current BlasMod constructor registers the Mod, applies Harmony patches to the Mod assembly, and registers ModLog. Mod code MUST NOT call PatchAll or CreateAndPatchAll for its own assembly. Target declaration and the approved manual-patch exception are owned by the Harmony branch, which Mod code MUST read for Patch declarations and exceptions.

## ModLog

The authoritative current source is [ModLog.cs](https://github.com/BrandenEK/Blasphemous.ModdingAPI/blob/main/Blasphemous.ModdingAPI/ModLog.cs). The source currently exposes these public methods; Register is internal and MUST NOT be called by Mod code.

| Public method | Public overloads | Source behavior | Intended use |
| --- | --- | --- | --- |
| Info | object message; object message, BlasMod mod | BepInEx Message level | Ordinary useful Mod state or completion information |
| Warn | object message; object message, BlasMod mod | BepInEx Warning level | Unexpected or recoverable condition |
| Error | object message; object message, BlasMod mod | BepInEx Error level | Failed operation or actionable fault |
| Fatal | object message; object message, BlasMod mod | BepInEx Fatal level; the source does not itself terminate the process | Critical failure after which the affected operation or Mod cannot safely continue |
| Debug | object message; object message, BlasMod mod | BepInEx Info level in the current source; it is not automatically compiled out | Diagnostic information during development or troubleshooting |
| Display | object message; object message, BlasMod mod | Logs at Message level and attempts to show an in-game popup; an uninitialized UI logs an Error | Information intended for the player, not ordinary diagnostics |

The one-argument overloads attribute the log to the calling assembly. A wrapper or shared helper SHOULD use the explicit BlasMod overload when calling-assembly attribution could identify the wrong Mod.

### Logging rules

- Every log call MUST choose a method whose severity matches the event.
- Error and Fatal messages MUST include enough Mod and operation context to identify what failed; ordinary Info and Warn messages SHOULD include feature or operation context when the event is not self-evident.
- A Mod SHOULD NOT emit repeated or high-frequency messages from Update, OnUpdate, or another per-frame path. Diagnostic output MUST NOT become a substitute for event-driven state.
- Display MUST be reserved for information the player needs to see. Display MUST NOT be used as a diagnostic replacement for Info, Debug, Warn, Error, or Fatal.
- A Mod MUST NOT treat Debug as Release-safe merely because the method is named Debug; the current source maps it to BepInEx Info and does not provide compile-time isolation.
- Display SHOULD be called only after the UI is initialized, normally from a lifecycle point such as OnAllInitialized or an appropriate level callback. The source catches an uninitialized UI failure, but that fallback does not make premature display calls correct.

### Pre-approved debug and temporary logging exception

A logging-only exception for debugging logging functionality is pre-approved and MAY be used without a separate per-use user confirmation when every condition below is met:

- A debug-only statement MUST be excluded from Release by #if DEBUG or another compile-time condition supported by the caller's project, so the Release build is unaffected; or
- A temporary statement MUST be marked with [DEBUG], [DIAG], or an explicit comment that identifies its temporary use, and MUST be removed after testing.

The qualifying statement MUST be for debugging logging functionality. It MUST still use a severity appropriate to the event and provide useful Mod and operation context. It MAY omit other logging guidance, such as ordinary frequency or user-facing-display rules, only for the qualifying debug or temporary statement. This exception MUST NOT waive non-logging coding, API, lifecycle, or patching rules.

If a logging statement does not satisfy every condition above, the normal exception-handling process in [Requirement levels](requirement-levels-definitions.md) applies and the agent MUST ask the user before deviating from a local rule.

## Positive and negative examples

### Lifecycle placement

Good:

```csharp
    protected override void OnAllInitialized()
    {
        RegisterWithAnotherModIfPresent();
    }
```

Bad:

```csharp
    protected override void OnUpdate()
    {
        RegisterWithAnotherModIfPresent();
    }
```

The bad placement repeats one-time cross-Mod setup every frame and ignores the documented all-initialized seam.

### Logging selection

Good:

```csharp
    ModLog.Error("DamageNumbers: failed to register damage-number service");
```

Bad:

```csharp
    ModLog.Display("DamageNumbers: entered Update");
```

The bad call turns a diagnostic event into a player-facing popup and places high-frequency information in the UI.

### Conflicting API facts

Good:

    The caller's assembly does not expose OnPreInitialize.
    Action: stop, verify the referenced source/version, and ask the user if the conflict remains.

Bad:

    The current main-branch example contains OnPreInitialize, so generate that override.

The bad path guesses from a lower-priority source and can produce a compile failure.

## Review checklist

Before finishing a ModdingAPI-related task, the reviewer MUST verify:

- The task loaded this branch through the coding standards router and passed the Mod-owned scope gate.
- Every relevant upstream docs/development document was routed without copying the upstream documentation wholesale.
- The caller's referenced assembly and corresponding source were given priority over stale or version-mismatched documentation.
- Every relevant BlasMod virtual callback was considered, with version gating and correct responsibility.
- No unused empty override, unconditional base call, repeated registration, or misplaced cross-Mod setup was introduced.
- The ModLog method inventory, severity, context, frequency, display, and debug/temporary exception rules were applied.
- Missing or conflicting API facts failed closed rather than being guessed.
- Normative wording follows [Requirement levels](requirement-levels-definitions.md).

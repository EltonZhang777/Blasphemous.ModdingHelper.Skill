# Localization

Localization source code navigation in Blasphemous (I2.Loc + the game's own `LocalizationManager`).

## Core Design Patterns

1. Dual engine: I2.Loc (third-party, `Sources[0]` holds all translation data) + game's own `LocalizationManager` (language switching, fonts, tag parsing) — keep them distinct
2. Term keys are `prefix/KEY`; `ScriptLocalization` is a compile-time generated type-safe wrapper
3. Tag system: `[ICON:name]` / `[ACT:action]` parsed by `ParseMeshPro()`
4. Text language and audio language managed independently (`CurrentAudioLanguageIndex` + `OnLocalizeAudioEvent`)

---

## Architecture Overview

Blasphemous uses **I2 Localization** (a third-party Unity plugin) as its localization engine, while also wrapping the game's own `Framework.Managers.LocalizationManager` as a bridge layer.

```
┌─────────────────────────────────────────────┐
│  I2.Loc.LocalizationManager (static)        │
│  Core fields: List<LanguageSource> Sources   │
│  Manages all translation string data and     │
│  the current language                        │
├─────────────────────────────────────────────┤
│  I2.Loc.Localize (MonoBehaviour)            │
│  Attached to Text/TextMeshPro components,   │
│  drives UI translation                      │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│  I2.Loc.ScriptLocalization (static)         │
│  Compile-time generated static wrapper      │
│  class, organized by UI module              │
│  Nested classes: UI, UI_BossRush, UI_Extras,│
│  UI_Inventory, UI_Map, UI_Penitences,       │
│  UI_Slot                                    │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│  Framework.Managers.LocalizationManager     │
│  Inherits GameSystem, manages language       │
│  switching, audio language, font selection, │
│  text label parsing, and other game logic   │
└─────────────────────────────────────────────┘
```

> **Note**: `I2.Loc.LocalizationManager` and `Framework.Managers.LocalizationManager` are two completely different classes. The code often uses both simultaneously, so be sure to distinguish between them.

---

## I2.Loc.LocalizationManager (Third-party Library, Compiled to DLL)

**Static class**, from the I2 Localization plugin. Its full implementation is not visible in the Blasphemous source code (only `ScriptLocalization.cs` is compile-time generated).

Core API:

| Member | Description |
|------|------|
| `Sources` | `static List<LanguageSource>` — List of language sources, stores all translation data |
| `CurrentLanguage` | `static string` — Current language name |
| `CurrentLanguageCode` | `static string` — Current language code (e.g., `"en"`, `"zh"`) |
| `GetTranslation(string, ...)` | Core method for retrieving translated strings |
| `GetAllLanguages(bool)` | Gets all available language names |
| `GetAllLanguagesCode(bool, bool)` | Gets all available language codes |
| `GetLanguageFromCode(string, bool)` | Gets the language name from its code |
| `GetSupportedLanguage(string)` | Gets the supported language name |
| `AddSource(LanguageSource)` | Adds a language source |
| `OnLocalizeEvent` | `static event` — Language switching event |

### Key Modding Entry Points

```csharp
// Get the main language source
var source = I2.Loc.LocalizationManager.Sources[0];
// source.mLanguages — all language data
// source.GetTermData(key) — get a translation term
// source.AddTerm(key) — add a translation term
```

---

## I2.Loc.Localize (Third-party Library, Compiled to DLL)

`MonoBehaviour`, attached to `Text` / `TextMeshProUGUI` components, automatically updates text based on the current language.

Key fields:

| Field | Description |
|------|------|
| `Term` | Main translation term path (e.g., `"UI/ENABLED_TEXT"`) |
| `SecondaryTerm` | Secondary translation term path (e.g., `"UI/FONT_XXX"`, used for font switching) |
| `mTermSecondary` | Whether `SecondaryTerm` should also update with language changes |

In `CheckFonts.cs`, you can see that the game's UI text carries font information via the `SecondaryTerm` field of `Localize` (with the `"UI/FONT"` prefix).

---

## I2.Loc.ScriptLocalization

**File location**: `I2/Loc/ScriptLocalization.cs`

A compile-time generated static wrapper class that provides type-safe access to translated strings. Internally structured as multi-level nested static classes organized by UI module.

### ScriptLocalization.Get()

```csharp
// All properties ultimately call this core method
public static string Get(string Term,
    bool FixForRTL = true,
    int maxLineLengthForRTL = 0,
    bool ignoreRTLnumbers = true,
    bool applyParameters = false,
    GameObject localParametersRoot = null,
    string overrideLanguage = null)
{
    return LocalizationManager.GetTranslation(Term, FixForRTL, maxLineLengthForRTL,
        ignoreRTLnumbers, applyParameters, localParametersRoot, overrideLanguage);
}
```

### ScriptLocalization Nested Class Overview

| Nested Class | Line Range | Translation Key Prefix | Coverage |
|--------|---------|-----------|---------|
| `UI` | 16-58 | `UI/` | General UI: ENABLED_TEXT, DISABLED_TEXT, GET_GUILTDROP_TEXT, ISIDORA_MENU_FORBIDDEN |
| `UI_BossRush` | 60-213 | `UI_BossRush/` | Boss Rush mode: COURSE_A/B/C/D_X, completion/failure suffix, unlock hints |
| `UI_Extras` | 214-257 | `UI_Extras/` | Extra content: background image labels BACKGROUND_0~3_LABEL |
| `UI_Inventory` | 258-441 | `UI_Inventory/` | Inventory: item acquisition hints, door operation prompts, equip/use labels, etc. |
| `UI_Map` | 442-515 | `UI_Map/` | Map and settings: video settings (Window/Fullscreen/Zoom/Pixel Perfect), button labels |
| `UI_Penitences` | 516-629 | `UI_Penitences/` | Penitence mode: PE series penalty/reward information |
| `UI_Slot` | 630-642 | `UI_Slot/` | Save slot information |

Each nested class's properties are `static string` (read-only getter), directly compiled into `ScriptLocalization.Get("prefix/KEY")` calls.

---

## Framework.Managers.LocalizationManager

**File location**: `Framework/Managers/LocalizationManager.cs`

**Inherits**: `GameSystem` (Framework core system base class)

Blasphemous's own localization manager. The difference from `I2.Loc.LocalizationManager` is that it handles game-specific logic: Steam language detection, audio language switching, per-language font selection, tag parsing (`[ICON:]` / `[ACT:]`), parameter substitution, etc.

### Initialization Flow

```csharp
Initialize() → WaitForCoreAnContinue()
    → Wait for Core.ready → Attempt to read user settings file
    → If reading fails, SteamLanguageChange()
```

`SteamLanguageChange()` maps Steam's language strings (`"spanish"`, `"schinese"`, etc.) to I2 language codes (`"es"`, `"zh"`, etc.) and sets the language via `Core.Localization`.

Supported language mapping:
| Steam Name | I2 Code |
|-----------|--------|
| spanish | es |
| english | en |
| french | fr |
| german | de |
| italian | it |
| schinese | zh |
| tchinese | zh |
| russian | ru |
| japanese | ja |
| brazilian | pt-BR |

### Core Methods

| Method | Description |
|------|------|
| `Initialize()` | Entry point, starts a coroutine to wait for Core to be ready, then initializes language |
| `SteamLanguageChange()` | Sets I2 language based on Steam language |
| `GetMainLanguageSource()` | `static`, returns `Sources[0]` |
| `SetNextLanguage()` | Switches to the next enabled language (cyclic) |
| `SetLanguageByIdx(int)` | Sets language by index |
| `GetCurrentLanguageIndex()` | Gets the current language index |
| `GetCurrentLanguageCode()` | Gets the current language code |
| `GetLanguageCodeByIndex(int)` | Gets language code by index |
| `GetLanguageNameByIndex(int)` | Gets language name by index |
| `GetIndexByLanguageCode(string)` | Finds index by code |
| `GetFontByLanguageName(string)` | Gets the corresponding font for a language (looked up from GameConstants) |
| `GetAllEnabledLanguagesNames()` | Gets all enabled language names |
| `GetAllEnabledLanguages()` | `List<LanguageData>`, gets full data for all enabled languages |
| `AddLanguageSource(string)` | Loads a LanguageSource via Resources and registers it into Sources |
| `Get(string key)` | Gets translation (wraps I2 translation, returns `[!LOC_KEY]` notation if not found) |
| `ParseMeshPro(...)` | `static`, parses tags in text (`[ICON:xxx]`, `[ACT:xxx]`) into rich text |
| `GetValueWithParam(string, string, string)` | Single parameter substitution (`{[key]}` → value) |
| `GetValueWithParams(string, Dictionary<string,string>)` | Multi-parameter substitution |

### Text Tag System

Special tags parsed by the `ParseMeshPro()` method:

| Tag Format | Description |
|---------|------|
| `[ICON:name]` | Inline icon sprite (looks up `ICON_name` from TMP_SpriteAsset) |
| `[ACT:action]` | Action button icon (selects `KB_`/`PS_`/`XBOX_`/`SWITCH_` prefix based on current controller type) |
| `[VAR:name]` | Variable substitution (not implemented, logs a warning) |

### Audio Language

`Framework.Managers.LocalizationManager` additionally manages audio language (voice), independent of text language:

| Member | Description |
|------|------|
| `AudioLanguages` | `List<string>` → `{"English", "Spanish"}` |
| `AudioLanguagesKeys` | `static List<string>` → `{"EN", "ES"}` |
| `CurrentAudioLanguageIndex` | Current audio language index (triggers `OnLocalizeAudioEvent` on switch) |
| `GetAllAudioLanguagesNames()` | Gets all audio language names |
| `GetCurrentAudioLanguageCode()` | Gets the current audio language code |
| `GetCurrentAudioLanguage()` | Gets the current audio language name |
| `OnLocalizeAudioEvent` | `static event OnLocalizeCallback` — Audio language switching event |

### Delegate

```csharp
public delegate void OnLocalizeCallback(string languageKey);
```

### Private Fields

| Field | Description |
|------|------|
| `currentId` | `static string` — The localization key ID currently being processed by ParseMeshPro |
| `currentTextMeshProFont` | `static TextMeshProUGUI` — Current font context for ParseMeshPro |
| `_cachedIconData` | `static TMP_SpriteAsset` — Cached icon sprite asset |
| `currentAudioLanguageIndex` | Current audio language index |

---

## GameConstants (Localization-related Configuration)

**File location**: `Framework/FrameworkCore/GameConstants.cs`

`static class GameConstants` contains localization-related static configuration:

| Field | Type | Value |
|------|------|----|
| `LanguageLineSpacingFactor` | `Dictionary<string, float>` | `{"ja": 1.2f}` — Legacy Text line spacing multiplier |
| `LanguageLineSpacingTextPro` | `Dictionary<string, float>` | `{"ja": 4f}` — TextMeshPro line spacing increment |
| `DefaultFont` | `string` | `"Majestic"` — Default font name |
| `FontByLanguages` | `Dictionary<string, string>` | `{"Russian":"RussianFont", "Chinese":"MSJhengHei", "Japanese":"KH-Dot", "Korean":"NeoDunggeunmo"}` |

---

## Gameplay/UI/FontsByLanguage.cs

**File location**: `Gameplay/UI/FontsByLanguage.cs`

`[Serializable]` struct that defines the mapping between language and font:

```csharp
public struct FontsByLanguage
{
    public string languageCode;  // Language code
    public Font font;            // Corresponding font
}
```

It is included in UIController's `fontsByLanguages` list and is used to switch the global font at runtime based on the language.

---

## Tools/DataContainer/LocalizationSpacingData.cs

**File location**: `Tools/DataContainer/LocalizationSpacingData.cs`

`ScriptableObject` (`CreateAssetMenu(menuName = "Blasphemous/Localization Spacing Data")`), defines per-language character spacing configuration.

| Field | Description |
|------|------|
| `Language` | Language name (Odin `[ValueDropdown("MyLanguages")]` dropdown) |
| `extraSpacing` | Extra character spacing |
| `extraAfterSpacing` | Extra trailing spacing |
| `verticalSpacing` | Vertical line spacing |
| `addCharacterWidth` | Whether to add character width |

The `MyLanguages()` method retrieves all language names from `LocalizationManager.GetAllLanguages(true)` as dropdown options.

---

## LanguageLineSpacing.cs

**File location**: `LanguageLineSpacing.cs`

`MonoBehaviour`, attached to UI text objects, automatically adjusts line spacing on language switching.

- In `Start()`, gets the original lineSpacing of the `Text` or `TextMeshProUGUI` component
- Subscribes to `I2.Loc.LocalizationManager.OnLocalizeEvent`
- In `OnLocalize()`, looks up the spacing factor for the current language from `GameConstants` and applies it
- In `OnDestroy()`, unsubscribes from the event

---

## Tools/DataContainer/TimeLocalization.cs

**File location**: `Tools/DataContainer/TimeLocalization.cs`

`[Serializable]` simple data class that defines time-related localization parameters:

| Field | Description |
|------|------|
| `from` | Start value |
| `to` | End value |

---

## ZonesLocalization.cs

**File location**: `ZonesLocalization.cs`

`MonoBehaviour` (editor tool), used to automatically generate zone localization keys.

- `source` field: References a `LanguageSource` asset
- `GenerateLocalization()`: Scans root objects named `D??` and their child `Z??` objects in the scene, automatically creates translation terms in the format `Map/DXX` and `Map/DXX_ZYY`
- `CreateTermIfNeeded(string key, string cad)`: Adds a term if it doesn't exist, and fills the same text for all languages

---

## ILocalizable.cs

**File location**: `ILocalizable.cs`

Interface that defines the base method for retrieving a translation ID:

```csharp
public interface ILocalizable
{
    string GetBaseTranslationID();
}
```

`BaseInventoryObject` implements this interface.

---

## CheckFonts.cs

**File location**: `CheckFonts.cs`

`MonoBehaviour` (editor tool), used to inspect and fix font usage issues in the game. Provides the following button methods:

| Method | Description |
|------|------|
| `CheckChild()` | Checks font consistency of Legacy Text in child objects |
| `CheckAll()` | Checks global Legacy Text font consistency |
| `CheckChildTextMesh()` | Checks font consistency of TextMeshPro in child objects |
| `CheckAllTextMesh()` | Checks global TextMeshPro font consistency |
| `CheckLocalizationChild()` | Checks if `Localize` components on child objects are missing the `"UI/FONT"` prefix in their SecondaryTerm |
| `CheckLocalizationAll()` | Globally checks `Localize`'s SecondaryTerm |

The logic of `CheckLocalizationInternal()` is particularly important: it iterates through `Text` components, checks whether a `Localize` component is attached, and whether `Localize.SecondaryTerm` starts with `"UI/FONT"` (the standard practice for font localization).

| Field | Description |
|------|------|
| `goodFont` | Target correct font (Legacy) |
| `goodFontPro` | Target correct font (SDF) |
| `fontsToChange` | List of fonts that can be automatically replaced |
| `showNames` | Whether to output detailed paths |
| `changePro` | Whether to automatically replace TextMeshPro fonts |

---

## Gameplay/UI/Console/LanguageCommand.cs

**File location**: `Gameplay/UI/Console/LanguageCommand.cs`

Console command `language`, inherits `ConsoleCommand`. Provides sub-commands:

| Sub-command | Description |
|--------|------|
| `language help` | Shows help |
| `language list` | Lists all available languages |
| `language current` | Shows the current language |
| `language set <CODE>` | Sets the language (e.g., `language set zh`) |

Implemented using the `I2.Loc.LocalizationManager` API.

---

## Key Modding Entry Points Summary

| Entry Point | Code | Usage |
|------|------|------|
| Get language source | `I2.Loc.LocalizationManager.Sources[0]` | Access/modify all translation data |
| Get translation term | `source.GetTermData("UI/KEY")` | Read a specific translation TermData |
| Add translation term | `source.AddTerm("UI/NEW_KEY")` | Dynamically add a new translation key |
| Current language code | `I2.Loc.LocalizationManager.CurrentLanguageCode` | Get/set the current language |
| Language switch event | `I2.Loc.LocalizationManager.OnLocalizeEvent` | Subscribe to language change notifications |
| Audio language event | `Framework.Managers.LocalizationManager.OnLocalizeAudioEvent` | Subscribe to audio language changes |
| Get translated string | `Core.Localization.Get("key")` | Get translation through the game's own manager |
| Font lookup | `Core.Localization.GetFontByLanguageName("Chinese")` | Get font by language name |
| Add LanguageSource | `Core.Localization.AddLanguageSource("SourcePrefabName")` | Dynamically load a language source |

### Example: Adding Custom Translations

```csharp
var source = I2.Loc.LocalizationManager.Sources[0];
var term = source.GetTermData("MY_MOD/MY_KEY");
if (term == null)
    term = source.AddTerm("MY_MOD/MY_KEY");
// Set translations for each language
int enIdx = source.GetLanguageIndex("English");
int zhIdx = source.GetLanguageIndex("Chinese");
term.Languages[enIdx] = "Hello World";
term.Languages[zhIdx] = "你好世界";
```

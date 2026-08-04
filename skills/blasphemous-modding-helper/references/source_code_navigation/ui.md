# UI

Complete navigation of the Blasphemous UI System. `UIController.instance` is the global singleton entry point, managing all interface switching, fade transitions, and UI widget references. The `UIScreens` enum defines switchable UI screens.

## Core Design Patterns

1. Entry: `UIController.instance` singleton + `UIScreens` enum
2. Widgets inherit `UIWidget` (CanvasGroup only); screen logic lives in `MenuLogic/`
3. HUD components in `UIGameLogic/` (health bar, fervour bar, flasks, etc.)
4. Console: `ConsoleCommand` base class + ~40 commands

---

## Core Entry Point

- **UIController.cs** - Global UI management singleton (`UIController.instance`). Manages the UI stack, screen transitions, fade animations, and event system references. Contains direct reference fields to all UI Widgets and MenuLogic.
- **UIScreens.cs** - Enum: `Gameplay`, `Configuration`, `DeadScreen`, `IngameMenu`, `EndScreen`, `Inventory`
- **FontsByLanguage.cs** - Multi-language font mapping configuration
- **AttrackMode.cs** - Attract mode / demo mode auto-loop playback logic

---

## Widgets

All Widgets inherit from `UIWidget` (which only contains a CanvasGroup component).

- **UIWidget.cs** - Base class for all Widgets, only `RequireComponent(typeof(CanvasGroup))`, no additional logic
- **FadeWidget.cs** - Full-screen fade in/out controller. Events: `OnFadeShowStart/End`, `OnFadeHidedStart/End`
- **ConsoleWidget.cs** - Development debug console UI. Manages all `ConsoleCommand` instances, handles input parsing and command execution. Listens to `SpawnManager.OnPlayerSpawn` to initialize command list
- **CreditsWidget.cs** - Credits scrolling playback
- **EndScreenWidget.cs** - Game ending/clear screen
- **GameplayWidget.cs** - In-game HUD container, manages UIGameLogic components such as health bar, fervour bar, flasks, etc.
- **GlowWidget.cs** - UI glow effects
- **HideUIOnCommand.cs** - Show/hide UI based on console commands
- **DebugInformation.cs** - Screen debug information overlay
- **CinematicBars.cs** - Cinematic letterbox bars (top and bottom)
- **CustomScrollBar.cs** - Custom scrollbar control
- **SaveSlot.cs** - Save slot UI component, displays save information

---

## Others/MenuLogic/

Menu logic classes, providing full behavioral control for each menu screen.

- **MainMenu.cs** - Old / original main menu implementation
- **MainMenuLauncher.cs** - Main menu launcher, points to NewMainMenu
- **NewMainMenu.cs** - New main menu UI implementation
- **Landing.cs** - Landing / splash screen before the main menu
- **PauseWidget.cs** - Pause menu
- **InGameMenuWidget.cs** - In-game menu (shown when paused)
- **GameMenu.cs** - Game menu base class
- **ConfigurationWidget.cs** - Settings / configuration menu (controls, video, audio, etc.)
- **InventoryWidget.cs** - Legacy inventory screen
- **InventoryMessages.cs** - Inventory system message definitions
- **Inventory_GridItem.cs** - Legacy inventory grid item
- **Inventory_PrayerItem.cs** - Legacy inventory prayer item
- **NewInventoryWidget.cs** - New inventory main screen
- **NewInventory_Description.cs** - New inventory item description panel
- **NewInventory_GridItem.cs** - New inventory grid item component
- **NewInventory_Layout.cs** - New inventory layout control
- **NewInventory_LayoutGrid.cs** - New inventory grid layout
- **NewInventory_LayoutSkill.cs** - New inventory skill tab layout
- **NewInventory_LayoutStatus.cs** - New inventory status tab layout
- **NewInventory_Skill.cs** - New inventory skill item component
- **MapMenuWidget.cs** - Map menu (legacy)
- **NewMapMenuWidget.cs** - New map menu
- **OptionsWidget.cs** - Options menu
- **AlmsWidget.cs** - Church alms / donation screen
- **BossRushWidget.cs** - Boss Rush mode main screen
- **BossRushRankWidget.cs** - Boss Rush ranking / medal display
- **ConfirmationWidget.cs** - Generic confirmation dialog
- **PopUpWidget.cs** - Generic popup notification
- **PopupAchievementWidget.cs** - Achievement unlock popup
- **KneelPopUpWidget.cs** - Kneel interaction popup (shrine/save point)
- **PatchNotesWidget.cs** - Patch notes / update log display
- **QuoteWidget.cs** - Quote / saying display screen
- **SelectSaveSlots.cs** - Save selection screen
- **ChoosePenitenceWidget.cs** - Choose penitence / penance mode screen
- **AbandonPenitenceWidget.cs** - Abandon penitence confirmation screen
- **ModeUnlockedWidget.cs** - Mode unlock notification popup
- **AchievementElementWidget.cs** - Individual achievement entry in the achievement list
- **UpgradeFlasksWidget.cs** - Upgrade flasks screen
- **ExtrasMenuWidget.cs** - Extras menu (artbook, music, etc.)
- **IntroDemakeWidget.cs** - Demake mode intro cutscene
- **AttrackModeVideo.cs** - Attract mode video playback
- **BasicUIBlockingWidget.cs** - Blocking UI base component
- **SelectableOption.cs** - Selectable option component
- **RankMedal.cs** - Ranking medal UI component
- **Escape.cs** - Back/exit key handling
- **ImportGamepadClose.cs** - Gamepad import close prompt
- **ImportSuccess.cs** - Import success prompt
- **CustomScrollView.cs** - Custom scrollable view
- **FixedScrollBar.cs** - Fixed scrollbar
- **CustomEventInput.cs** - Custom event input handling
- **EventInputSwitcher.cs** - Input event switching / control mapping switching
- **KeepFocus.cs** - UI focus keeping utility class

---

## Others/UIGameLogic/

In-game HUD logic components, displayed on the Gameplay screen.

- **BossHealth.cs** - Boss health bar display
- **PlayerHealth.cs** - Player health bar (standard mode)
- **PlayerHealthDemake.cs** - Demake mode player health display
- **PlayerHealthPE02.cs** - PE02 special health display variant
- **PlayerFervour.cs** - Player fervour bar display
- **PlayerFlask.cs** - Flask count display
- **PlayerGuiltPanel.cs** - Player guilt panel
- **PlayerPurgePoints.cs** - Purge points display
- **InteractionSignal.cs** - Interaction prompt signal (interactable object prompt)
- **MiriamTimer.cs** - Miriam challenge timer
- **BossRushTimer.cs** - Boss Rush mode timer
- **PadButton.cs** - Gamepad button prompt icon
- **PlayerDecipher.cs** - Decipher / decryption progress prompt

---

## Console/

Development console commands (~40 commands), all inheriting from the `ConsoleCommand` base class. Press a key (usually ~ or F1) in-game to open the console input.

- **ConsoleCommand.cs** - Command base class. Provides virtual methods: `Execute(command, parameters)`, `GetName()`, `Initialize(console)`, `Update()`
- **Help.cs** - `help` - List all commands or get help for a specific command
- **AchievementCommand.cs** - `achievement` - Achievement-related operations
- **AlmsCommand.cs** - `alms` - Alms / donation related
- **AudioCommand.cs** - `audio` - Audio debugging
- **BonusCommand.cs** - `bonus` - Bonus content / rewards
- **BossRushCommand.cs** - `bossrush` - Boss Rush mode control
- **CameraCommand.cs** - `camera` - Camera debugging
- **CompletionCommand.cs** - `completion` - Completion percentage related
- **DebugCommand.cs** - `debug` - General debug commands
- **DebugUICommand.cs** - `debugui` - Debug UI toggle
- **DemakeCommand.cs** - `demake` - Demake mode toggle
- **DialogCommand.cs** - `dialog` - Dialog system debugging
- **ExecutionCommand.cs** - `execution` - Execution related
- **ExitCommand.cs** - `exit` - Exit console
- **FervourRefill.cs** - `fervourrefill` - Refill fervour
- **FlagCommand.cs** - `flag` - Game flag setting/viewing
- **GameModeCommand.cs** - `gamemode` - Game mode switching
- **Graybox.cs** - `graybox` - Graybox / development visualization
- **GuiltCommand.cs** - `guilt` - Guilt value operations
- **InventoryCommand.cs** - `inventory` - Inventory item operations
- **Invincible.cs** - `invincible` - Invincibility toggle
- **Kill.cs** - `kill` - Kill all/specific enemies
- **LanguageCommand.cs** - `language` - Language switching
- **LoadLevel.cs** - `loadlevel` - Directly load a level scene
- **MapCommand.cs** - `map` - Map related
- **MaxFervour.cs** - `maxfervour` - Set max fervour
- **MiriamCommand.cs** - `miriam` - Miriam challenge control
- **Npcoff.cs** - `npcoff` - NPC disable
- **PenitenceCommand.cs** - `penitence` - Penitence / penance mode
- **Restart.cs** - `restart` - Restart game
- **SaveGameCommand.cs** - `savegame` - Save game operations
- **SendEvent.cs** - `sendevent` - Send game event
- **SharedCommandsCommand.cs** - `sharedcommands` - Shared command management
- **ShowUICommand.cs** - `showui` - UI show/hide
- **SkillCommand.cs** - `skill` - Skill-related operations
- **SkinCommand.cs** - `skin` - Skin switching
- **StatsCommand.cs** - `stats` - Stats viewing
- **TeleportCommand.cs** - `teleport` - Teleport
- **TestPlanCommand.cs** - `testplan` - Test plan execution
- **TimescaleCommand.cs** - `timescale` - Time scale
- **TutorialsCommand.cs** - `tutorials` - Tutorial reset/trigger

---

## PixelPerfect/

Pixel-perfect rendering related components.

- **VirtualCanvasScaler.cs** - Virtual Canvas scaler, implementing pixel-perfect scaling
- **ScreenResizer.cs** - Screen size adapter, handling letterboxing/expansion across different resolutions

---

## Others/Buttons/

UI button components.

- **UIButtonsFX.cs** - UI button sound effect / FX playback
- **TLDButton.cs** - TLD-style button
- **RestartButton.cs** - Restart button
- **MenuButton.cs** - Generic menu button
- **EventsButton.cs** - Event-triggered button
- **DeadScreenWidget.cs** - Death screen UI (includes buttons)
- **ControlRemapButton.cs** - Control remapping button
- **ButtonColor.cs** - Button color management
- **BossRushButton.cs** - Boss Rush button

---

## Others/Screen/

Ending screen related components.

- **SlideShow.cs** - Slideshow playback (cutscenes/endings)
- **EndScreenTitle.cs** - Ending screen title
- **EndScreenBody.cs** - Ending screen body text

---

## Others/Disclaimer/

Disclaimer / opening prompts.

- **Disclaimer.cs** - Disclaimer / health warning screen
- **DisclaimerText.cs** - Disclaimer text content

---

## Others/UIGameEditor/

UI helper tools in the scene editor.

- **ClimbPreview.cs** - Climb detection visual preview (displays wall-climb detection range in editor)
- **PixelPivot.cs** - Pixel alignment pivot tool

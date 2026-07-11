# Blasphemous Source Code Navigation Guide

Blasphemous source code full navigation. All paths are relative to `Assembly-CSharp/`.

---

## Source Code Structure Overview

| Top-level Directory | Description | Navigation Document |
|---------|------|---------|
| `Framework/` | Core Framework, Managers, Attributes, Inventory, Maps, DLC |  |
| `Gameplay/` | Gameplay: Bosses, Enemies, Player, UI, Animation |  |
| `Tools/` | Tools/Utilities: Level, PlayMaker, Audio, NPC, Items |  |
| `Extras/` | Epic Online Services (EOS) Integrations |  |
| `I2/` | I2 Localization Framework |  |
| `VisualEffects/` | Screen color palette |  |
| `Effects/` | Blood particle fix tool |  |
| `HutongGames/` | PlayMaker Custom Actions |  |
| `TPO_FOLLOWER_PROTOTYPE/` | TPO Follower Prototype |  |
| Root `.cs` files | Miscellaneous tools, traps, effects, UI components, etc. |  |

---

## Navigation Document Index

| Section | Description | Document |
|---------|-------------|----------|
| Core | Core Framework: Managers, Attributes, Audio, Dialog, Map, Penitences, BossRush, DLC, Pooling, Util, Achievements | [core.md](core.md) |
| Player | Player Penitent: Abilities, Attacks, Movement, Input, Animation, Prayers, State Machine | [player.md](player.md) |
| Enemy | Enemy System: All enemy types, AI Framework, Entity Base Classes | [enemy.md](enemy.md) |
| Bosses | Boss System: All Boss types, BossFightManager, Common Attacks | [bosses.md](bosses.md) |
| UI | UI System: UIController, Widgets, MenuLogic, HUD, Console | [ui.md](ui.md) |
| Items | Item/Equipment System: Inventory item types, Effect System, Achievements | [items.md](items.md) |
| Level | Level/Environment: Actionables, Interactables, Layout, Teleport | [level.md](level.md) |
| Tools | Tool Set: PlayMaker Actions/Conditions/Events, Audio, Data Containers, NPC | [tools.md](tools.md) |
| Localization | Localization System: I2.Loc, Blasphemous's own LocalizationManager | [localization.md](localization.md) |

---

## Quick Access for Mod Development

| Entry Point | Description |
|------|------|
| `Core.Instance` | Global framework singleton |
| `Core.Logic` | LogicManager, game logic core |
| `Core.Logic.Penitent` | Player Penitent instance |
| `Core.Events` | EventManager, Flag/Event system |
| `Core.Input` | InputManager, input management |
| `Core.LevelManager` | Level loading |
| `Core.Persistence` | Save system |
| `Core.InventoryManager` | Inventory system |
| `Core.SkillManager` | Skill system |
| `Core.AudioManager` | Audio management |
| `Core.DialogManager` | Dialog system |
| `Core.ColorPaletteManager` | Color palette management |
| `UIController.instance` | UI system singleton |

---

## Common Namespaces

| Namespace | Description |
|---------|------|
| `Framework.Managers` | All core Manager classes |
| `Framework.FrameworkCore` | Attribute system, entity states, abilities |
| `Framework.Inventory` | Item/Equipment/Effect system |
| `Gameplay.GameControllers.Penitent` | All Player-related |
| `Gameplay.GameControllers.Enemies` | All Enemy-related |
| `Gameplay.GameControllers.Bosses` | All Boss-related |
| `Gameplay.GameControllers.Entities` | Entity Base Classes (Entity, Enemy, Hit, Attack) |
| `Gameplay.GameControllers.Camera` | Camera System |
| `Gameplay.UI` | All UI-related |
| `I2.Loc` | I2 Localization Framework |
| `Tools.Playmaker2` | PlayMaker Custom Actions |

---

## Find by Feature

- **Player Actions** → [player.md](player.md) (Penitent, Abilities, Input)
- **Enemy AI** → [enemy.md](enemy.md) (EnemyBehaviour, EnemyAI)
- **Boss Combat** → [bosses.md](bosses.md) (BossFightManager, BossBehaviour)
- **Item Effects** → [items.md](items.md) (ObjectEffect, RelicEffect, RosaryBead)
- **UI Screens** → [ui.md](ui.md) (UIController, Widgets, MenuLogic)
- **Level Mechanics** → [level.md](level.md) (Actionables, Interactables, Teleport)
- **Story Events** → [core.md](core.md) (EventManager, DialogManager)
- **Save System** → [core.md](core.md) (PersistentManager)
- **Localization / Translation** → [localization.md](localization.md)
- **PlayMaker Scripts** → [tools.md](tools.md) (Playmaker2/Action, Condition, Events)
- **Console Commands** → [ui.md](ui.md) (Console/)

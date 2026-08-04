# Items / Inventory / Equipment

Item / inventory / equipment / effect / achievement source code navigation in Blasphemous.

## Core Design Patterns

1. Three-layer item model: `BaseElement` (ScriptableObject data) → `BaseInventoryObject` (MonoBehaviour behaviour) → concrete type
2. `ObjectEffect` is the core effect base class; `EffectType` / `ConditionType` enums control trigger timing and conditions
3. Achievement progress accumulates automatically via `Add()` and other hooks (fixed percentages per type, e.g. AC16–AC20)
4. Equippables: `EquipableInventoryObject` (Equip/UnEquip/Use → SendMessage events)

---

## Item Types

### Framework/Inventory/BaseElement.cs
`ScriptableObject` — Base class for item data (pure data container). Contains `id`, `caption`, `description`, `lore`, `picture`, `carryonstart` fields. Inherited by `BaseInventoryObject`.

### Framework/Inventory/BaseInventoryObject.cs
Abstract `MonoBehaviour`, implements `ILocalizable` — Base class for all inventory item behaviors. Core properties: `IsOwned`, `id`, `caption`, `description`, `lore`, `picture`, `carryonstart`, `preserveInNewGamePlus`. Core methods: `Add()` (triggers AC16-AC20 achievement progress), `Remove()`, `Reset()`, `HitEnemy(Hit)`, `KillEnemy(Enemy)`, `HitReceived(Hit)`, `PenitentHealthChanged(float)`, `BreakableBreak(BreakableObject)`, `PenitentDead()`, `NumberOfCurrentFlasksChanged(float)`. Abstract methods: `GetItemType()`.

### Framework/Inventory/EquipableInventoryObject.cs
Inherits `BaseInventoryObject` — Abstract base class for equippable items. Provides `IsEquiped`, `Equip()` (→ SendMessage "OnEquipInventoryObject"), `UnEquip()` (→ "OnUnEquipInventoryObject"), `Use()` (→ "OnUseInventoryObject"). `IsEquipable()` returns true. `UsePercentageCompletition` controls whether it counts toward completion percentage.

### Framework/Inventory/CollectibleItem.cs
`ItemType.Collectible` — Collectibles (bones, etc.). `ClaimedInOssuary` property persisted via flag. `HasLore()` returns false. Each collectible contributes 2.27% to AC19 progress.

### Framework/Inventory/Sword.cs
`ItemType.Sword` — Sword Heart. Static `Id` class defines "HE01" (SteamingIncenseHeart). Each Sword Heart contributes 11.11% to AC20 progress.

### Framework/Inventory/Prayer.cs
`ItemType.Prayer` — Prayers. `PrayerType` enum: `Laments` / `Thanksgiving` / `Hymn`. `decipherMax`, `fervourNeeded` (default 20) control prayer strength. `CurrentDecipher` / `AddDecipher(int)` system. `EffectTime` auto-calculated on Awake (max EffectTime of all OnUse ObjectEffects with LimitTime). Each prayer contributes 7.69% to AC16 progress.

### Framework/Inventory/RosaryBead.cs
`ItemType.Bead` — Rosary Beads. Static `Id` class defines multiple RB IDs (`RB01` PigeonSkull, `RB04` UvulaProclamation, `RB05` HollowPearl, `RB06` BallOfHair, `RB10` FrozenOlive, `RB17-19` RedWax, `RB22` LimestoneRingFinger, `RB24-26` BlueWax, `RB28` PelicanEffigy). Each bead contributes 3.33% to AC18 progress.

### Framework/Inventory/Relic.cs
`ItemType.Relic` — Relics. Each relic contributes 14.28% to AC17 progress. Used with `RelicEffect` component (requires `[RequireComponent(typeof(Relic))]`).

### Framework/Inventory/QuestItem.cs
`ItemType.Quest` — Quest items, not equippable.

### Framework/Inventory/TearsObject.cs
`ItemType.Quest` (reused) — Tears items. `TearsForDuplicatedObject` tears amount when duplicated (default 1200f).

### Framework/Inventory/InteractableInvAdd.cs
`MonoBehaviour` — Scene interaction component, adds any item type to inventory via `OnUsePost()` and saves.

### Framework/Inventory/InteractableInventoryAdd.cs
`MonoBehaviour` — Same as above (variant), functionally identical.

### Framework/Inventory/InteractableInventoryAddQuestItem.cs
`MonoBehaviour` — Deprecated quest item addition component (warning: `¡Este componente está deprecado!! Usa InteractableInvAdd.`). Uses `[InventoryId(ItemType.Quest)]` attribute filter.

### Framework/Inventory/InteractableInventoryShowUnlockSkills.cs
`MonoBehaviour` — Opens unlockable skill UI on interaction (`UIController.ShowUnlockSKill()`).

---

## Effect System

### Framework/Inventory/ObjectEffect.cs
`MonoBehaviour` (`[RequireComponent(typeof(BaseInventoryObject))]`) — **Core base class for all item effects**.

`EffectType` enum defines trigger timings: `OnEquip`, `OnUse` (Prayer only), `OnHitEnemy`, `OnInitialization`, `OnUpdate`, `OnHitReceived`, `OnceOnTimer`, `OnBreakBreakable`, `OnKillEnemy`, `OnAdquisition`, `OnPenitentDead`, `OnAbilityCast`.

Key properties: `LimitTime` / `EffectTime`, `TriggerOnlyOnce`, `PingTime` (polling interval for continuous effects), `OnlyWhenUsingPrayer`, `percentToExecute` (probability trigger), `UsePrayerDurationAddition`, `UseWhenCastingPrayer`.

`ConditionType` enum (trigger conditions): `WhenLifeUnderPercent`, `WhenExecutionDone`, `WhenHeavyAttackDone`, `WhenDamageReceived`, `WhenNoFlasksLeft`. `Conditions` / `StoppingConditions` lists control effect enable/disable.

Overridable methods: `OnAwake()`, `OnStart()`, `OnUpdate()`, `OnApplyEffect()`, `OnRemoveEffect()`, `OnDispose()`.

### Framework/Inventory/ObjectEffect_Stat.cs
Inherits `ObjectEffect` — Modifies player attribute values. `EffectMode` enum: `Bonus` (RawBonus) / `Current` (direct add/subtract). `ValueType` enum: `Value` (fixed), `BasedOnCurrentStat`, `BasedOnMaxStat`. `statType` specifies target attribute. `UseHitAsBaseValue` for OnHit effects based on damage amount.

### Framework/Inventory/RelicEffect.cs
`MonoBehaviour` (`[RequireComponent(typeof(Relic))]`) — Base class for relic effects. Virtual methods: `OnEquipEffect()` / `OnUnEquipEffect()`.

---

### Effect Subclass Overview

#### Rosary Bead Effects (Framework/Inventory/)
| File | Base Class | Notes |
|------|------|------|
| BidirectionalParryBeadEffect.cs | ObjectEffect | Bidirectional parry bead |
| CloisteredGemBeadEffect.cs | ObjectEffect | Cloistered gem bead effect (used with `RubyOfWiseMen`/`EmeraldOfTheWiseMen`) |
| HardLandingBeadEffect.cs | ObjectEffect | Hard landing damage reduction bead |
| IncreaseSpeedBeadEffect.cs | ObjectEffect | Speed increase bead (modifies `Dash.MoveSetting` and `PlatformCharacterController` speed) |
| QuickHealingBeadEffect.cs | ObjectEffect | Quick healing bead (modifies Animator's "HEALING_SPEED_MULTIPLIER") |

#### Prayer Effects (Framework/Inventory/)
| File | Base Class | Notes |
|------|------|------|
| HeavyAttackPrayerEffect.cs | ObjectEffect_Stat | Heavy attack prayer (sets `PenitentAttack.CurrentLevel=2` and `IsHeavyAttackPrayerEquipped`) |
| PrayerAlliedCherubEffect.cs | ObjectEffect_Stat | Allied cherub prayer (summons AlliedCherubPrayer) |
| PrayerGhostGuardian.cs | ObjectEffect | Ghost guardian prayer (instantiates GuardianPrayer) |
| PrayerMiriam.cs | ObjectEffect | Miriam prayer effect |
| PrayerShieldEffect.cs | ObjectEffect | Shield prayer effect |
| PrayerUseVfx.cs | ObjectEffect | Prayer use VFX |
| ProtectionDomeEffect.cs | ObjectEffect_Stat | Protection dome prayer (provides invulnerability within range, `MaxDistanceFromDome`) |
| ToxicCloudEffect.cs | ObjectEffect_Stat | Toxic cloud prayer (periodically spawns PoisonAreaEffect, damage affected by `PrayerStrengthMultiplier`) |
| ZambraTearsHarvestEffect.cs | ObjectEffect | Zambra tears harvest (`EffectType.OnBreakBreakable`, gain tears from breaking objects) |

#### Relic Effects (Framework/Inventory/)
| File | Base Class | Notes |
|------|------|------|
| CherubRelicEffect.cs | RelicEffect | Cherub relic (`CheckTrap.AvoidTrapDamage=true` when equipped, immune to trap damage) |
| IncreaseSpeedSwordHeartEffect.cs | ObjectEffect | Sword heart speed increase effect |
| PowerSlashesSwordHeartEffect.cs | ObjectEffect | Sword heart power slash effect |
| QuickAreaTransformBeadEffect.cs | ObjectEffect | Quick area transformation bead effect |

#### Special Item Effects (Tools/Items/)

**Penance Related:**
| File | Base Class | Notes |
|------|------|------|
| BloodPenitenceBeadEffect.cs | ObjectEffect | Blood penance bead (`Core.PenitenceManager.AddFlasksPassiveHealthRegen`) |
| GuiltPenitenceBeadEffect.cs | ObjectEffect | Guilt penance bead (`UseFervourFlasks=true`, checks PE03 on unequip) |

**Prayer Attack:**
| File | Base Class | Notes |
|------|------|------|
| StuntPrayerEffect.cs | ObjectEffect | Stun prayer (`BossAreaSummonAttack` summon) |
| PenitentAreaAttack.cs | ObjectEffect | Area attack prayer (`Physics2D.OverlapCircleNonAlloc` AOE) |
| PenitentCrawlerOrbsEffect.cs | ObjectEffect | Crawling orb prayer (`BossStraightProjectileAttack.Shoot` left/right shooting) |
| PenitentDivineLightEffect.cs | ObjectEffect | Divine light prayer (`BossAreaSummonAttack.SummonAreas`) |
| PenitentFlamePillarsEffect.cs | ObjectEffect | Flame pillar prayer |
| PenitentGuardianEffect.cs | ObjectEffect | Guardian prayer |
| PenitentLightBeamEffect.cs | ObjectEffect | Light beam prayer (vertical beam, `BossAreaSummonAttack`) |
| PenitentMultishotEffect.cs | ObjectEffect | Multishot prayer |
| PenitentTeleportToPriedieu.cs | ObjectEffect | Teleport to Priedieu (plays "RegresoAPuerto" animation) |
| PR203ElmFireLoopEffect.cs | ObjectEffect | Lightning loop prayer (`ElmFireTrapManager` serialized trap effects, multi-pulse damage, affected by `PrayerStrengthMultiplier` and `PrayerDurationAddition`) |

**Relic/Quest Item Effects:**
| File | Base Class | Notes |
|------|------|------|
| ChaliceEffect.cs | ObjectEffect | Chalice quest logic (listens to `SpawnManager.OnTeleport`, `Entity.Death` events, manages QI75→QI76→QI77 transition, clears on teleport/death) |
| DirtyNailRelicEffect.cs | RelicEffect | Dirty nail relic (disables all `MudAreaEffect`, except those marked with `unafectedByRelic`) |
| SilverLungRelicEffect.cs | RelicEffect | Silver lung relic (disables all `PoisonAreaEffect`) |
| FamiliarSpawnEffect.cs | ObjectEffect | Familiar spawn effect (`Instantiate(FamiliarPrefab)` and sets `Owner=Penitent`) |
| IncorruptHandBell.cs | ObjectEffect | **Incorrupt Hand Bell** — indicates distance to hidden walls via FMOD audio intensity and halo color/duration, updates every 3s, 5 intensity levels |
| IncorruptHandConfig.cs | struct | Incorrupt hand bell intensity config struct (`haloTransparency`, `haloDuration`) |

**General Effect Tools:**
| File | Base Class | Notes |
|------|------|------|
| ObjectEffect_ChangeItem.cs | ObjectEffect | Replaces current item with a new one (can auto-equip to same slot) |
| ItemAudio.cs | ObjectEffect | Plays FMOD audio effect |
| ItemFlag.cs | ObjectEffect | Sets/clears event Flag |
| ItemGhostTrail.cs | ObjectEffect | Enables/disables colored GhostTrail |
| ItemTemporalEffect.cs | ObjectEffect | **Temporary status effect** — `PenitentEffects` enum: `StopFervourRecolection` (stop fervour recollection), `Invulnerable` (invulnerable), `RedAttack` (red attack), `Level2Attack` (level 2 attack), `StopGuiltDrop` (no guilt drop), `DisableUnEquipSword` (disable sword unequip) |
| Invulnerability.cs | ObjectEffect | Invulnerability effect (empty OnApplyEffect/OnRemoveEffect, handled by parent class) |

---

## Achievement System

### Framework/Achievements/Achievement.cs
Serializable achievement class. Core properties: `Id`, `Progress` (0-100f), `Name`, `Description`, `Image`, `Status` (LOCKED/UNLOCKED/HIDDEN), `PreserveProgressInNewGamePlus`, `CanBeHidden`. Core methods: `AddProgress(float)`, `AddProgressSafeTo99(float)`, `Grant()`, `IsGranted()`. Localization keys are `Achievements/<Id>_NAME` / `_DESC`.

### Framework/Achievements/AchievementList.cs
`SerializedScriptableObject` — Achievement list container (`List<Achievement> achievementList`).

### Framework/Achievements/IAchievementsHelper.cs
Interface — `SetAchievementProgress(string id, float value)` / `GetAchievementProgress(string id, GetAchievementOperationEvent evt)`.

### Framework/Achievements/GetAchievementOperationEvent.cs
Delegate — `delegate void GetAchievementOperationEvent(string id, float value)`.

### Framework/Achievements/SteamAchievementsHelper.cs
`IAchievementsHelper` implementation — Steamworks SDK integration. Uses `SteamUserStats.SetAchievement` / `GetAchievement` for Steam achievements.

### Framework/Achievements/GogAchievementsHelper.cs
`IAchievementsHelper` implementation — GOG integration (empty implementation).

### Framework/Achievements/LocalAchievementsHelper.cs
`IAchievementsHelper` implementation — Local PlayerPrefs achievement storage. Also maintains `LocalAchievementsCache` (JSON file persistence), reads existing achievements from save slots.

### Framework/Achievements/AC39Enemies.cs
`SerializedScriptableObject` — AC39 (Mediterranean Diet) enemy list. Contains 51 enemy IDs (EN01-EN34, EV01-EV29).

### Framework/Achievements/AC44Checker.cs
`MonoBehaviour` — AC44 (Speedrun) checker. Checks game time on Start, grants AC44 if less than 180 minutes.

### Framework/Achievements/EnemyIdAndName.cs
Serializable struct — `id`, `name`, `hasAnotherName`, `otherName`. Used for AC39 enemy list.

---

## Special Item Tools

### Tools/Items/ItemAudio.cs
`ObjectEffect` subclass — Plays specified FMOD audio event on trigger.

### Tools/Items/ItemFlag.cs
`ObjectEffect` subclass — Sets `Core.Events.SetFlag` on apply/remove.

### Tools/Items/ItemGhostTrail.cs
`ObjectEffect` subclass — Enables player GhostTrail (`GhostTrailGenerator`) and sets color.

### Tools/Items/ItemTemporalEffect.cs
`ObjectEffect` subclass — Applies/removes multiple temporary player status effects (see Effect System section).

### Tools/Items/Invulnerability.cs
`ObjectEffect` subclass — Empty implementation of invulnerability effect (logic driven by parent OnEquip/OnUse events).

### Tools/Items/ObjectEffect_ChangeItem.cs
`ObjectEffect` subclass — Swaps current item with a new one (configurable add/auto-equip).

---

## Unlockable Skills

### Framework/FrameworkCore/UnlockableSkill.cs
`ScriptableObject` (`[CreateAssetMenu(menuName = "Blasphemous/Unlockable Skill")]`), implements `ILocalizable` — Skill tree node. Core properties: `id`, `caption`, `description`, `instructions`, `tier`, `cost` (default 500), `unlocked`, `parentSkill` (skill dependency chain). `GetParentSkill()` returns "NO DEPENDENCY" when no prerequisite is required.

---

## InventoryIdAttribute

### Framework/Inventory/InventoryIdAttribute.cs
`PropertyAttribute` — Unity editor attribute, used in Inspector to filter the item ID list of the specified `InventoryManager.ItemType`. Constructor takes an `InventoryManager.ItemType` parameter.

# Enemies — Enemy System Navigation

> Source Root: `Assembly-CSharp/`  
> Enemy Implementation: `Gameplay/GameControllers/Enemies/`  
> Entity Base Classes: `Gameplay/GameControllers/Entities/`  
> EntityStatus: `Framework/FrameworkCore/EntityStatus.cs`

> **Boss/Enemy 归属规则**:本文档覆盖 `Gameplay/GameControllers/Enemies/` 下的敌人与组件。Boss 主类一律在 `Gameplay/GameControllers/Bosses/` 下 → [bosses.md](bosses.md);位于 `Enemies/` 目录但由 Boss 系统驱动的实体(`MasterAnguish` 音频、`SingleAnguish` 动画)与 Boss 级敌人(`Menina`)仅在此列出组件,主类见行内 Notes;同名实体(Boss vs 小怪,如 `PontiffHusk`)以行内链接互相指认。

---

## Enemy List

### A ~ B

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| Acolyte | `Acolyte/Acolyte.cs` | `Acolyte/IA/AcolyteBehaviour.cs` | `Acolyte/AcolyteAttack.cs` | `Acolyte/Attack/AcolyteCandlestick.cs` | `Acolyte/Animator/AcolyteAnimatorInyector.cs` | `Acolyte/Audio/AcolyteAudio.cs` | Candle stick monk, melee |
| AshCharger | `AshCharger/AshCharger.cs` | `AshCharger/AI/AshChargerBehaviour.cs` | — | — | `AshCharger/Animator/AshChargerAnimatorInyector.cs` | `AshCharger/Audio/AshChargerAudio.cs` | Ash charger, multi-state AI |
| BellCarrier | `BellCarrier/BellCarrier.cs` | `BellCarrier/IA/BellCarrierBehaviour.cs` | `BellCarrier/Attack/BellCarrierAttack.cs` | `BellCarrier/Attack/BellCarrierWeapon.cs` | `BellCarrier/Animator/BellCarrierAnimatorInyector.cs` | `BellCarrier/Audio/BellCarrierAudio.cs` | Bell-carrying enemy |
| BellGhost | `BellGhost/BellGhost.cs` | `BellGhost/AI/BellGhostBehaviour.cs` | `BellGhost/Attack/BellGhostAttack.cs` `BellGhost/Attack/BellGhostVariantAttack.cs` | `BellGhost/Attack/BellGhostWeapon.cs` `BellGhost/ProjectileWeapon.cs` | `BellGhost/Animator/BellGhostAnimatorInyector.cs` | `BellGhost/Audio/BellGhostAudio.cs` | Bell ghost, has variant and tracking zone |
| Bishop | `Bishop/Bishop.cs` | `Bishop/AI/BishopBehaviour.cs` | `Bishop/Attack/BishopAttack.cs` | `Bishop/Attack/BishopSpear.cs` | `Bishop/Animation/BishopAnimatorInyector.cs` | `Bishop/Audio/BishopAudio.cs` | Bishop, spear-wielding |

### C ~ D

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| CauldronNun | `CauldronNun/CauldronNun.cs` | `CauldronNun/AI/CauldronNunBehaviour.cs` | `CauldronNun/Attack/CauldronNunAttack.cs` | — | `CauldronNun/Animator/CauldronNunAnimatorInyector.cs` | `CauldronNun/Audio/CauldronNunAudio.cs` | Cauldron nun |
| ChainedAngel | `ChainedAngel/ChainedAngel.cs` | `ChainedAngel/AI/ChainedAngelBehaviour.cs` | `ChainedAngel/Attack/ChainedAngelAttack.cs` | `ChainedAngel/Attack/ChainedAngelWeapon.cs` | `ChainedAngel/Animator/ChainedAngelAnimatorInjector.cs` | `ChainedAngel/Audio/ChainedAngelAudio.cs` | Chained angel, includes Attack/Idle state |
| ChasingHead | `ChasingHead/ChasingHead.cs` | `ChasingHead/AI/ChasingHeadBehaviour.cs` | `ChasingHead/Attack/ChasingHeadAttack.cs` `ChasingHead/Variation/ExplodingHeadAttack.cs` | `ChasingHead/Attack/ChasingHeadWeapon.cs` | `ChasingHead/Animator/ChasingHeadAnimatorInyector.cs` | `ChasingHead/Audio/ChasingHeadAudio.cs` | Chasing head, includes exploding variant |
| ChimeRinger | `ChimeRinger/ChimeRinger.cs` | `ChimeRinger/AI/ChimeRingerBehaviour.cs` | `ChimeRinger/Attack/ChimeRingerAttack.cs` | — | `ChimeRinger/Animator/ChimeRingerAnimatorInyector.cs` | `ChimeRinger/Audio/ChimeRingerAudio.cs` | Chime ringer |
| CowardTrapper | `CowardTrapper/CowardTrapper.cs` | `CowardTrapper/AI/CowardTrapperBehaviour.cs` | `CowardTrapper/Attack/CowardTrap.cs` | — | `CowardTrapper/Animator/CowardTrapperAnimatorInjector.cs` | `CowardTrapper/Audio/CowardTrapperAudio.cs` | Coward trapper, multi-state (Death/Idle/RunAway) |
| CrossCanyon | `CrossCanyon/CrossCannon.cs` | — | — | — | — | — | Environmental trap, non-standard enemy |
| CrossCrawler | `CrossCrawler/CrossCrawler.cs` | `CrossCrawler/IA/CrossCrawlerBehaviour.cs` | `CrossCrawler/Attack/CrossCrawlerAttack.cs` | `CrossCrawler/Attack/CrossCrawlerWeapon.cs` | `CrossCrawler/Animator/CrossCrawlerAnimatorInyector.cs` | `CrossCrawler/Audio/CrossCrawlerAudio.cs` | Cross crawler |
| DrownedCorpse | `DrownedCorpse/DrownedCorpse.cs` | `DrownedCorpse/AI/DrownedCorpseBehaviour.cs` | — | — | `DrownedCorpse/Animator/DrownedCorpseAnimatorInjector.cs` `DrownedCorpse/Animator/DrownedCorpseHelmet.cs` | `DrownedCorpse/Audio/DrownedCorpseAudio.cs` | Drowned corpse, includes Chase/Sleep state |

### E ~ G

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| ExplodingEnemy | `ExplodingEnemy/ExplodingEnemy.cs` | `ExplodingEnemy/AI/ExplodingEnemyBehaviour.cs` | `ExplodingEnemy/Attack/ExplodingEnemyAttack.cs` | `ExplodingEnemy/Attack/ExplodingenemyWeapon.cs` | `ExplodingEnemy/Animator/ExplodingEnemyAnimatorInyector.cs` | `ExplodingEnemy/Audio/ExplodingEnemyAudio.cs` | Self-destructing enemy |
| Firethrower | `Firethrower/Firethrower.cs` | `Firethrower/IA/FirethrowerBehaviour.cs` | `Firethrower/Attack/FirethrowerAttack.cs` | `Firethrower/Attack/FirethrowerWeapon.cs` | `Firethrower/Animator/FirethrowerAnimatorInyector.cs` | `Firethrower/Audio/FireThrowerAudio.cs` | Fire thrower |
| Flagellant | `Flagellant/Flagellant.cs` | `Flagellant/IA/FlagellantBehaviour.cs` | `Flagellant/Attack/FlagellantAttack.cs` | `Flagellant/Attack/FlagellantWhip.cs` | `Flagellant/Animator/FlagellantAnimatorInyector.cs` | `Flagellant/Audio/FlagellantAudio.cs` | Flagellant, whip-wielding |
| FlyingPortrait | `FlyingPortrait/FlyingPortrait.cs` | `FlyingPortrait/AI/FlyingPortraitBehaviour.cs` | `FlyingPortrait/Attack/FlyingPortraitAttack.cs` | `FlyingPortrait/Attack/FlyingPortraitWeapon.cs` | `FlyingPortrait/Animator/FlyingPortraitAnimator.cs` | `FlyingPortrait/Audio/FlyingPortraitAudio.cs` | Flying portrait, includes Attack/Death/Wander state |
| Fool | `Fool/Fool.cs` | `Fool/AI/FoolBehaviour.cs` | `Fool/Attack/FoolAttack.cs` | `Fool/Attack/FoolWeapon.cs` | `Fool/Animator/FoolAnimatorInyector.cs` | `Fool/Audio/FoolAudio.cs` | Fool |
| Ghost | `Ghost/Ghost.cs` | — | — | — | — | — | Ghost base class, includes `GhostFlight`/`GhostPath`/`GhostWaypoint` |
| GhostKnight | `GhostKnight/GhostKnight.cs` | `GhostKnight/AI/GhostKnightBehaviour.cs` | `GhostKnight/Attack/GhostKnightAttack.cs` | `GhostKnight/Attack/GhostKnightSword.cs` | `GhostKnight/Animator/GhostKnightAnimatorInyector.cs` `GhostKnight/Animator/GhostKnightAnimatorBridge.cs` | `GhostKnight/Audio/GhostKnightAudio.cs` | Ghost knight, sword-wielding |
| GoldenCorpse | `GoldenCorpse/GoldenCorpse.cs` | `GoldenCorpse/AI/GoldenCorpseBehaviour.cs` | `GoldenCorpse/Attack/GoldenCorpseAttack.cs` `GoldenCorpse/Attack/DrownedCorpseAttack.cs` | `GoldenCorpse/Attack/DrownedCorpseWeapon.cs` | `GoldenCorpse/Animator/GoldenCorpseAnimatorInyector.cs` | `GoldenCorpse/Audio/GoldenCorpseAudio.cs` | Golden corpse, reuses drowned corpse attack, includes Awakener |

### H ~ L

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| HeadThrower | `HeadThrower/HeadThrower.cs` | `HeadThrower/AI/HeadThrowerBehaviour.cs` | — | — | `HeadThrower/Animator/HeadThrowerAnimatorInyector.cs` `HeadThrower/Animator/HeadThrowerAnimatorBridge.cs` | `HeadThrower/Audio/HeadThrowerAudio.cs` | Head thrower |
| HomingTurret | `HomingTurret/HomingTurret.cs` | `HomingTurret/AI/HomingTurretBehaviour.cs` | `HomingTurret/Attack/HomingTurretAttack.cs` | — | `HomingTurret/Animation/HomingTurretAnimationInyector.cs` | `HomingTurret/Audio/HomingTurretAudio.cs` | Homing turret, includes Attack/Dead/Idle state |
| JarThrower | `JarThrower/JarThrower.cs` | `JarThrower/AI/JarThrowerBehaviour.cs` | `JarThrower/Attack/JarThrowerAttack.cs` | `JarThrower/Attack/JarWeapon.cs` | `JarThrower/Animator/JarThrowerAnimator.cs` | `JarThrower/Audio/JarThrowerAudio.cs` | Jar thrower, includes Attack/Chase/Wander state |
| Jumper | `Jumper/Jumper.cs` | `Jumper/AI/JumperBehaviour.cs` | `Jumper/Attack/JumperAttack.cs` | — | `Jumper/Animator/JumperAnimator.cs` | `Jumper/Audio/JumperAudio.cs` | Jumper |
| LanceAngel | `LanceAngel/LanceAngel.cs` | `LanceAngel/AI/LanceAngelBehaviour.cs` | `LanceAngel/Attack/LanceAngelAttack.cs` | — | `LanceAngel/Animator/LanceAngelAnimatorInjector.cs` | `LanceAngel/Audio/LanceAngelAudio.cs` | Lance angel, includes Attack/Idle/Parry state |
| Legionary | `Legionary/Legionary.cs` | `Legionary/AI/LegionaryBehaviour.cs` | — | `Legionary/Attack/LegionaryWeapon.cs` | `Legionary/Animator/LegionaryAnimator.cs` | `Legionary/Audio/LegionaryAudio.cs` | Legionary, includes Attack/Wander state |

### M ~ N

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| MasterAnguish | — | — | — | — | — | `MasterAnguish/Audio/MasterAnguishAudio.cs` `MasterAnguish/Audio/ElderBrotherAudio.cs` `MasterAnguish/Audio/SingleAnguishAudio.cs` | Boss audio, audio components only. Main class: `TresAngustias/TresAngustiasMaster.cs` → [bosses.md](bosses.md) |
| MeltedLady | `MeltedLady/MeltedLady.cs` `MeltedLady/FloatingLady.cs` `MeltedLady/InkLady.cs` | `MeltedLady/IA/MeltedLadyBehaviour.cs` | `MeltedLady/Attack/MeltedLadyAttack.cs` `MeltedLady/Attack/FloatingLadyAttack.cs` | — | `MeltedLady/Animator/MeltedLadyAnimatorInyector.cs` `MeltedLady/Animator/InkLadyAnimatorInjector.cs` `MeltedLady/Animator/FloatingLadyAnimatorInjector.cs` | `MeltedLady/Audio/MeltedLadyAudio.cs` `MeltedLady/Audio/InkLadyAudio.cs` `MeltedLady/Audio/InkLadyBeamAudio.cs` | Melted lady, 3 variants, includes Attack/Death/Idle state |
| Menina | `Menina/Menina.cs` | `Menina/AI/MeninaBehaviour.cs` | `Menina/Attack/MeninaAttack.cs` | `Menina/Attack/MeninaWeapon.cs` | `Menina/Animator/MeninaAnimatorInyector.cs` | `Menina/Audio/MeninaAudio.cs` `Menina/IsabelAudio.cs` `Menina/LionheadAudio.cs` | Menina (Boss-level enemy under `Enemies/`, not in `Bosses/`), includes Attack/Backwards/Chase state |
| MudCrawler | — | — | — | — | — | `MudCrawler/Audio/MudCrawlerAudio.cs` | Audio component only, main class may be elsewhere |
| NewFlagellant | `NewFlagellant/NewFlagellant.cs` | `NewFlagellant/AI/NewFlagellantBehaviour.cs` | `NewFlagellant/Attack/NewFlagellantAttack.cs` | `NewFlagellant/Attack/NewFlagellantWeapon.cs` | `NewFlagellant/Animator/NewFlagellantAnimatorInyector.cs` | `NewFlagellant/Audio/NewFlagellantAudio.cs` | New flagellant, multi-state (Attack/Chase/Death/Falling/Hurt/Idle/Patrol) |
| Nun | `Nun/Nun.cs` | `Nun/IA/NunBehaviour.cs` | `Nun/Attack/NunAttack.cs` | `Nun/Attack/NunWeapon.cs` `Nun/Attack/OilPuddle.cs` | `Nun/Animator/NunAnimatorInyector.cs` | `Nun/Audio/NunAudio.cs` | Nun, oil puddle trap |

### P ~ R

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| PatrollingFlyingEnemy | `PatrollingFlyingEnemy/PatrollingFlyingEnemy.cs` | `PatrollingFlyingEnemy/AI/PatrollingFlyingEnemyBehaviour.cs` | `PatrollingFlyingEnemy/Attack/PatrollingFlyingEnemyAttack.cs` | — | `PatrollingFlyingEnemy/Animator/PatrollingFlyingEnemyAnimatorInyector.cs` | `PatrollingFlyingEnemy/Audio/PatrollingFlyingEnemyAudio.cs` | Patrolling flying enemy |
| Pietat | `Pietat/Pietat.cs` | — | — | — | `Pietat/PietatAnimations/PietatAnimations.cs` | — | Animation control only, non-standard enemy |
| PontiffHusk | `PontiffHusk/PontiffHuskMelee.cs` `PontiffHusk/PontiffHuskRanged.cs` | `PontiffHusk/AI/PontiffHuskMeleeBehaviour.cs` `PontiffHusk/AI/PontiffHuskRangedBehaviour.cs` | `PontiffHusk/Attack/PontiffHuskMeleeAttack.cs` `PontiffHusk/Attack/PontiffHuskRangedAttack.cs` `PontiffHusk/Attack/PontiffHuskRangedVariantAttack.cs` | `PontiffHusk/Attack/PontiffHuskMeleeWeapon.cs` `PontiffHusk/Attack/PontiffHuskRangedWeapon.cs` | `PontiffHusk/Animator/PontiffHuskAnimatorInyector.cs` `PontiffHusk/Animator/PontiffHuskAnimatorBridge.cs` | `PontiffHusk/Audio/PontiffHuskAudio.cs` | Pontiff husk, melee/ranged dual variant, includes FloatingMotion. Same-named boss → [bosses.md](bosses.md) (PontiffHuskBoss) |
| Processioner | `Processioner/Processioner.cs` `Processioner/ShooterProcessioner.cs` | `Processioner/AI/ProcessionerBehaviour.cs` `Processioner/AI/ShooterProcessionerBehaviour.cs` | — | — | `Processioner/Animator/ProcessionerAnimator.cs` `Processioner/Animator/ShooterProcessionerAnimator.cs` | `Processioner/Audio/ProcesionerAudio.cs` | Processioner and shooter variant |
| Projectiles | — | — | — | — | — | — | Projectile utility class directory, not an enemy. Includes `Projectile.cs`/`StraightProjectile.cs`/`HomingProjectile.cs`/`CurvedProjectile.cs`/`ParriableProjectile.cs` etc. |
| RangedBoomerang | `RangedBoomerang/RangedBoomerang.cs` | `RangedBoomerang/IA/RangedBoomerangBehaviour.cs` | `RangedBoomerang/Attack/RangedBoomerangAttack.cs` | — | `RangedBoomerang/Animator/RangedBoomerangAnimatorInyector.cs` | `RangedBoomerang/Audio/RangedBoomerangAudio.cs` `RangedBoomerang/BookThrowerAudio.cs` | Ranged boomerang / book thrower |
| ReekLeader | `ReekLeader/ReekLeader.cs` | `ReekLeader/AI/ReekLeaderBehaviour.cs` | `ReekLeader/Attack/ReekLeaderAttack.cs` | `ReekLeader/Attack/ReekSpawner.cs` `ReekLeader/Attack/ReekSpawnPoint.cs` | `ReekLeader/Animator/ReekLeaderAnimatorInyector.cs` | `ReekLeader/Audio/ReekLeaderAudio.cs` | Reek leader, can summon |
| Roller | `Roller/Roller.cs` `Roller/AxeRoller.cs` | `Roller/AI/RollerBehaviour.cs` `Roller/AI/AxeRollerBehaviour.cs` | `Roller/Attack/RollerAttack.cs` `Roller/Attack/AxeRollerAttack.cs` `Roller/Attack/AxeRollerMeleeAttack.cs` | `Roller/Attack/AxeRollerMeleeWeapon.cs` `Roller/Attack/AxeRollerProjectile.cs` `Roller/Attack/RollerProjectile.cs` | `Roller/Animator/RollerAnimatorInjector.cs` `Roller/Animator/AxeRollerAnimatorInjector.cs` | `Roller/Audio/RollerAudio.cs` `Roller/Audio/AxeRollerAudio.cs` | Roller / Axe roller dual variant |
| Runner | `Runner/Runner.cs` | `Runner/AI/RunnerBehaviour.cs` | `Runner/Attack/RunnerAttack.cs` | — | `Runner/Animator/RunnerAnimatorInjector.cs` | `Runner/Audio/RunnerAudio.cs` | Runner, includes Chase/Idle state |

### S ~ W

| Enemy Name | Main Class | Behaviour | Attack | Weapon | Animator | Audio | Notes |
|--------|------|-----------|--------|--------|----------|-------|------|
| ShieldMaiden | `ShieldMaiden/ShieldMaiden.cs` | `ShieldMaiden/IA/ShieldMaidenBehaviour.cs` | `ShieldMaiden/Attack/ShieldMaidenAttack.cs` | `ShieldMaiden/Attack/ShieldMaidenWeapon.cs` | `ShieldMaiden/Animator/ShieldMaidenAnimatorInyector.cs` | `ShieldMaiden/Audio/ShieldMaidenAudio.cs` | Shield maiden |
| SingleAnguish | — | — | — | — | `SingleAnguish/Animator/SingleAnguishAnimatorInyector.cs` | — | Animation control only; main class: `TresAngustias/TresAngustiasMaster.cs` → [bosses.md](bosses.md) |
| Stoners | `Stoners/Stoners.cs` | `Stoners/AI/StonerBehaviour.cs` | `Stoners/Attack/StonersAttack.cs` | `Stoners/Rock/StonersRock.cs` `Stoners/Rock/StonersGrave.cs` `Stoners/Rock/RockPool.cs` | `Stoners/Animator/StonerAnimatorInyector.cs` `Stoners/Animator/StonerAnimatorBridge.cs` | `Stoners/Audio/StonersAudio.cs` `Stoners/Audio/StonersRockAudio.cs` | Stoners, includes Rock physics system |
| Swimmer | `Swimmer/Swimmer.cs` | `Swimmer/AI/SwimmerBehaviour.cs` | `Swimmer/Attack/SwimmerAttack.cs` | `Swimmer/Attack/SwimmerWeapon.cs` | `Swimmer/Animator/SwimmerAnimatorInyector.cs` `Swimmer/Animator/SwimmerTerrainEffect.cs` | `Swimmer/Audio/SwimmerAudio.cs` | Swimmer enemy, includes terrain effects |
| TrinityMinion | `TrinityMinion/TrinityMinion.cs` | `TrinityMinion/AI/TrinityMinionBehaviour.cs` | `TrinityMinion/Attack/TrinityMinionAttack.cs` | — | `TrinityMinion/Animator/TrinityMinionAnimatorInyector.cs` | `TrinityMinion/Audio/TrinityMinionAudio.cs` | Trinity minion |
| ViciousDasher | `ViciousDasher/ViciousDasher.cs` | `ViciousDasher/AI/ViciousDasherBehaviour.cs` | `ViciousDasher/Attack/ViciousDasherAttack.cs` | `ViciousDasher/Attack/ViciousDasherWeapon.cs` | `ViciousDasher/Animator/ViciousDasherAnimatorInyector.cs` | `ViciousDasher/Audio/ViciousDasherAudio.cs` | Vicious dasher, includes Attack/Death/Idle state |
| WalkingTomb | `WalkingTomb/WalkingTomb.cs` | `WalkingTomb/AI/WalkingTombBehaviour.cs` | `WalkingTomb/Attack/WalkingTombAttack.cs` | `WalkingTomb/Attack/WalkingTombWeapon.cs` | `WalkingTomb/Animator/WalkingTombAnimatorInjector.cs` | `WalkingTomb/Audio/WalkingTombAudio.cs` | Walking tomb, includes Attack/Walk state |
| WallEnemy | `WallEnemy/WallEnemy.cs` | `WallEnemy/AI/WallEnemyBehaviour.cs` | `WallEnemy/Attack/WallEnemyAttack.cs` `WallEnemy/Attack/WallEnemyRangedAttack.cs` | `WallEnemy/Attack/WallEnemyWeapon.cs` `WallEnemy/Attack/WallEnemyProjectile.cs` | `WallEnemy/Animator/WallEnemyAnimatorInyector.cs` | `WallEnemy/Audio/WallEnemyAudio.cs` `WallEnemy/Audio/BasicWallEnemyAudio.cs` `WallEnemy/Audio/RangedWallEnemyAudio.cs` | Wall enemy, melee/ranged dual variant |
| WaxCrawler | `WaxCrawler/WaxCrawler.cs` | `WaxCrawler/AI/WaxCrawlerBehaviour.cs` | `WaxCrawler/Attack/WaxCrawlerAttack.cs` | `WaxCrawler/Attack/WaxCrawlerBodyWeapon.cs` | `WaxCrawler/Animator/WaxCrawlerAnimatorInyector.cs` `WaxCrawler/Animator/WaxCrawlerAnimatorBridge.cs` | `WaxCrawler/Audio/WaxCrawlerAudio.cs` `WaxCrawler/Audio/CreepCrawlerAudio.cs` | Wax crawler |
| WheelCarrier | `WheelCarrier/WheelCarrier.cs` | `WheelCarrier/IA/WheelCarrierBehaviour.cs` | `WheelCarrier/Attack/WheelCarrierAttack.cs` | `WheelCarrier/Attack/WheelCarrierWeapon.cs` | `WheelCarrier/Animator/WheelCarrierAnimatorInyector.cs` | `WheelCarrier/Audio/WheelCarrierAudio.cs` | Wheel carrier |

---

## Framework Base Classes

All file paths are relative to `Assembly-CSharp/Gameplay/GameControllers/Enemies/Framework/`.

### AI Core (`Framework/IA/`)

| Class | File | Inheritance | Description |
|----|------|------|------|
| `EnemyBehaviour` | `IA/EnemyBehaviour.cs` | `MonoBehaviour` | **Enemy AI core abstract class**. Manages `PlayerHeard`/`PlayerSeen`/`TurningAround`/`SensorHitsFloor`/`GotParry` states, holds a `BehaviourTree` (NodeCanvas), serves as the root for all enemy behaviour trees. Drives entity `Entity.Status` state transitions |
| `EnemyAI` | `IA/EnemyAI.cs` | `MonoBehaviour` | Enemy AI helper component, manages hearing/vision sensors, ground detection, directional awareness, handles `EntityOrientation` flipping |
| `EnemyAction` | `IA/EnemyAction.cs` | — | Base class for enemy behaviour tree Action nodes, uses `CustomYieldInstruction` to wait for completion, supports `OnActionStarts`/`OnActionIsStopped`/`OnActionFinished` callbacks |
| `EnemySensor` | `IA/EnemySensor.cs` | `MonoBehaviour` | Sensor base class, detects entity orientation via `EntityOrientation`, auto-flips position. Subclasses override `InheritedStart()` |

#### EnemyAction Subclasses

| Class | File | Description |
|----|------|------|
| `LaunchMethod_EnemyAction` | `IA/LaunchMethod_EnemyAction.cs` | Executes a parameterless method |
| `LaunchMethodWithVector_EnemyAction` | `IA/LaunchMethodWithVector_EnemyAction.cs` | Executes a method with Vector parameter |
| `LaunchMethodWithTwoVectors_EnemyAction` | `IA/LaunchMethodWithTwoVectors_EnemyAction.cs` | Executes a method with two Vector parameters |
| `WaitSeconds_EnemyAction` | `IA/WaitSeconds_EnemyAction.cs` | Waits N seconds |
| `WaitUntilActionFinishes` | `IA/WaitUntilActionFinishes.cs` | Waits for another Action to complete |
| `WaitUntilActionCustomCallback` | `IA/WaitUntilActionCustomCallback.cs` | Waits for custom callback to complete |
| `MoveEasing_EnemyAction` | `IA/MoveEasing_EnemyAction.cs` | Eased movement |
| `MoveToPointUsingAgent_EnemyAction` | `IA/MoveToPointUsingAgent_EnemyAction.cs` | NavAgent movement |
| `CountdownFromTen_EnemyAction` | `IA/CountdownFromTen_EnemyAction.cs` | Countdown action |
| `DebugText_EnemyAction` | `IA/DebugText_EnemyAction.cs` | Debug text action |

#### EnemySensor Subclasses (`Framework/IA/Sensors/`)

| Class | File | Inheritance | Description |
|----|------|------|------|
| `AudioSensor` | `IA/Sensors/AudioSensor.cs` | `EnemySensor` | Audio sensor |
| `VisualSensor` | `IA/Sensors/VisualSensor.cs` | `EnemySensor` | Visual sensor |

#### Other AI Files

| Class | File | Description |
|----|------|------|
| `CliffSensor` | `IA/CliffSensor.cs` | Cliff detection sensor |
| `EnemySpawner` | `IA/EnemySpawner.cs` | Enemy spawner |
| `NPCInputs` | `IA/NPCInputs.cs` | NPC input data |
| `SpawnBehaviourConfig` / `SpawnBehaviorFloatParam` | `IA/` | Spawn behaviour configuration |
| `ContactAreaDummyEnemyBehaviour` | `IA/ContactAreaDummyEnemyBehaviour.cs` | Contact area dummy behaviour |
| `EnemyActionTesterBehaviour` | `IA/EnemyActionTesterBehaviour.cs` | Action testing behaviour |

### Attack (`Framework/Attack/`)

| Class | File | Description |
|----|------|------|
| `EnemyAttack` | `Attack/EnemyAttack.cs` | Inherits `Attack`, enemy attack base class. Sets `ContactDamageType`/`ContactDamageAmount`/`ContactAttackForce`, creates `ContactHit`, holds `CurrentEnemyWeapon` |
| `IDirectAttack` | `Attack/IDirectAttack.cs` | Direct attack interface |
| `IProjectileAttack` | `Attack/IProjectileAttack.cs` | Projectile attack interface |
| `ISpawnerAttack` | `Attack/ISpawnerAttack.cs` | Spawner attack interface |
| `IPaintAttackCollider` | `Attack/IPaintAttackCollider.cs` | Attack collider drawing interface |
| `PaintAttackColliderWhenActive` | `Attack/PaintAttackColliderWhenActive.cs` | Draws collider when active |
| `PaintDamageableCollider` | `Attack/PaintDamageableCollider.cs` | Draws damageable collider |

### Audio (`Framework/Audio/`)

| Class | File | Description |
|----|------|------|
| `EnemyAttackAudio` | `Audio/EnemyAttackAudio.cs` | Enemy attack audio |
| `EnemyMovementSetAudio` | `Audio/EnemyMovementSetAudio.cs` | Enemy movement audio set |

### Damage (`Framework/Damage/`)

| Class | File | Description |
|----|------|------|
| `EnemyDamageArea` | `Damage/EnemyDamageArea.cs` | Enemy damage area |

### Physics (`Framework/Physics/`)

| Class | File | Description |
|----|------|------|
| `EnemyBumper` | `Physics/EnemyBumper.cs` | Enemy collision bounce |
| `EnemyFloorChecker` | `Physics/EnemyFloorChecker.cs` | Enemy ground detection |

### Persistence (`Framework/Persistence/`)

| Class | File | Description |
|----|------|------|
| `PersistentEnemy` | `Persistence/PersistentEnemy.cs` | Persists enemy state (cross-scene saving) |

---

## Entity Base Classes

All file paths are relative to `Assembly-CSharp/Gameplay/GameControllers/Entities/`.

### Core Entities

| Class | File | Inheritance | Description |
|----|------|------|------|
| `Entity` | `Entity.cs` | `MonoBehaviour` | **Root class for all entities**. Provides `Status` (`EntityStatus`), event system (`OnDamaged`/`OnDamageTaken`/`OnDeath`), `EntityShadow`, `Kill()`. Marked with `[SelectionBase]` |
| `Enemy` | `Enemy.cs` | `Entity` | **Enemy base class**. `[RequireComponent(typeof(EnemyBehaviour))]`, manages `IsGuarding`/`IsFalling`/`IsAttacking`/`IsChasing`/`Landing`, `SpriteRenderer`, damage flash (`Flash`). Abstract method `EnemyAttack()` returns `EnemyAttack` |
| `EntityStatus` | `Framework/FrameworkCore/EntityStatus.cs` | — | Entity state object. Fields: `Unattacable`, `Invulnerable`, `Orientation` (EntityOrientation), `CurrentState`, etc. |
| `EntityStates` | `EntityStates.cs` | `enum` | Entity state enum: `Wander`, `Attack`, `Hurt`, `Idle`, `Chasing` |
| `EntityStats` | `EntityStats.cs` | `PersistentInterface` | Entity stats: `AttackSpeed`/`Agility`/`Defense`/`Strength`/`Life`/`Fervour`, etc. |
| `EntityOrientation` | Defined in `Framework/FrameworkCore/` | `enum` | `Left`/`Right` |

### Attack & Damage (`Entities/`)

| Class | File | Inheritance | Description |
|----|------|------|------|
| `Attack` | `Attack.cs` | `Trait` | **Attack abstract base class**. Contains `IsEnemyHit`/`IsAttacking`/`EntityOwner`, method `ContactAttack(IDamageable)` |
| `Hit` | `Hit.cs` | — | Attack hit data object. Fields: `AttackingEntity`/`DamageType`/`DamageElement`/`DamageAmount`/`Force`/`Unparriable`/`HitSoundId` |
| `AttackArea` | `AttackArea.cs` | — | Attack detection area |
| `CircleAttackArea` | `CircleAttackArea.cs` | — | Circular detection area |
| `DamageArea` | `DamageArea.cs` | — | Damage area base class, contains `DamageType`/`DamageElement` enums |
| `DamageAreaSwapper` | `DamageAreaSwapper.cs` | — | Damage area swapper |
| `ContactDamage` | `ContactDamage.cs` | — | Contact damage |
| `ContactDamageDummyAttack` | `ContactDamageDummyAttack.cs` | — | Contact damage dummy attack |
| `IDamageable` | `IDamageable.cs` | `interface` | Damageable interface |
| `IHittable` | `IHittable.cs` | `interface` | Hittable interface |
| `ICollisionEmitter` | `ICollisionEmitter.cs` | `interface` | Collision event emitter interface |
| `IPaintDamageableCollider` | `IPaintDamageableCollider.cs` | `interface` | Paint damageable collider interface |
| `CustomDamageEffectsTrait` | `CustomDamageEffectsTrait.cs` | — | Custom damage effects |

### Animations (`Entities/Animations/`)

| Class | File | Description |
|----|------|------|
| `EnemyAnimatorInyector` | `Animations/EnemyAnimatorInyector.cs` | Enemy animator injector base class |
| `EntityAnimationEvents` | `Animations/EntityAnimationEvents.cs` | Entity animation events |
| `AttackAnimationsEvents` | `Animations/AttackAnimationsEvents.cs` | Attack animation events |
| `AttackAnimations` | `AttackAnimations.cs` | Attack animation control |

### Weapons (`Entities/Weapon/`)

| Class | File | Description |
|----|------|------|
| `Weapon` | `Weapon/Weapon.cs` | Weapon base class |

### Utilities (`Entities/`)

| Class/File | Description |
|----------|------|
| `CheckTrap.cs` | Trap detection |
| `SimpleVFX.cs` | Simple visual effects |
| `ThrowBack.cs` | Knockback/throwback effect |
| `EnemyBarrier.cs` | Enemy barrier |
| `EnemyHealthBar.cs` | Enemy health bar UI |
| `EnemyRootPoint.cs` | Enemy root point |
| `CollisionSensor.cs` | Collision sensor |
| `TriggerSensor.cs` | Trigger sensor |
| `VisionCone.cs` | Vision cone |
| `EntityDisplacement.cs` | Entity displacement |
| `EntityMotionChecker.cs` | Entity motion detection |
| `EntityShadow.cs` | Entity shadow |
| `FlipEntityComponents.cs` | Flip entity components |
| `MotionLerper.cs` | Motion interpolation |
| `MoveOnStart.cs` | Initial movement |
| `SpawnPoint.cs` | Spawn point |
| `SensorType.cs` | Sensor type enum |
| `ExecutionController.cs` | Execution controller |

### Traits (`Entities/Traits/`)

| Class | File | Description |
|----|------|------|
| `EnemyHitStun` | `Traits/EnemyHitStun.cs` | Enemy hit stun |
| `VulnerablePeriodTrait` | `Traits/VulnerablePeriodTrait.cs` | Vulnerability window |
| `CustomShadowTrait` | `Traits/CustomShadowTrait.cs` | Custom shadow |

### Special Entities (under `Entities/`)

| Class | Directory | Description |
|----|------|------|
| `GuardianPrayer` | `Guardian/` | Guardian prayer (Boss helper entity), includes full AI state machine, attack, weapon, animation, audio |
| `MiriamPortalPrayer` | `MiriamPortal/` | Miriam portal prayer, structure similar to GuardianPrayer |

### Entity Gizmos (`Entities/EntityGizmos/`)

| Class | Description |
|----|------|
| `EntityRootMotion` | Entity root motion visualization |

---

## Key Entry Points for Mod Development

### 1. Enemy AI Control — `EnemyBehaviour`

All enemy AI inherits from `EnemyBehaviour` (`Framework/IA/EnemyBehaviour.cs`). Core flow:

```
EnemyBehaviour
  ├── BehaviourTree (NodeCanvas)  ← Behaviour tree
  ├── PlayerHeard / PlayerSeen    ← Player perception
  ├── SensorHitsFloor             ← Ground detection
  ├── GotParry                    ← Parried flag
  └── Entity (via GetComponent)   ← Holds Entity reference
```

**Hook points**: Override `Update()`, hook into `BehaviourTree` nodes, or read/modify entity state (`EntityStates` enum) via `Entity.Status`.

### 2. Entity State Management — `Entity.Status`

- `Entity.Status` is an `EntityStatus` instance (`Framework/FrameworkCore/EntityStatus.cs`)
- Key properties: `Unattacable`, `Invulnerable`, `Orientation`
- `EntityStates` enum controls behaviour state: `Wander` / `Attack` / `Hurt` / `Idle` / `Chasing`

### 3. Attack System — `EnemyAttack` / `Attack`

- `Attack` (`Entities/Attack.cs`): Attack abstract base class, inherits `Trait`
- `EnemyAttack` (`Framework/Attack/EnemyAttack.cs`): Enemy attack, inherits `Attack`, creates `ContactHit` (`Hit` object), holds `CurrentEnemyWeapon`
- `Hit`: Attack hit data, contains `DamageAmount`/`DamageType`/`Force`/`Unparriable`/`HitSoundId`
- Damage is transmitted via `IDamageable.Damage(Hit)` interface
- Attack interfaces split into `IDirectAttack`/`IProjectileAttack`/`ISpawnerAttack`

### 4. Weapon System — `Weapon`

- Weapon base class: `Entities/Weapon/Weapon.cs`
- Each enemy can have a dedicated weapon in its `Attack/` subdirectory (e.g., `AcolyteCandlestick`, `FlagellantWhip`)

### 5. Typical Enemy File Structure

```
Enemies/<EnemyName>/
  <EnemyName>.cs          → Main class, inherits Enemy
  AI/  or IA/              → Behaviour class, inherits EnemyBehaviour
  Attack/                 → Attack class, inherits EnemyAttack + Weapon class
  Animator/               → AnimatorInyector class
  Audio/                  → Audio class
```

### 6. Inheritance Chain Reference

```
MonoBehaviour
  └── Entity                    (Entities/Entity.cs)
        ├── Status: EntityStatus
        ├── Stats: EntityStats
        └── Enemy               (Entities/Enemy.cs)  [RequireComponent(EnemyBehaviour)]
              └── <Specific Enemy Class>   (e.g., Acolyte.cs, BellGhost.cs)
                    └── EnemyBehaviour  (Framework/IA/EnemyBehaviour.cs)
                          └── <Specific Behaviour> (e.g., AcolyteBehaviour)

Attack (Entities/Attack.cs : Trait)
  └── EnemyAttack              (Framework/Attack/EnemyAttack.cs)
        └── IDirectAttack / IProjectileAttack / ISpawnerAttack
```

### 7. Projectile System (`Enemies/Projectiles/`)

This directory contains utility classes, not enemy implementations. Inheritance chain:

```
Projectile  (base class)
  ├── StraightProjectile
  ├── HomingProjectile
  ├── CurvedProjectile
  ├── BouncingProjectile
  ├── BoomerangProjectile
  ├── AcceleratedProjectile
  ├── OscillatingProjectile
  ├── SplineFollowingProjectile
  ├── CrawlerProjectile
  ├── TargetedProjectile
  └── ParriableProjectile      ← Parriable projectile
```

Also includes `ProjectilePool` and `ProjectileReaction` helpers.

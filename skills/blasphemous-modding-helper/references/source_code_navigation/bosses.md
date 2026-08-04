# Bosses

Boss system source code navigation. All paths relative to `Assembly-CSharp/`.

> **Boss/Enemy ownership rule**: This document covers Boss main classes/behaviour under `Gameplay/GameControllers/Bosses/`. Entities under `Enemies/` that are driven by the Boss system (`MasterAnguish` audio, `SingleAnguish` animation) and Boss-level enemies (`Menina`) are documented in [enemy.md](enemy.md); same-named entities (Boss vs regular enemy, e.g. `PontiffHusk`) are cross-linked inline.

## Core Design Patterns

1. One folder per boss: main class + `XXXBehaviour` + `XXX_St*` state classes + Attack/Weapon/Animator/Audio
2. `BossFightManager` controls fight flow and phase transitions
3. Reusable attack patterns shared via `CommonAttacks/`
4. State definitions centralized in `BOSS_STATES.cs` (shared across bosses)

---

## Boss Overview

| Boss Name | Main Class | Behaviour | AI/States | Attack | Weapon | Animator | Audio | Notes |
|---------|------|-----------|-----------|--------|--------|----------|-------|------|
| **Amanecidas** (Golden Blades, Bejeweled Arrow, Chiselled Steel, Molten Thorn, Laudes) | `Gameplay/GameControllers/Bosses/Amanecidas/Amanecidas.cs` | `Amanecidas/AmanecidasBehaviour.cs` | `Amanecidas/Amanecidas_StAction.cs`<br/>`Amanecidas/Amanecidas_StFloating.cs`<br/>`Amanecidas/Amanecidas_StHurt.cs`<br/>`Amanecidas/Amanecidas_StRecharging.cs` | `Amanecidas/AmanecidasMeleeAttack.cs`<br/>`Amanecidas/AmanecidaBeamAttack.cs` | `Amanecidas/AmanecidasWeapon.cs`<br/>`Amanecidas/AmanecidaShield.cs` | — | `Amanecidas/Audio/AmanecidasAudio.cs` | Config: `AmanecidaAttackScriptableConfig.cs` |
| **BejeweledSaint** (Melquíades, The Exhumed Archbishop) | `Gameplay/GameControllers/Bosses/BejeweledSaint/BejeweledSaintBoss.cs` | `BejeweledSaint/IA/BejeweledSaintBehaviour.cs` | `BejeweledSaint/IA/BejeweledSaint_StAction.cs`<br/>`BejeweledSaint/IA/BejeweledSaint_StChasePlayer.cs`<br/>`BejeweledSaint/IA/BejeweledSaint_StCollapsed.cs`<br/>`BejeweledSaint/IA/BejeweledSaint_StDeath.cs`<br/>`BejeweledSaint/IA/BejeweledSaint_StIntro.cs`<br/>`BejeweledSaint/IA/BejeweledSaint_StMoveToPoint.cs` | `BejeweledSaint/Attack/BejeweledSaintArmAttack.cs`<br/>`BejeweledSaint/Attack/BejeweledSaintCastArm.cs`<br/>`BejeweledSaint/Attack/BejeweledSaintStaff.cs`<br/>`BejeweledSaint/Attack/BejeweledSmashHand.cs`<br/>`BejeweledSaint/Attack/BejeweledSmashHandManager.cs`<br/>`BejeweledSaint/Attack/BejeweledDivineBeam.cs` | — | `BejeweledSaint/Animation/BejeweledSaintAnimatorInyector.cs` | `BejeweledSaint/Audio/BejeweledSaintAudio.cs` | Sub-components: `BejeweledSaintHead.cs`, `BejeweledSaintHolder.cs`, `DivineBeamOrigin.cs`; Managers: `BsDivineBeamManager.cs`, `BsHolderManager.cs` |
| **WickerWurm** (Expósito, Scion of Abjuration) | `Gameplay/GameControllers/Bosses/BlindBaby/WickerWurm.cs` | `BlindBaby/WickerWurmBehaviour.cs` | `BlindBaby/AI/WickerWurm_StDeath.cs`<br/>`BlindBaby/AI/WickerWurm_StFixed.cs`<br/>`BlindBaby/AI/WickerWurm_StIntro.cs`<br/>`BlindBaby/AI/WickerWurm_StMoving.cs`<br/>`BlindBaby/AI/WickerWurm_StStun.cs` | — | — | — | — | Sub-components: `WickerWurmHeart.cs`; Definitions: `BOSS_STATES.cs`; Balance: `BlindBabyBalanceImporter.cs` |
| **BurntFace** (Our Lady of the Charred Visage) | `Gameplay/GameControllers/Bosses/BurntFace/BurntFace.cs` | `BurntFace/AI/BurntFaceBehaviour.cs` | `BurntFace/AI/BurntFaceHandBehaviour.cs`<br/>`BurntFace/AI/BurntFaceSt_Death.cs`<br/>`BurntFace/AI/BurntFaceSt_Eyes.cs`<br/>`BurntFace/AI/BurntFaceSt_Head.cs`<br/>`BurntFace/AI/BurntFaceSt_Hidden.cs`<br/>`BurntFace/AI/BurntFaceSt_Intro.cs` | `BurntFace/Rosary/BurntFaceBeamAttack.cs` | — | `BurntFace/Animation/BurntFaceAnimatorInyector.cs` | `BurntFace/BurntFaceAudio.cs`<br/>`BurntFace/BurntFaceBeamAudio.cs` | Rosary: `BurntFaceRosaryManager.cs`, `BurntFaceRosaryPattern.cs`, `BurntFaceRosaryScriptablePattern.cs`, `BurntFaceRosaryBead.cs`, `BurntFaceRosaryAngles.cs`; Bead States: `BurntFaceRosaryBead_St*.cs` (7); `BurntFaceBossFightPoints.cs`, `PointsByPatternId.cs`; Balance: `BurnfaceBalanceImporter.cs` |
| **Crisanta** (Crisanta of the Wrapped Agony) | `Gameplay/GameControllers/Bosses/Crisanta/Crisanta.cs` | `Crisanta/CrisantaBehaviour.cs` | `Crisanta/AI/Crisanta_StAction.cs`<br/>`Crisanta/AI/Crisanta_StDeath.cs`<br/>`Crisanta/AI/Crisanta_StGuard.cs`<br/>`Crisanta/AI/Crisanta_StIntro.cs` | `Crisanta/CrisantaMeleeAttack.cs` | `Crisanta/CrisantaWeapon.cs` | `Crisanta/Animator/CrisantaAnimatorInyector.cs` | `Crisanta/Audio/CrisantaAudio.cs` | Balance: `CrisantaBalanceImporter.cs`; Definitions: `BOSS_STATES.cs` |
| **Esdras** (Esdras, of the Anointed Legion) | `Gameplay/GameControllers/Bosses/EcclesiaBros/Esdras/Esdras.cs` | `EcclesiaBros/Esdras/EsdrasBehaviour.cs` | `EcclesiaBros/Esdras/AI/Esdras_StAction.cs`<br/>`EcclesiaBros/Esdras/AI/Esdras_StDeath.cs`<br/>`EcclesiaBros/Esdras/AI/Esdras_StIntro.cs`<br/>`EcclesiaBros/Esdras/AI/Esdras_StRun.cs` | `EcclesiaBros/Esdras/EsdrasMeleeAttack.cs` | `EcclesiaBros/Esdras/EsdrasWeapon.cs` | `EcclesiaBros/Esdras/Animator/EsdrasAnimatorInyector.cs` | `EcclesiaBros/Esdras/Audio/EsdrasAudio.cs` | Balance: `EsdrasBalanceImporter.cs`, `LegionaryBalanceImporter.cs`; Definitions: `BOSS_STATES.cs` |
| **Perpetua** (Perpetua) | `Gameplay/GameControllers/Bosses/EcclesiaBros/Perpetua/Perpetua.cs` | `EcclesiaBros/Perpetua/PerpetuaBehaviour.cs` | `EcclesiaBros/Perpetua/AI/Perpetua_StAction.cs`<br/>`EcclesiaBros/Perpetua/AI/Perpetua_StDeath.cs`<br/>`EcclesiaBros/Perpetua/AI/Perpetua_StFlapToPoint.cs`<br/>`EcclesiaBros/Perpetua/AI/Perpetua_StFollowPlayer.cs`<br/>`EcclesiaBros/Perpetua/AI/Perpetua_StIntro.cs` | — | — | `EcclesiaBros/Perpetua/Animator/PerpetuaAnimatorInyector.cs` | `EcclesiaBros/Perpetua/Audio/PerpetuaAudio.cs` | Config: `PerpetuaAttackConfig.cs`, `PerpetuaScriptableFightConfig.cs`; `PerpetuaFightSpawner.cs`, `PerpetuaPoints.cs`; Balance: `PerpetuaBalanceImporter.cs`; Definitions: `BOSS_STATES.cs` |
| **ElderBrother** (Warden of the Silent Sorrow) | `Gameplay/GameControllers/Bosses/ElderBrother/ElderBrother.cs` | `ElderBrother/ElderBrotherBehaviour.cs` | — | — | — | `ElderBrother/ElderBrotherAnimatorInyector.cs` | — | Balance: `ElderBrotherBalanceImporter.cs` |
| **HighWills** (High Wills) | `Gameplay/GameControllers/Bosses/HighWills/HighWills.cs` | `HighWills/HighWillsBehaviour.cs` | — | `HighWills/Attack/RangedMine.cs`<br/>`HighWills/Attack/RangedMineShooter.cs` | — | — | — | UI: `HighWillsPlayerBarsColorController.cs` |
| **Isidora** (Isidora, Voice of the Dead) | `Gameplay/GameControllers/Bosses/Isidora/Isidora.cs` | `Isidora/IsidoraBehaviour.cs` | — | `Isidora/IsidoraMeleeAttack.cs` | `Isidora/IsidoraWeapon.cs` | `Isidora/IsidoraAnimatorInyector.cs` | `Isidora/Audio/IsidoraAudio.cs` | Fireballs: `HomingBonfire.cs`, `HomingBonfireAttack.cs`, `HomingBonfireBehaviour.cs`, `HomingBonfireAnimationInyector.cs`, `HomingBonfireAudio.cs`; Bonfire States: `HomingBonfireAttackState.cs`, `HomingBonfireChargeIsidoraState.cs`, `HomingBonfireIdleState.cs`; Config: `IsidoraScriptableConfig.cs` |
| **Lesmes** (Lesmes of the Cradle of Sorrow) | `Gameplay/GameControllers/Bosses/Lesmes/Lesmes.cs` | `Lesmes/LesmesBehaviour.cs` | — | — | — | `Lesmes/Animation/LesmesAnimatorInyector.cs` | — | — |
| **PietyMonster** (Ten Piedad) | `Gameplay/GameControllers/Bosses/PietyMonster/PietyMonster.cs` | `PietyMonster/IA/PietyMonsterBehaviour.cs` | — | `PietyMonster/Attack/PietyBush.cs`<br/>`PietyMonster/Attack/PietyBushManager.cs`<br/>`PietyMonster/Attack/PietyClaw.cs`<br/>`PietyMonster/Attack/PietyClawAttack.cs`<br/>`PietyMonster/Attack/PietyFeetAttackArea.cs`<br/>`PietyMonster/Attack/PietyHoof.cs`<br/>`PietyMonster/Attack/PietyRoot.cs`<br/>`PietyMonster/Attack/PietyRootsManager.cs`<br/>`PietyMonster/Attack/PietySmash.cs`<br/>`PietyMonster/Attack/PietySmashAttack.cs`<br/>`PietyMonster/Attack/PietySpitAttack.cs`<br/>`PietyMonster/Attack/PietyStompAttack.cs` | — | `PietyMonster/Animation/PietyMonsterAnimatorInyector.cs`<br/>`PietyMonster/Animation/PietyAnimatorBridge.cs` | `PietyMonster/Sound/PietyMonsterAudio.cs` | Thorn Projectile: `PietyMonster/ThornProjectile/ThornProjectile.cs`; Barrier: `PietyMonster/Animation/BossBodyBarrier.cs` |
| **PontiffGiant** (His Holiness Escribar) | `Gameplay/GameControllers/Bosses/PontiffGiant/PontiffGiant.cs` | `PontiffGiant/PontiffGiantBehaviour.cs` | `PontiffGiant/AI/PontiffGiant_StAction.cs`<br/>`PontiffGiant/AI/PontiffGiant_StDeath.cs`<br/>`PontiffGiant/AI/PontiffGiant_StIntro.cs` | `PontiffGiant/PontiffSwordMeleeAttack.cs` | `PontiffGiant/PontiffGiantWeapon.cs` | `PontiffGiant/Animator/PontiffGiantAnimatorInyector.cs`<br/>`PontiffGiant/Animator/PontiffGiantAnimationEvents.cs` | `PontiffGiant/Audio/PontiffGiantAudio.cs` | Balance: `PontiffGiantBalanceImporter.cs`; Definitions: `BOSS_STATES.cs`; `PontiffGiantBossfightPoints.cs` |
| **PontiffHusk** (Pontiff Husk) | `Gameplay/GameControllers/Bosses/PontiffHusk/PontiffHuskBoss.cs` | `PontiffHusk/PontiffHuskBossBehaviour.cs` | — | `PontiffHusk/PontiffHuskBossMeleeAttack.cs` | `PontiffHusk/PontiffHuskBossWeapon.cs`<br/>`PontiffHusk/PontiffHuskBossAnchor.cs` | `PontiffHusk/PontiffHuskBossAnimatorInyector.cs` | `PontiffHusk/Audio/PontiffHuskBossAudio.cs` | Config: `PontiffHuskBossScriptableConfig.cs`; same-named regular enemy → [enemy.md](enemy.md) |
| **PontiffOldman** (Last Son of the Miracle) | `Gameplay/GameControllers/Bosses/PontiffOldman/PontiffOldman.cs` | `PontiffOldman/PontiffOldmanBehaviour.cs` | `PontiffOldman/AI/PontiffOldman_StAction.cs`<br/>`PontiffOldman/AI/PontiffOldman_StCasting.cs`<br/>`PontiffOldman/AI/PontiffOldman_StDeath.cs`<br/>`PontiffOldman/AI/PontiffOldman_StIntro.cs` | — | — | `PontiffOldman/Animator/PontiffOldmanAnimatorInyector.cs` | `PontiffOldman/Audio/PontiffOldmanAudio.cs` | Balance: `PontiffOldmanBalanceImporter.cs`; `PontiffOldmanBossfightPoints.cs`, `MaterialsBySpellType.cs`; Definitions: `BOSS_STATES.cs`, `PONTIFF_SPELLS.cs` |
| **PontiffSword** (Pontiff Sword) | `Gameplay/GameControllers/Bosses/PontiffSword/PontiffSword.cs` | `PontiffSword/PontiffSwordBehaviour.cs` | `PontiffSword/AI/PontiffSword_StAction.cs`<br/>`PontiffSword/AI/PontiffSword_StDeath.cs` | — | — | `PontiffSword/Animator/PontiffSwordAnimatorInyector.cs` | `PontiffSword/Audio/PontiffSwordAudio.cs` | Definitions: `SWORD_STATES.cs` |
| **Quirce** (Quirce, Returned By The Flames) | `Gameplay/GameControllers/Bosses/Quirce/Quirce.cs` | `Quirce/QuirceBehaviour.cs` | `Quirce/AI/QuirceSwordBehaviour.cs`<br/>`Quirce/AI/QuirceSwordSt_Idle.cs`<br/>`Quirce/AI/QuirceSwordSt_SpinToPoint.cs`<br/>`Quirce/AI/QuirceSwordSt_Spinning.cs` | `Quirce/Attack/BossAreaSummonAttack.cs`<br/>`Quirce/Attack/BossDashAttack.cs`<br/>`Quirce/Attack/BossInstantProjectileAttack.cs`<br/>`Quirce/Attack/BossJumpAttack.cs`<br/>`Quirce/Attack/BossSpawnedAreaAttack.cs`<br/>`Quirce/Attack/BossSpawnedAreaAttackEndBehaviour.cs`<br/>`Quirce/Attack/BossSpawnedGeoAttack.cs`<br/>`Quirce/Attack/BossSplineFollowingProjectileAttack.cs`<br/>`Quirce/Attack/BossTeleportAttack.cs`<br/>`Quirce/Attack/DashAttackInstantiations.cs`<br/>`Quirce/Attack/TestRicochetRay.cs` | — | `Quirce/Animation/QuirceAnimatorInyector.cs` | `Quirce/Audio/QuirceAudio.cs` | Balance: `QuirceBalanceImporter.cs`; `QuirceBossFightPoints.cs`, `SplinePointInfo.cs` |
| **Snake** (Sierpes) | `Gameplay/GameControllers/Bosses/Snake/Snake.cs` | `Snake/SnakeBehaviour.cs`<br/>`Snake/SnakeBehaviour_StIdle.cs` | `Snake/Snake_StAction.cs`<br/>`Snake/Snake_StDeath.cs` | `Snake/SnakeMeleeAttack.cs`<br/>`Snake/SnakeBeamAttack.cs`<br/>`Snake/SnakeBeamExplosionsCoordinator.cs` | `Snake/SnakeWeapon.cs` | `Snake/SnakeAnimatorInyector.cs` | `Snake/Audio/SnakeAudio.cs` | Config: `SnakeScriptableConfig.cs`; Movement: `SnakeSegmentsMovementController.cs` |
| **TresAngustias** (Tres Angustias) | `Gameplay/GameControllers/Bosses/TresAngustias/TresAngustiasMaster.cs` | `TresAngustias/TresAngustiasMasterBehaviour.cs` | `TresAngustias/AI/SingleAnguishSt_Action.cs`<br/>`TresAngustias/AI/SingleAnguishSt_Dance.cs`<br/>`TresAngustias/AI/SingleAnguishSt_Death.cs`<br/>`TresAngustias/AI/SingleAnguishSt_GoToComboPoint.cs`<br/>`TresAngustias/AI/SingleAnguishSt_GoToDance.cs`<br/>`TresAngustias/AI/SingleAnguishSt_GoToMergePoint.cs`<br/>`TresAngustias/AI/SingleAnguishSt_Intro.cs`<br/>`TresAngustias/AI/SingleAnguishSt_Merged.cs` | — | — | `TresAngustias/Animator/TresAngustiasMasterAnimatorInyector.cs` | — | Sub-entities: `SingleAnguish.cs`, `SingleAnguishAction.cs`, `SingleAnguishBehaviour.cs`; Config: `MasterAnguishAttackConfig.cs`; Definitions: `BOSS_STATES.cs`, `MASTER_ANGUISH_ATTACKS.cs`, `MASTER_ANGUISH_STATES.cs`; Balance: `TresAngustiasBalanceImporter.cs` |

---

## Common Components

The following components are located in `Gameplay/GameControllers/Bosses/` and are shared by multiple bosses.

### BossFight Management

| File | Description |
|------|------|
| `BossFight/BossFightManager.cs` | Global boss fight manager, controls fight flow and phase transitions |
| `BossFight/BossFightAudio.cs` | Boss fight audio management |
| `BossFight/BossFightMetrics.cs` | Boss fight metrics (damage, time, etc.) |

### Boss Base Components

| File | Description |
|------|------|
| `BossPhase.cs` | Boss phase definition (phase transitions, HP thresholds, etc.) |
| `BossPlayerAwareness.cs` | Boss player awareness/detection |
| `BossAwarenessArea.cs` | Boss awareness area (trigger range) |
| `BossScripting.cs` | Boss scripting events/cutscene triggers |

### Global References

| File | Location | Description |
|------|------|------|
| `BossAttackWarning.cs` | `Assembly-CSharp/` root | Boss attack warning prompt |

---

## Common Attacks (CommonAttacks)

Located in `Gameplay/GameControllers/Bosses/CommonAttacks/`, reusable boss attack patterns.

| File | Description |
|------|------|
| `BossEnemySpawn.cs` | Boss summons minions |
| `BossBoomerangProjectileAttack.cs` | Boomerang projectile attack |
| `BossCurvedProjectileAttack.cs` | Curved projectile attack |
| `BossStraightProjectileAttack.cs` | Straight projectile attack |

---

## Other Common Attacks

| File | Location | Description |
|------|------|------|
| `BossMachinegunShooter.cs` | `Gameplay/GameControllers/Bosses/Generic/Attacks/` | Boss machinegun/rapid fire attack |

---

## Directory Structure

```
Bosses/
├── Amanecidas/           # Golden Blades, Bejeweled Arrow, Chiselled Steel, Molten Thorn, Laudes
├── BejeweledSaint/       # Melquíades, The Exhumed Archbishop
├── BlindBaby/            # Expósito, Scion of Abjuration
├── BossFight/            # Common Boss Fight Management
├── BurntFace/            # Our Lady of the Charred Visage (BurntFace)
├── CommonAttacks/        # Common Attack Components
├── Crisanta/             # Crisanta of the Wrapped Agony
├── EcclesiaBros/         # Ecclesia Bros
│   ├── Esdras/           #   Esdras, of the Anointed Legion
│   └── Perpetua/         #   Perpetua
├── ElderBrother/         # Warden of the Silent Sorrow (DLC)
├── Generic/Attacks/      # Common Attacks (Supplementary)
├── HighWills/            # High Wills (DLC Finale)
├── Isidora/              # Isidora, Voice of the Dead (DLC)
├── Lesmes/               # Lesmes of the Cradle of Sorrow
├── PietyMonster/         # Ten Piedad
├── PontiffGiant/         # His Holiness Escribar
├── PontiffHusk/          # Pontiff Husk
├── PontiffOldman/        # Last Son of the Miracle
├── PontiffSword/         # Pontiff Sword
├── Quirce/               # Quirce, Returned By The Flames
├── Snake/                # Sierpes
└── TresAngustias/        # Tres Angustias
```

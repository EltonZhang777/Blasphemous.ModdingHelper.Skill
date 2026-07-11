# Player

Source code navigation for the Player System (Penitent). The active instance is accessible via `Core.Logic.Penitent`.

---

## Main Class

- `Penitent.cs` - Main class for the player character "Penitent", inherits `Entity`, aggregates all player subsystems (abilities, attack, animation, movement, input, audio, etc.). Active instance: `Core.Logic.Penitent`

## Ability System

- `Abilities/ActiveRiposte.cs` - Active riposte (counterattack after perfect block)
- `Abilities/AbilityDeactivator.cs` - Ability deactivator
- `Abilities/ChargedAttack.cs` - Charged attack
- `Abilities/Combo.cs` - Combo system
- `Abilities/Dash.cs` - Dash
- `Abilities/DrivePlayer.cs` - Drive player (forced movement control)
- `Abilities/FervourPenance.cs` - Fervour penance (consume fervour to restore health)
- `Abilities/FlaskRegenerationBalance.cs` - Flask regeneration balance
- `Abilities/GrabCliffLede.cs` - Grab cliff ledge
- `Abilities/GrabLadder.cs` - Grab ladder
- `Abilities/GroundAttack.cs` - Ground attack
- `Abilities/GuardSlide.cs` - Guard slide
- `Abilities/Healing.cs` - Healing (use flask)
- `Abilities/LungeAttack.cs` - Lunge attack
- `Abilities/MapShow.cs` - Show map
- `Abilities/Parry.cs` - Parry
- `Abilities/Pe01Balance.cs` - PE01 balance parameters
- `Abilities/PlayerIdleMode.cs` - Player idle mode
- `Abilities/PrayerUse.cs` - Prayer use
- `Abilities/RangeAttack.cs` - Ranged attack
- `Abilities/RangeAttackBalance.cs` - Ranged attack balance parameters
- `Abilities/SoftLanding.cs` - Soft landing (fall cushioning)
- `Abilities/UnlockableSkillId.cs` - Unlockable skill ID enum
- `Abilities/VerticalAttack.cs` - Vertical attack (up/down attack)
- `Abilities/WallJump.cs` - Wall jump

## Attack System

- `Attack/ChargedAttackProjectile.cs` - Charged attack projectile
- `Attack/CloisteredGemProjectileAttack.cs` - Cloistered gem projectile attack
- `Attack/PenitentAttack.cs` - Penitent attack main class
- `Attack/PenitentSword.cs` - Penitent sword (weapon entity)
- `Attack/RangeAttackExplosion.cs` - Ranged attack explosion
- `Attack/RangeAttackProjectile.cs` - Ranged attack projectile
- `Attack/SwordAnimatorInyector.cs` - Sword animator injector

## Movement System

- `Movement/CharacterMotionProfile.cs` - Character motion profile
- `Movement/GravityScaleManager.cs` - Gravity scale manager
- `Movement/PhysicsSwitcher.cs` - Physics switcher

## Input System

- `InputSystem/EntityRumble.cs` - Entity rumble (controller vibration feedback)
- `InputSystem/PlatformCharacterInput.cs` - Platform character input processing. The `Rewired` property (of type `Rewired.Player`) is the core input component

## Animation

- `Animator/AnimatorInyector.cs` - Animator injector
- `Animator/MaterialsPerDamageElement.cs` - Material switching by damage element
- `Animator/PenitentAttackAnimations.cs` - Penitent attack animations
- `Animator/PenitentMoveAnimations.cs` - Penitent movement animations

## Audio

- `Audio/PenitentAudio.cs` - Penitent audio management

## Damage

- `Damage/PenitentDamageArea.cs` - Penitent damage area

## Prayers

- `Prayers/TearHarvestEffect.cs` - Tear harvest effect
- `Prayers/ZambraTearsHarvestPrayer.cs` - Zambra's tear harvest prayer

## State Machine

- `States/Driven.cs` - Driven state (cutscene/cinematic forced control)
- `States/Playing.cs` - Normal gameplay state

## Spawning

- `Spawn/CherubRespawn.cs` - Cherub respawn
- `Spawn/FamiliarSpawner.cs` - Familiar spawner
- `Spawn/PenitentSpawner.cs` - Penitent spawner

## Effects

- `Effects/ActiveRiposteEffect.cs` - Active riposte visual effects
- `Effects/GuiltDropRecover.cs` - Guilt drop recovery
- `Effects/GuiltRecoverEffect.cs` - Guilt recovery effect

## Gizmos

- `Gizmos/PenitentSpawnPoint.cs` - Penitent spawn point (scene editor)
- `Gizmos/RootMotionDriver.cs` - Root motion driver

## Sensor

- `Sensor/FloorDistanceChecker.cs` - Floor distance checker

## External Dependencies

- `CreativeSpore.SmartColliders.PlatformCharacterController` - Platform character controller, handles player movement, collision and physics. Not in the Penitent/ directory, belongs to the SmartColliders plugin

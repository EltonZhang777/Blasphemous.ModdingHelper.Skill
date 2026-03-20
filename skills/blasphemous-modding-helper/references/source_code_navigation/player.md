# Player

List of important player-related code in Blasphemous source code.

---

## Gameplay.GameControllers.Penitent.Penitent

Class that represents the player character "Penitent" in Blasphemous. Its active instance that should be manipulated for modding purposes is `Core.Logic.Penitent`

## CreativeSpore.SmartColliders.PlatformCharacterController

Class that is in charge of player's movement, collision, and physics.

## Gameplay.GameControllers.Penitent.InputSystem.PlatformCharacterInput

Class that handles player's input. The `Rewired` property in this class (of type `Rewired.Player`) is its core component for handling player input.

## Gameplay.GameControllers.Entities.EntityStats

Class that handles all the stats of all entities in game (including player, enemies, bosses, etc.). For the player instance, use `Core.Logic.Penitent.Stats` to manipulate player stats.



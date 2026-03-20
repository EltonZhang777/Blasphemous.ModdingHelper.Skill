# Localization

List of important localization code components in Blasphemous source code.

---

## I2.Loc.LocalizationManager

**Static** class from the package `I2` that Blasphemous uses to handle localization storage and components. Localization strings are stored as `I2.Loc.LanguageSource` objects in the `List<LanguageSource> Sources` field of this class.

## I2.Loc.Localize

MonoBehavior script that is attached to text components in game to handle localization.

## Framework.Managers.LocalizationManager

Blasphemous's own localization manager that has more connections to other game components and managing. **DO NOT mistake this with `I2.Loc.LocalizationManager`**.
 
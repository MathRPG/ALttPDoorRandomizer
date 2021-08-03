# Overworld Randomizer

This is a overworld randomizer for _The Legend of Zelda: A Link to the Past_ for the SNES
based on the Door Randomizer found at [Aerinon's Github Project.](https://github.com/Aerinon/ALttPDoorRandomizer)
See https://alttpr.com/ for more details on the normal randomizer.

### Trackers & Guides

This is a very new mode of LTTPR so the tools and info is very limited.
- There is an [OW Rando Cheat Sheet](https://zelda.codemann8.com/images/shared/ow-rando-reference-sheet.png) that shows all the transitions that exist and are candidates for shuffle.
- There is OW tracking capability within the following trackers:
  - CodeTracker, an [EmoTracker](https://emotracker.net) package for LTTPR
  - [Community Tracker](https://alttptracker.dunka.net/)
- There is an [OW OWG Reference Sheet](https://zelda.codemann8.com/images/shared/ow-owg-reference-sheet.png) that shows all the in-logic places where boots/mirror clips and fake flippers are expected from the player.

# Known Issues
(Updated 2021-06-23)

### If you want to playtest this, know these things:
- Big Red Bomb may require bomb duping as ledge drops may be in the way of your path to the Pyramid Fairy crack
- Do NOT grab the Frogsmith until you have seen the Blacksmith location. Doing so may prevent you from continuing in your save file.
- If you fake flipper, beware of transitioning south. You could end up at the top of the waterfall in the southeast of either world. If you mistakenly drop down, it is important to NOT make any other movements and S+Q immediately when the game allows you to (might take several seconds, the game has to scroll back to the original point of water entry) or there will be a hardlock. Falling from the waterfall is avoidable but it is super easy to do as it is super close to the transition.
- In Crossed OW Tile Swap, there are some interesting bunny water-walk situations that can occur, these are mean to be out-of-logic but beware of logic bugs around this area.

### Known bugs:
- ~~In Mixed OW Tile Swap, Smith and Stumpy have issues when their tiles are swapped. Progression cannot be found on them when these tiles are swapped~~ (Fixed in 0.1.6.4)
- Screens that loop on itself and also have free-standing items, the sprites are duplicated and can cause item duplication
- When OWG are performed to enter mega-tile screens (large OW screens), there is a small chance that an incorrect VRAM reference value causes the map graphics to offset in increments of 16 pixels

# Feedback and Bug Reports

All feedback and dev conversation happens in the #ow-rando channel on the [ALTTP Randomizer discord](https://discordapp.com/invite/alttprandomizer).

# Installation from Source

Download the source code from the repository directly and put it in a folder of your choosing.

You must have Python installed (version 3.6 - 3.9 supported)

This program requires all python dependencies that are necessary to run Aerinon's Door Randomizer. Try running ```pip install missingdependency``` or ```python -m pip install missingdependency``` on the command line (replace ```missingdependency``` with the specific package that is missing) to install the dependency.

Alternatively, run ```resources/ci/common/local_install.py``` to install all the missing dependencies as well.

See the following link if you have additional trouble: https://github.com/codemann8/ALttPDoorRandomizer/blob/OverworldShuffle/docs/BUILDING.md

# Running the Program

To use the CLI, run ```DungeonRandomizer.py```.

Alternatively, run ```Gui.py``` for a simple graphical user interface.

# Settings

Only extra settings are found here. All door and entrance randomizer settings are supported. See their [readme](https://github.com/Aerinon/ALttPDoorRandomizer/blob/master/README.md)

## Overworld Layout Shuffle (--ow_shuffle)

### Vanilla

OW is not shuffled.

### Parallel

OW Transitions are shuffled, but both worlds will have a matching layout.

### Full

OW Transitions are shuffled within each world separately.

## Overworld Tile Swap (--ow_swap)

### Vanilla

OW tiles remain in their original worlds.

### Mixed

OW tiles are randomly chosen to become a part of the opposite world

### Crossed

OW tiles remain in their original world, but transitions can now be travel cross-world.

## Visual Representation of Main OW Shuffle Settings

![OW Shuffle Settings Combination](https://zelda.codemann8.com/images/shared/ow-modes.gif)

## Keep Similar Edges Together (--ow_keepsimilar)

This keeps similar edge transitions together. ie. The 2 west edges of Potion Shop will be paired to another set of two similar edges

## Flute Shuffle (--ow_fluteshuffle)

When enabled, new flute spots are generated and gives the player the option to cancel out of the flute menu by pressing X.

### Vanilla

Flute spots remain unchanged.

### Balanced

New flute spots are chosen at random, with restrictions that limit the promixity between other chosen flute spots.

### Random

New flute spots are chosen at random with minimum bias.


# Command Line Options

```
-h, --help
```

Show the help message and exit.

```
--ow_shuffle <mode>
```

For specifying the overworld layout shuffle you want as above. (default: vanilla)

```
--ow_swap <mode>
```

For specifying the overworld tile swap you want as above. (default: vanilla)

```
--ow_keepsimilar
```

This keeps similar edge transitions paired together with other pairs of transitions

```
--ow_fluteshuffle <mode>
```

For randomizing the flute spots around the overworld

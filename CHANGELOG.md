# Changelog

### 0.2.8.0
- ~Merged DR v1.0.1.0 - Pottery options, BPS support, MSU Resume, Collection Rate Counter~
- Various improvements to increase generation success rate and reduce generation time
- Fixed issue with playthru recognizing Aga accessibility
- Fixed issue with applying rules correctly to Murahdahla, fixing Murahdahla+Beatable issues
- Fixed issue with Flute+Rainstate, flute use is no longer in logic until Zelda is delivered

### 0.2.7.3
- Restructured OWR algorithm to include some additional scenarios not previously allowed
- Added new Inverted D-pad controls for Social Distortion (ie. Mirror Mode) support
- Crossed OWR/Special OW Areas are now included in the spoiler log
- Fixed default TF pieces with Trinity in Mystery
- Added bush crabs to rupee farm logic (only in non-enemizer)
- Updated tree pull logic to also require ability to kill most things

### 0.2.7.2
- Special OW Areas are now shuffled in Layout Shuffle (Zora/Hobo/Pedestal)
- Fixed some broken water region graph modelling, fixed some reachability logic
- Some minor code simplifications

### 0.2.7.1
- Map checks in Mixed OWR now will show the proper tile images when screens are swapped (ie. Pyramid shows in the LW if that screen is swapped)
- Added mystery seed number to spoiler log, so it is easier to match a spoiler log to a rom filename
- Added proper branch-specific versioning (ie. Dev branch has '-u' suffixing the version number while Release/Main branch does not)

### 0.2.7.0
- ~Merged DR v1.0.0.3 - MANY changes, major things listed below~
  - New Item Fills (Districts/Vanilla/Major Location/Dungeon)
  - New OW Map Prize Indicators (In ER, map checks can spoil dungeon locations with a user setting)
  - Forbidden Boss Items (Exclude certain dungeon items from dropping on bosses)
- Map checks in Mixed OWR now will show dungeon prizes for dungeons actually in the world you map check on
- In Mixed OWR, Sanc screen must stay in LW if the starting location is guaranteed to exit at the Sanc entrance
- Fixed various issues with Flute logic
- Fixed issue that resulted in infinite loops in Flute Shuffle
- Changed map in attract mode to always show a vanilla LW map
- Various improvements to increase generation success rate

### 0.2.6.1
- Fixed issue with mirror bonking deleting portal in Crossed OW
- Fixed issue with mirror portal not spawning when entering the OW from the DW, in Crossed OW
- Updated some text with proper capitalization/spacing
- Updated tournament winners text

### 0.2.6.0
- New text engine font!
- Fixed invisible Witch item bug
- Added 'O' to ROM Header for autotrackers
- Fixed generation error with Shopsanity + OWR Layout
- Fixed OWR validation error with Insanity ER + OWR Layout
- Fixed issue with TR Peg Puzzle not spawning a valid portal

### 0.2.5.3
- Changed AT/GT Swap to favor vanilla, only swapping if GT entrance is the only choice in starting world
- Fixed issue with Links House not swapping in OW Mixed
- Added Flute Spots to spoiler log
- Fixed issue with Light Hype Fairy excluded from bombable door list

### 0.2.5.1
- Fixed missing rule for Inverted VoO Portal access

### 0.2.5.0
- Many updates to Inverted OW Terrain:
    - Links House start now spawns in Big Bomb Shop
    - Old Man Cave/Bumper Cave returned to vanilla
    - Mountain Cave S+Q now spawns in his usual Cave
    - Flute Spot 1 is moved to Top of Dark Death Mountain
    - Ladder is removed from West Dark Death Mountain
    - When finding Flute, it comes pre-activated (will hear SFX on collecting)
    - Spiral and Mimic Cave are now bridged together
    - TR Peg Puzzle is restored but instead reveals a ladder
    - Houlihan now exits same place as Big Bomb Shop does (OWR branch always had this)
    - Ice Palace has been re-sealed to vanilla, portal moved to outer edge of moat
    - Glitched modes will now use vanilla terrain except where necessary
- Fixed errors with OW Layout Shuffle
- Fixed issue with incorrect Mirror bonking
- Fixed issue with old man follower death to Pyramid
- Fixed Hera boss music not playing when boss not defeated
- ~Merged DR v0.5.1.7 - TT boss trap door fix/Applied Glitched flag~

### 0.2.4.0
- Added Guaranteed OWR Reachability
- Fixed incorrect parity calc for Whirlpool Shuffle
- Fixed error with generating seeds with GUI
- CLI fixes for triforce piece arguments

### 0.2.3.6
- Added Trinity goal (8/10 default TF pieces)
- Many improvements to TFH pool allocation
- Fixed some issues with Multiworld generation with Custom Item Pools

### 0.2.3.5
- Fixed issue with multiworld generation
- Added infinite loop detection
- Move mirror portal off screen during mirror bonk in Crossed OW

### 0.2.3.4
- Fixed major issue with subsequent seeds using same seed/settings resulting different
- Flute Shuffle now awards separated regions a prorated number of flute spots based on size
- Fixed spoiler log, was missing OW Tile Swap map
- Fixed spoiler log JSON output
- Fake flipper damage fix improved to skip the long delay after the scroll
- Fixed missing Blue Potion in Lake Shop in Inverted
- Added legacy OW Crossed option 'None (Allowed)' to support old behavior when invalid option was used in Mystery
- ~Merged DR v0.5.1.6 - Money balancing fix/Boss logic fixes with Bombbag~

### 0.2.3.3
- Added OW Layout validation that reduces the cases where some screens are unreachable
- Fixed issue with mirror portals showing up in DW in Crossed OW
- Corrected Lost/Skull Woods Pass regions to be more accurate

### 0.2.3.0/1/2
- Fixed issue in Crossed OW where mirror portal sprites would disappear when changing worlds
- Added Big Red Bomb logic to support using residual mirror portals for later re-entry
- Suppressed irrelevant paths in spoiler playthru
- Suppressed identical paths in spoiler playthru if multiple locations within the same region contain progression

### 0.2.2.3
- Fixed GT entrance not being opened when Inverted and WDM is Tile Swapped
- The Goal sign is moved to the area where the hole will be (always in opposite world as starting)

### 0.2.2.2
- Fixed Whirlpool Shuffle with Grouped Crossed OW
- Made filename not spoil OWR in Mystery
- Fixed Triforce Hunt goal

### 0.2.2.1
- Allow normal Link speed with Old Man following if not in his cave or WDM
- Fixed issue with Flute exits not getting placed on the correct tiles
- Hints in Lite/Lean ER no longer refer to entrances that are guaranteed vanilla
- Added Links House entrance to hint candidate list in ER when it is shuffled
- Added Tile Swaps ASCII map to Spoiler Log when Tile Swap is enabled
- Fixed issue with Whirlpool Shuffle not abiding by Polar rules

### 0.2.2.0
- Delivering Big Red Bomb is now in logic
- Smith/Purple Chest have proper dynamic pathing to fix logical issues
- Fixed issue with bomb walls in OW not requiring moon pearl in DW

### 0.2.1.3
- New fake flipper handling to allow S+Q rather than insta-kill
- Fixed whirlpools in Crossed OW
- Spoiler fixes, incl. missing Starting Inventory in Spoiler
- Fixed music track change to Sanc music when Standard mode is delivering Zelda
- Fixed SP flooding issue
- Fixed issue with Shuffle Ganon in CLI/GUI
- ~Merged DR v0.5.1.5 - Mystery subweights~

### 0.2.1.2
- Fixed issue with whirlpools not changing world when in Crossed OW

### 0.2.1.1
- Many fixes to ER: infinite loops, preventing cross-world scenarios in non-cross-world modes
- Spoiler log improvements, outputs in stages so a Spoiler is available if an error occurs
- Added no_race option for Mystery
- Fixed output_path in Mystery to use the saved setting if none is specified on CLI

### 0.2.1.0
- Implemented Whirlpool Shuffle

### 0.2.0.0
- Massive overhaul of ER algorithm
- Added 2 new ER modes (Lite and Lean)
- Added new mystery options (Logic/Shuffle Ganon)
- Smith deletion on S+Q only occurs if Blacksmith not reachable from starting locations
- Spoiler log improvements to prevent spoiling in the beginning 'meta' section
- Various minor fixes and improvements
- ~Merged DR v0.5.1.4 - ROM bug fixes/keylogic improvements~

### 0.1.9.4
- Hotfix for bad 0.1.9.3 version

### 0.1.9.3
- Moved flute spot from Northwest Lake Hylia to Southeast Lake Hylia
- Fixed Links House start in Inverted ER
- Minor accuracy improvements to ER, mostly preparations for future work

### 0.1.9.2
- Fixed spoiler log and mystery for new Crossed/Mixed structure
- Minor preparations and tweaks to ER framework (added global Entrance/Exit pool)
- ~Merged DR v0.5.1.2 - Blind Prison shuffled outside TT/Keylogic Improvements~

### 0.1.9.1
- Fixed logic issue with leaving IP entrance not requiring flippers
- ~Merged DR v0.5.1.1 - Map Indicator Fix/Boss Shuffle Bias/Shop Hints~

### 0.1.9.0
- Expanded Crossed OW to four separate options, see Readme for details
- Crossed OW will now play a short SFX when changing worlds
- Improved Link/Bunny state in Crossed OW
- Fixed issue with TR Pegs when fluting directly from an area with hammerpegs
- Updated OW GUI layout

### 0.1.8.2
- Fixed issue with game crashing on using Flute
- Fixed issues with Link/Bunny state in Crossed OW
- Fixed issue with Standard+Parallel not using vanilla connections for Escape
- Fixed issue with Mystery for OW boolean options
- ~Merged DR v0.5.1.0 - Major Keylogic Update~

### 0.1.8.1
- Fixed issue with activating flute in DW (OW Mixed)
- Fixed issue with Parallel+Crossed not generating
- Fixed issue with Standard not generating
- Fixed issue with Swordless not generating
- Fixed logic for Graveyard Ledge and Kings Tomb

### 0.1.8.0
- Moved Crossed to its own checkbox option
- Removed Legacy ER shuffles
- Added OW Shuffle support for Plando module (needs user testing)
- Fixed issue with Sanc start at TR as bunny when it is LW
- Fixed issue with Pyramid Hole not getting shuffled
- ~Merged DR v0.5.0.3 - Minor DR fixes~

### 0.1.7.4
- Fixed issue with Mixed OW failing to generate when HC/Pyramid is swapped
- Various fixes to improve generation rates for Mixed OW Shuffle
- ~Merged DR v0.5.0.2 - Shuffle SFX~

### 0.1.7.3
- Fixed minor issue with ambient SFX stopping and starting on OW screen load
- MSU-1 changed to play LW2 (track 60) when Aga1 is killed instead of ped pull
- Added dynamic flute exits for all LW OW regions
- Improved spoiler log playthru pathing accuracy by including flute routing
- Fixed issue with generating a filename for vanilla OW settings

### 0.1.7.2
- Fixed music algorithm to play correct track in OW Shuffle
- Removed convenient portal on WDM in OW Layout Shuffle
- Fixed Mystery to not spoil OW Shuffle in filename

### 0.1.7.1
- Improved bomb logic to consider tree pulls, bush crabs, and stun prize
- Fixed Mystery to use new updated OW mode terminology

### 0.1.7.0
- Expanded new DR bomb logic to all modes (bomb usage in logic only if there is an unlimited supply of bombs available)
- ~Merged DR v0.5.0.1 - Bombbag mode / Enemizer fixes~

### 0.1.6.9
- ~Merged DR v0.4.0.12 - Secure random update / Credits fix~

### 0.1.6.8
- Implemented a smarter Balanced Flute Shuffle algorithm
- Fixed Collection Rate in credits
- Removed sortedcontainers dependency

### 0.1.6.7
- Mountain Entry and West Death Mountain are now Swapped independently (Old Man rescue is always in your starting world)
- Fixed issue with AT/GT access logic
- Improved spoiler log playthru accuracy
- Fixed Boss Music when boss room is entered thru straight stairs
- Suppressed in-dungeon music changes when DR is enabled
- Fixed issue with Pyramid Exit exiting to wrong location in ER
- ~Merged DR v0.4.0.11 - Various DR changes~

### 0.1.6.6
- ~Merged DR v0.4.0.9 - P/C Indicator / Credits fix / CLI Hints Fix~

### 0.1.6.5
- Reduced chance of diagonal flute spot in Balanced
- ~Merged DR v0.4.0.8 - Boss Indicator / Psuedo Boots / Quickswap Update / Credits Updates~

### 0.1.6.4
- Fixed Frogsmith and Stumpy and restored progression in these locations
- Added Blacksmith/Hammer Pegs to OW Tile Swap pool

### 0.1.6.3
- Fixed borked credits (and missing Sprite Author) when collection rate isn't 216 or if GTBK count isn't /22
- Added OW Rando in credits
- Actually merged in DR v0.4.0.7 (with no thanks to GitHub)

### 0.1.6.2
- Added Balanced option for Flute Shuffle
- Fixed issue with Flute Spot to Mountain Entry softlocking
- Fixed logic bug with Inverted Kakariko Portal

### 0.1.6.1
- Fixed issue with Flute Spot to VoO softlocking
- Fixed Houlihan to exit where Link's House does
- Fixed issue with jsonout not correctly showing rom mods for some OW Shuffle data

### 0.1.6.0
- Added Flute Shuffle setting
- Minor GUI changes

### 0.1.5.3
- Fixed issue with Aga portal mirror bonking in Mixed Shuffle
- Fixed issue with Frog/Dig Game edges duplicating in edge pool, causing Insanity-like behavior

### 0.1.5.2
- Partial revert of horizontal VRAM fix from v0.1.5.0

### 0.1.5.1
- Fixed issue with Flute Spot 7 logically connecting to the wrong area in Mixed/Crossed OW Shuffle
- Fixed issue with TR portal not requiring mitts when tile is swapped

### 0.1.5.0
- Added OW Tile Swap setting
- Fixed horizontal VRAM visual loading glitch on megatiles
- ~~Merged DR v0.4.0.7 - Fast Credits / Reduced Flashing / Sprite Author in Credits~~ Didn't fully merge

### 0.1.4.3
- ~Merged DR v0.4.0.6 - TT Maiden Attic Hint / DR Entrance Floor Mat Mods / Hard/Expert Item Pool Fix~

### 0.1.4.2
- Modified various OW map terrain specific to OW Shuffle
- Changed World check to table-based vs OW ID-based (should have no effect with current modes)
- ~Merged DR v0.4.0.5 - Mystery Boss Shuffle Fix / Swordless+Hard Item Pool Fix / Insanity+Inverted ER Fixes~

### 0.1.4.1
- Moved Inverted Pyramid Entrance to top of HC Ledge
- Fixed various issues with Inverted and Insanity

### 0.1.4.0
- Initial Inverted Implementation
- Fix for Kakariko Pond no longer requiring fake flipper

### 0.1.3.1
- Various logic fixes and region prep for Inverted
- Fixed muted MSU-1 music in door rando when descending GT Climb stairs
- Fixed Standard + Vanilla (thanks compiling)
- ~Merged DR v0.4.0.4 - Shuffle Link's House / Experimental Bunny Start / 10 Bomb Fix~

### 0.1.3.0
- Added OWG Logic for OW Shuffle
- ~Merged DR v0.4.0.2 - OWG Framework / YAML~

### 0.1.2.2
- Re-purposed OW Shuffle setting to Layout Shuffle
- Merged Parallel Worlds setting into Layout Shuffle
- Added guaranteed Flute hint for OW Shuffle modes

### 0.1.2.1
- Made possible fix for Standard
- ~Merged DR v0.3.1.10 - Fixed Standard generation~

### 0.1.2.0
- Added 'Parallel Worlds' toggle option
- Updated shuffle algorithm
- Renamed some OW areas

### 0.1.1.2
- If Link's current position fits within the incoming gap, Link will not get re-centered to the incoming gap
- Added Rule for Pearl required to drop down back of SW
- ~Merged DR v0.3.1.8 - Improved Shopsanity pricing - Fixed Retro generation~

### 0.1.1.1
- Fixed camera unlocking issue
- Changed default setting for DR to Vanilla

### 0.1.1.0
- Added 'Keep Similar Edges Together' toggle option
- Removed Duplicate Pyramid Ledge location, causing a Warning of unfilled location on generation

### 0.1.0.3
- Modified various logic rule for some OW locations

### 0.1.0.2
- Fixed error generating a bad Spoiler log

### 0.1.0.1
- Separated DR versioning from OR versioning
- Removed LW/DW flag toggle on transitions

### 0.1.0.0
- Initial release
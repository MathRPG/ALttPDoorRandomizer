import collections
import logging
from collections import deque

import OverworldGlitchRules
from BaseClasses import CollectionState, RegionType, DoorType, Entrance, CrystalBarrier, KeyRuleType, LocationType
from BaseClasses import PotFlags
from Dungeons import dungeon_table
from RoomData import DoorKind
from OverworldGlitchRules import overworld_glitches_rules


def set_rules(world, player):

    if world.logic[player] == 'nologic':
        logging.getLogger('').info('WARNING! Seeds generated under this logic often require major glitches and may be impossible!')
        world.get_region('Menu', player).can_reach_private = lambda state: True
        for exit in world.get_region('Menu', player).exits:
            exit.hide_path = True
        return

    global_rules(world, player)
    default_rules(world, player)
    ow_rules(world, player)

    ow_bunny_rules(world, player)

    if world.mode[player] == 'standard':
        if world.get_region('Big Bomb Shop', player).entrances: # just some location that is placed late in the ER algorithm, prevent standard rules from applying when trying to search reachability in the overworld
            standard_rules(world, player)
    elif world.mode[player] == 'open' or world.mode[player] == 'inverted':
        open_rules(world, player)
    else:
        raise NotImplementedError('Not implemented yet')

    bomb_rules(world, player)
    pot_rules(world, player)

    if world.logic[player] == 'noglitches':
        no_glitches_rules(world, player)
    elif world.logic[player] == 'minorglitches':
        logging.getLogger('').info('Minor Glitches may be buggy still. No guarantee for proper logic checks.')
        no_glitches_rules(world, player)
        fake_flipper_rules(world, player)
    elif world.logic[player] == 'owglitches':
        logging.getLogger('').info('There is a chance OWG has bugged edge case rulesets, especially in inverted. Definitely file a report on GitHub if you see anything strange.')
        # Initially setting no_glitches_rules to set the baseline rules for some
        # entrances. The overworld_glitches_rules set is primarily additive.
        no_glitches_rules(world, player)
        fake_flipper_rules(world, player)
        overworld_glitches_rules(world, player)
    else:
        raise NotImplementedError('Not implemented yet')

    if world.goal[player] == 'dungeons':
        # require all dungeons to beat ganon
        add_rule(world.get_location('Ganon', player), lambda state: state.can_reach('Master Sword Pedestal', 'Location', player) and state.has('Beat Agahnim 1', player) and state.has('Beat Agahnim 2', player) and state.has_crystals(7, player))
    elif world.goal[player] == 'ganon':
        # require aga2 to beat ganon
        add_rule(world.get_location('Ganon', player), lambda state: state.has('Beat Agahnim 2', player))
    elif world.goal[player] in ['triforcehunt', 'trinity']:
        for location in world.get_region('Hyrule Castle Courtyard', player).locations:
            if location.name == 'Murahdahla':
                add_rule(location, lambda state: state.item_count('Triforce Piece', player) + state.item_count('Power Star', player) >= int(state.world.treasure_hunt_count[player]))

    # if swamp and dam have not been moved we require mirror for swamp palace
    if not world.swamp_patch_required[player]:
        add_rule(world.get_entrance('Swamp Lobby Moat', player), lambda state: state.has_Mirror(player))

    set_bunny_rules(world, player, world.mode[player] == 'inverted')


def mirrorless_path_to_location(world, startName, targetName, player):
    # If Agahnim is defeated then the courtyard needs to be accessible without using the mirror for the mirror offset glitch.
    # Only considering the secret passage for now (in non-insanity shuffle).  Basically, if it's Ganon you need the master sword.
    start = world.get_region(startName, player)
    target = world.get_region(targetName, player)
    is_same_world = start.type == target.type or target.type.is_indoors
    seen = {start}
    queue = collections.deque([(start, [])])
    while queue:
        (current, path) = queue.popleft()
        for entrance in current.exits:
            if (entrance.connected_region is not None and entrance.connected_region not in seen
                and (entrance.connected_region.type == start.type or entrance.connected_region.type.is_indoors
                    or (not is_same_world and ((world.mode[player] != 'inverted' and start.type == RegionType.LightWorld)
                        or (world.mode[player] == 'inverted' and start.type == RegionType.DarkWorld))))):
                new_path = path + [entrance.access_rule]
                if entrance.connected_region == target:
                    return new_path
                else:
                    queue.append((entrance.connected_region, new_path))
                    seen.add(entrance.connected_region)

def mirrorless_path_to_castle_courtyard(world, player):
    # If Agahnim is defeated then the courtyard needs to be accessible without using the mirror for the mirror offset glitch.
    # Only considering the secret passage for now (in non-insanity shuffle).  Basically, if it's Ganon you need the master sword.
    start = world.get_entrance('Hyrule Castle Secret Entrance Drop', player)
    if start.connected_region == world.get_region('Sewer Drop', player):
        return [lambda state: False]  # not handling dungeons for now
    target = world.get_region('Hyrule Castle Courtyard', player)
    seen = {start.parent_region, start.connected_region}
    queue = collections.deque([(start.connected_region, [])])
    while queue:
        (current, path) = queue.popleft()
        if current:
            for entrance in current.exits:
                if entrance.connected_region not in seen:
                    new_path = path + [entrance.access_rule]
                    if entrance.connected_region == target:
                        return new_path
                    else:
                        queue.append((entrance.connected_region, new_path))
                        seen.add(entrance.connected_region)

def set_rule(spot, rule):
    spot.access_rule = rule

def set_defeat_dungeon_boss_rule(location):
    # Lambda required to defer evaluation of dungeon.boss since it will change later if boos shuffle is used
    set_rule(location, lambda state: location.parent_region.dungeon.boss.can_defeat(state))

def set_always_allow(spot, rule):
    spot.always_allow = rule

def add_rule(spot, rule, combine='and'):
    old_rule = spot.access_rule
    if combine == 'or':
        spot.access_rule = lambda state: rule(state) or old_rule(state)
    else:
        spot.access_rule = lambda state: rule(state) and old_rule(state)

def add_bunny_rule(spot, player):
    add_rule(spot, lambda state: state.is_not_bunny(spot.parent_region, player))


def or_rule(rule1, rule2):
    return lambda state: rule1(state) or rule2(state)


def add_lamp_requirement(spot, player):
    add_rule(spot, lambda state: state.has('Lamp', player, state.world.lamps_needed_for_dark_rooms))


def forbid_item(location, item, player):
    old_rule = location.item_rule
    location.item_rule = lambda i: (i.name != item or i.player != player) and old_rule(i)

def add_item_rule(location, rule):
    old_rule = location.item_rule
    location.item_rule = lambda item: rule(item) and old_rule(item)

def item_in_locations(state, item, player, locations):
    for location in locations:
        if item_name(state, location[0], location[1]) == (item, player):
            return True
    return False

def item_name(state, location, player):
    location = state.world.get_location(location, player)
    if location.item is None:
        return None
    return (location.item.name, location.item.player)

def global_rules(world, player):
    # ganon can only carry triforce
    add_item_rule(world.get_location('Ganon', player), lambda item: item.name == 'Triforce' and item.player == player)

    # we can s&q to the old man house after we rescue him. This may be somewhere completely different if caves are shuffled!
    world.get_region('Menu', player).can_reach_private = lambda state: True
    for exit in world.get_region('Menu', player).exits:
        exit.hide_path = True
    
    world.get_region('Flute Sky', player).can_reach_private = lambda state: True
    #for exit in world.get_region('Flute Sky', player).exits:
    #    exit.hide_path = True

    set_rule(world.get_entrance('Old Man S&Q', player), lambda state: state.can_reach('Old Man', 'Location', player))

    set_rule(world.get_entrance('Flute Spot 1', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 2', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 3', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 4', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 5', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 6', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 7', player), lambda state: state.can_flute(player))
    set_rule(world.get_entrance('Flute Spot 8', player), lambda state: state.can_flute(player))
    
    set_rule(world.get_location('Sunken Treasure', player), lambda state: state.has('Open Floodgate', player))
    set_rule(world.get_location('Dark Blacksmith Ruins', player), lambda state: state.has('Return Smith', player))
    set_rule(world.get_location('Middle Aged Man', player), lambda state: state.has('Pick Up Purple Chest', player))  # Can S&Q with chest
    set_rule(world.get_location('Purple Chest', player), lambda state: state.has('Deliver Purple Chest', player))  # Can S&Q with chest
    set_rule(world.get_location('Big Bomb', player), lambda state: state.has('Crystal 5', player) and state.has('Crystal 6', player))
    set_rule(world.get_location('Pyramid Crack', player), lambda state: state.has('Pick Up Big Bomb', player))
    set_rule(world.get_entrance('Pyramid Fairy', player), lambda state: state.has('Detonate Big Bomb', player))
    set_rule(world.get_location('Master Sword Pedestal', player), lambda state: state.has('Red Pendant', player) and state.has('Blue Pendant', player) and state.has('Green Pendant', player))

    set_rule(world.get_location('Missing Smith', player), lambda state: state.has('Get Frog', player))
    set_rule(world.get_location('Blacksmith', player), lambda state: state.has('Return Smith', player))
    set_rule(world.get_location('Magic Bat', player), lambda state: state.has('Magic Powder', player))
    set_rule(world.get_location('Sick Kid', player), lambda state: state.has_bottle(player))
    set_rule(world.get_location('Library', player), lambda state: state.has_Boots(player))
    set_rule(world.get_location('Mimic Cave', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_location('Sahasrahla', player), lambda state: state.has('Green Pendant', player))

    set_rule(world.get_location('Spike Cave', player), lambda state:
             state.has('Hammer', player) and state.can_lift_rocks(player) and
             ((state.has('Cape', player) and state.can_extend_magic(player, 16, True)) or
             (state.has('Cane of Byrna', player) and
              (state.can_extend_magic(player, 12, True) or
              (state.world.can_take_damage and (state.has_Boots(player) or state.has_hearts(player, 4))))))
             )

    set_rule(world.get_location('Hookshot Cave - Top Right', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_location('Hookshot Cave - Top Left', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_location('Hookshot Cave - Bottom Right', player), lambda state: state.has('Hookshot', player) or state.has('Pegasus Boots', player))
    set_rule(world.get_location('Hookshot Cave - Bottom Left', player), lambda state: state.has('Hookshot', player))

    set_rule(world.get_entrance('Hookshot Cave Bonk Path', player), lambda state: state.has('Hookshot', player) or state.has('Pegasus Boots', player))
    set_rule(world.get_entrance('Hookshot Cave Hook Path', player), lambda state: state.has('Hookshot', player))

    # Start of door rando rules
    # TODO: Do these need to flag off when door rando is off? - some of them, yes

    # Eastern Palace
    # Eyegore room needs a bow
    set_rule(world.get_entrance('Eastern Duo Eyegores NE', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('Eastern Single Eyegore NE', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('Eastern Map Balcony Hook Path', player), lambda state: state.has('Hookshot', player))

    # Boss rules. Same as below but no BK or arrow requirement.
    set_defeat_dungeon_boss_rule(world.get_location('Eastern Palace - Prize', player))
    set_defeat_dungeon_boss_rule(world.get_location('Eastern Palace - Boss', player))

    # Desert
    set_rule(world.get_location('Desert Palace - Torch', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('Desert Wall Slide NW', player), lambda state: state.has_fire_source(player))
    set_defeat_dungeon_boss_rule(world.get_location('Desert Palace - Prize', player))
    set_defeat_dungeon_boss_rule(world.get_location('Desert Palace - Boss', player))

    # Tower of Hera
    set_rule(world.get_location('Tower of Hera - Big Key Chest', player), lambda state: state.has_fire_source(player))
    set_rule(world.get_entrance('Hera Big Chest Hook Path', player), lambda state: state.has('Hookshot', player))
    set_defeat_dungeon_boss_rule(world.get_location('Tower of Hera - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Tower of Hera - Prize', player))

    # Castle Tower
    set_rule(world.get_entrance('Tower Gold Knights SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Gold Knights EN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Dark Archers WN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Red Spears WN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Red Guards EN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Red Guards SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('Tower Altar NW', player), lambda state: state.has_sword(player))
    set_defeat_dungeon_boss_rule(world.get_location('Agahnim 1', player))


    set_rule(world.get_entrance('PoD Arena Landing Bonk Path', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('PoD Mimics 1 NW', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('PoD Mimics 2 NW', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('PoD Bow Statue Down Ladder', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('PoD Map Balcony Drop Down', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('PoD Dark Pegs Landing to Right', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('PoD Dark Pegs Right to Landing', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('PoD Turtle Party NW', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('PoD Turtle Party ES', player), lambda state: state.has('Hammer', player))
    set_defeat_dungeon_boss_rule(world.get_location('Palace of Darkness - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Palace of Darkness - Prize', player))

    set_rule(world.get_entrance('Swamp Lobby Moat', player), lambda state: state.has('Flippers', player) and state.has('Open Floodgate', player))
    set_rule(world.get_entrance('Swamp Entrance Moat', player), lambda state: state.has('Flippers', player) and state.has('Open Floodgate', player))
    set_rule(world.get_entrance('Swamp Trench 1 Approach Dry', player), lambda state: not state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Key Ledge Dry', player), lambda state: not state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Departure Dry', player), lambda state: not state.has('Trench 1 Filled', player))
    # these two are here so that, if they flood the area before finding flippers, nothing behind there can lock out the flippers
    set_rule(world.get_entrance('Swamp Trench 1 Nexus Approach', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Swamp Trench 1 Nexus Key', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Swamp Trench 1 Approach Key', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Approach Swim Depart', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Key Approach', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Key Ledge Depart', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Departure Approach', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 1 Departure Key', player), lambda state: state.has('Flippers', player) and state.has('Trench 1 Filled', player))
    set_rule(world.get_location('Trench 1 Switch', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Swamp Hub Hook Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Swamp Hub Side Hook Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_location('Swamp Palace - Hookshot Pot Key', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Swamp Trench 2 Pots Dry', player), lambda state: not state.has('Trench 2 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 2 Pots Wet', player), lambda state: state.has('Flippers', player) and state.has('Trench 2 Filled', player))
    set_rule(world.get_entrance('Swamp Trench 2 Departure Wet', player), lambda state: state.has('Flippers', player) and state.has('Trench 2 Filled', player))
    set_rule(world.get_entrance('Swamp West Ledge Hook Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Swamp Barrier Ledge Hook Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Swamp Drain Right Switch', player), lambda state: state.has('Drained Swamp', player))
    set_rule(world.get_entrance('Swamp Drain WN', player), lambda state: state.has('Drained Swamp', player))
    # this might be unnecesssary for an insanity style shuffle
    set_rule(world.get_entrance('Swamp Flooded Room WS', player), lambda state: state.has('Drained Swamp', player))
    set_rule(world.get_entrance('Swamp Flooded Room Ladder', player), lambda state: state.has('Drained Swamp', player))
    set_rule(world.get_entrance('Swamp Flooded Spot Ladder', player), lambda state: state.has('Flippers', player) or state.has('Drained Swamp', player))
    set_rule(world.get_entrance('Swamp Drain Left Up Stairs', player), lambda state: state.has('Flippers', player) or state.has('Drained Swamp', player))
    set_rule(world.get_entrance('Swamp Waterway NW', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Swamp Waterway N', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Swamp Waterway NE', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_location('Swamp Palace - Waterway Pot Key', player), lambda state: state.has('Flippers', player))
    set_defeat_dungeon_boss_rule(world.get_location('Swamp Palace - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Swamp Palace - Prize', player))

    set_rule(world.get_entrance('Skull Big Chest Hookpath', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Skull Torch Room WN', player), lambda state: state.has('Fire Rod', player))
    set_rule(world.get_entrance('Skull Vines NW', player), lambda state: state.has_sword(player))
    set_rule(world.get_entrance('Skull 2 West Lobby Pits', player), lambda state: state.has_Boots(player) or state.has('Hidden Pits', player))
    set_rule(world.get_entrance('Skull 2 West Lobby Ledge Pits', player), lambda state: state.has('Hidden Pits', player))
    set_defeat_dungeon_boss_rule(world.get_location('Skull Woods - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Skull Woods - Prize', player))

    # blind can't have the small key? - not necessarily true anymore - but likely still

    set_rule(world.get_location('Thieves\' Town - Big Chest', player), lambda state: state.has('Hammer', player))
    for entrance in ['Thieves Basement Block Path', 'Thieves Blocked Entry Path', 'Thieves Conveyor Block Path', 'Thieves Conveyor Bridge Block Path']:
        set_rule(world.get_entrance(entrance, player), lambda state: state.can_lift_rocks(player))

    # I think these rules are unnecessary now - testing needed
    # for location in ['Thieves\' Town - Blind\'s Cell', 'Thieves\' Town - Boss']:
    #     forbid_item(world.get_location(location, player), 'Big Key (Thieves Town)', player)
    # forbid_item(world.get_location('Thieves\' Town - Blind\'s Cell', player), 'Big Key (Thieves Town)', player)
    # for location in ['Suspicious Maiden', 'Thieves\' Town - Blind\'s Cell']:
    #     set_rule(world.get_location(location, player), lambda state: state.has('Big Key (Thieves Town)', player))
    set_rule(world.get_location('Revealing Light', player), lambda state: state.has('Shining Light', player) and state.has('Maiden Rescued', player))
    set_rule(world.get_location('Thieves\' Town - Boss', player), lambda state: state.has('Maiden Unmasked', player) and world.get_location('Thieves\' Town - Boss', player).parent_region.dungeon.boss.can_defeat(state))
    set_rule(world.get_location('Thieves\' Town - Prize', player), lambda state: state.has('Maiden Unmasked', player) and world.get_location('Thieves\' Town - Prize', player).parent_region.dungeon.boss.can_defeat(state))

    set_rule(world.get_entrance('Ice Lobby WS', player), lambda state: state.can_melt_things(player))
    set_rule(world.get_entrance('Ice Hammer Block ES', player), lambda state: state.can_lift_rocks(player) and state.has('Hammer', player))
    set_rule(world.get_location('Ice Palace - Hammer Block Key Drop', player), lambda state: state.can_lift_rocks(player) and state.has('Hammer', player))
    set_rule(world.get_location('Ice Palace - Map Chest', player), lambda state: state.can_lift_rocks(player) and state.has('Hammer', player))
    set_rule(world.get_entrance('Ice Antechamber Hole', player), lambda state: state.can_lift_rocks(player) and state.has('Hammer', player))
    # todo: ohko rules for spike room - could split into two regions instead of these, but can_take_damage is usually true
    set_rule(world.get_entrance('Ice Spike Room WS', player), lambda state: state.world.can_take_damage or state.has('Hookshot', player) or state.has('Cape', player) or state.has('Cane of Byrna', player))
    set_rule(world.get_entrance('Ice Spike Room Up Stairs', player), lambda state: state.world.can_take_damage or state.has('Hookshot', player) or state.has('Cape', player) or state.has('Cane of Byrna', player))
    set_rule(world.get_entrance('Ice Spike Room Down Stairs', player), lambda state: state.world.can_take_damage or state.has('Hookshot', player) or state.has('Cape', player) or state.has('Cane of Byrna', player))
    set_rule(world.get_location('Ice Palace - Spike Room', player), lambda state: state.world.can_take_damage or state.has('Hookshot', player) or state.has('Cape', player) or state.has('Cane of Byrna', player))
    set_rule(world.get_location('Ice Palace - Freezor Chest', player), lambda state: state.can_melt_things(player))
    set_rule(world.get_entrance('Ice Hookshot Ledge Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Ice Hookshot Balcony Path', player), lambda state: state.has('Hookshot', player))
    if not world.get_door('Ice Switch Room SE', player).entranceFlag:
        set_rule(world.get_entrance('Ice Switch Room SE', player), lambda state: state.has('Cane of Somaria', player) or state.has('Convenient Block', player))
    set_defeat_dungeon_boss_rule(world.get_location('Ice Palace - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Ice Palace - Prize', player))

    set_rule(world.get_entrance('Mire Lobby Gap', player), lambda state: state.has_Boots(player) or state.has('Hookshot', player))
    set_rule(world.get_entrance('Mire Post-Gap Gap', player), lambda state: state.has_Boots(player) or state.has('Hookshot', player))
    set_rule(world.get_entrance('Mire Falling Bridge WN', player), lambda state: state.has_Boots(player) or state.has('Hookshot', player))  # this is due to the fact the the door opposite is blocked
    set_rule(world.get_entrance('Mire 2 NE', player), lambda state: state.has_sword(player) or
             (state.has('Fire Rod', player) and (state.can_use_bombs(player) or state.can_extend_magic(player, 9))) or  # 9 fr shots or 8 with some bombs
             (state.has('Ice Rod', player) and state.can_use_bombs(player)) or  # freeze popo and throw, bomb to finish
             state.has('Hammer', player) or state.has('Cane of Somaria', player) or state.can_shoot_arrows(player))  # need to defeat wizzrobes, bombs don't work ...
            # byrna could work with sufficient magic
    set_rule(world.get_location('Misery Mire - Spike Chest', player), lambda state: (state.world.can_take_damage and state.has_hearts(player, 4)) or state.has('Cane of Byrna', player) or state.has('Cape', player))
    loc = world.get_location('Misery Mire - Spikes Pot Key', player)
    if loc.pot.x == 48 and loc.pot.y == 28:  # pot shuffled to spike area
        set_rule(loc, lambda state: (state.world.can_take_damage and state.has_hearts(player, 4)) or state.has('Cane of Byrna', player) or state.has('Cape', player))
    set_rule(world.get_entrance('Mire Left Bridge Hook Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Mire Tile Room NW', player), lambda state: state.has_fire_source(player))
    set_rule(world.get_entrance('Mire Attic Hint Hole', player), lambda state: state.has_fire_source(player))
    set_rule(world.get_entrance('Mire Dark Shooters SW', player), lambda state: state.has('Cane of Somaria', player))

    set_defeat_dungeon_boss_rule(world.get_location('Misery Mire - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Misery Mire - Prize', player))

    set_rule(world.get_entrance('TR Main Lobby Gap', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Lobby Ledge Gap', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub SW', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub SE', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub ES', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub EN', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub NW', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub NE', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub Path', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Hub Ledges Path', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Torches NW', player), lambda state: state.has('Cane of Somaria', player) and state.has('Fire Rod', player))
    set_rule(world.get_entrance('TR Big Chest Entrance Gap', player), lambda state: state.has('Cane of Somaria', player) or state.has('Hookshot', player))
    set_rule(world.get_entrance('TR Big Chest Gap', player), lambda state: state.has('Cane of Somaria', player) or state.has_Boots(player))
    set_rule(world.get_entrance('TR Dark Ride Up Stairs', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Dark Ride SW', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Dark Ride Path', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Dark Ride Ledges Path', player), lambda state: state.has('Cane of Somaria', player))
    for location in world.get_region('TR Dark Ride Ledges', player).locations:
        set_rule(location, lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Final Abyss Balcony Path', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('TR Final Abyss Ledge Path', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_location('Turtle Rock - Eye Bridge - Bottom Left', player), lambda state: state.has('Cane of Byrna', player) or state.has('Cape', player) or state.has('Mirror Shield', player))
    set_rule(world.get_location('Turtle Rock - Eye Bridge - Bottom Right', player), lambda state: state.has('Cane of Byrna', player) or state.has('Cape', player) or state.has('Mirror Shield', player))
    set_rule(world.get_location('Turtle Rock - Eye Bridge - Top Left', player), lambda state: state.has('Cane of Byrna', player) or state.has('Cape', player) or state.has('Mirror Shield', player))
    set_rule(world.get_location('Turtle Rock - Eye Bridge - Top Right', player), lambda state: state.has('Cane of Byrna', player) or state.has('Cape', player) or state.has('Mirror Shield', player))
    set_defeat_dungeon_boss_rule(world.get_location('Turtle Rock - Boss', player))
    set_defeat_dungeon_boss_rule(world.get_location('Turtle Rock - Prize', player))

    set_rule(world.get_location('Ganons Tower - Bob\'s Torch', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('GT Hope Room EN', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('GT Conveyor Cross WN', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('GT Conveyor Cross EN', player), lambda state: state.has('Hookshot', player))
    if not world.get_door('GT Speed Torch SE', player).entranceFlag:
        set_rule(world.get_entrance('GT Speed Torch SE', player), lambda state: state.has('Fire Rod', player))
    set_rule(world.get_entrance('GT Hookshot South-Mid Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('GT Hookshot Mid-North Path', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('GT Hookshot East-Mid Path', player), lambda state: state.has('Hookshot', player) or state.has_Boots(player))
    set_rule(world.get_entrance('GT Hookshot North-Mid Path', player), lambda state: state.has('Hookshot', player) or state.has_Boots(player))
    set_rule(world.get_entrance('GT Hookshot Mid-South Path', player), lambda state: state.has('Hookshot', player) or state.has_Boots(player))
    set_rule(world.get_entrance('GT Hookshot Mid-East Path', player), lambda state: state.has('Hookshot', player) or state.has_Boots(player))
    set_rule(world.get_entrance('GT Firesnake Room Hook Path', player), lambda state: state.has('Hookshot', player))

    # I am tempted to stick an invincibility rule for getting across falling bridge
    set_rule(world.get_entrance('GT Ice Armos NE', player), lambda state: world.get_region('GT Ice Armos', player).dungeon.bosses['bottom'].can_defeat(state))
    set_rule(world.get_entrance('GT Ice Armos WS', player), lambda state: world.get_region('GT Ice Armos', player).dungeon.bosses['bottom'].can_defeat(state))

    set_rule(world.get_entrance('GT Mimics 1 NW', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('GT Mimics 1 ES', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('GT Mimics 2 WS', player), lambda state: state.can_shoot_arrows(player))
    set_rule(world.get_entrance('GT Mimics 2 NE', player), lambda state: state.can_shoot_arrows(player))
    # consider access to refill room
    set_rule(world.get_entrance('GT Gauntlet 1 WN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 2 EN', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 2 SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 3 NW', player), lambda state: state.can_kill_most_things(player))
    if not world.get_door('GT Gauntlet 3 SW', player).entranceFlag:
        set_rule(world.get_entrance('GT Gauntlet 3 SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 4 NW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 4 SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 5 NW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Gauntlet 5 WS', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Wizzrobes 1 SW', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Wizzrobes 2 SE', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Wizzrobes 2 NE', player), lambda state: state.can_kill_most_things(player))
    set_rule(world.get_entrance('GT Lanmolas 2 ES', player), lambda state: world.get_region('GT Lanmolas 2', player).dungeon.bosses['middle'].can_defeat(state))
    set_rule(world.get_entrance('GT Lanmolas 2 NW', player), lambda state: world.get_region('GT Lanmolas 2', player).dungeon.bosses['middle'].can_defeat(state))
    set_rule(world.get_entrance('GT Torch Cross ES', player), lambda state: state.has_fire_source(player))
    set_rule(world.get_entrance('GT Falling Torches NE', player), lambda state: state.has_fire_source(player))
    # todo: the following only applies to crystal state propagation from this supertile
    # you can also reset the supertile, but I'm not sure how to model that
    set_rule(world.get_entrance('GT Falling Torches Down Ladder', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('GT Moldorm Gap', player), lambda state: state.has('Hookshot', player) and world.get_region('GT Moldorm', player).dungeon.bosses['top'].can_defeat(state))
    set_defeat_dungeon_boss_rule(world.get_location('Agahnim 2', player))

    # crystal switch rules
    if world.get_door('Thieves Attic ES', player).crystal == CrystalBarrier.Blue:
        set_rule(world.get_entrance('Thieves Attic ES', player), lambda state: state.can_reach_blue(world.get_region('Thieves Attic', player), player))
    else:
        set_rule(world.get_entrance('Thieves Attic ES', player), lambda state: state.can_reach_orange(world.get_region('Thieves Attic', player), player))
    set_rule(world.get_entrance('Thieves Attic Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Thieves Attic', player), player))
    set_rule(world.get_entrance('Thieves Attic Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Thieves Attic', player), player))

    set_rule(world.get_entrance('Hera Lobby to Front Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Hera Lobby', player), player))
    set_rule(world.get_entrance('Hera Front to Lobby Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Hera Front', player), player))
    set_rule(world.get_entrance('Hera Front to Down Stairs Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Hera Front', player), player))
    set_rule(world.get_entrance('Hera Down Stairs to Front Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Hera Down Stairs Landing', player), player))
    set_rule(world.get_entrance('Hera Front to Up Stairs Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('Hera Front', player), player))
    set_rule(world.get_entrance('Hera Up Stairs to Front Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('Hera Up Stairs Landing', player), player))
    set_rule(world.get_entrance('Hera Front to Back Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('Hera Front', player), player))
    set_rule(world.get_entrance('Hera Back to Front Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('Hera Back', player), player))
    set_rule(world.get_location('Tower of Hera - Basement Cage', player), lambda state: state.can_reach_orange(world.get_region('Hera Basement Cage', player), player))
    set_rule(world.get_entrance('Hera Tridorm WN', player), lambda state: state.can_reach_blue(world.get_region('Hera Tridorm', player), player))
    set_rule(world.get_entrance('Hera Tridorm SE', player), lambda state: state.can_reach_orange(world.get_region('Hera Tridorm', player), player))
    set_rule(world.get_entrance('Hera Tile Room EN', player), lambda state: state.can_reach_blue(world.get_region('Hera Tile Room', player), player))

    set_rule(world.get_entrance('Hera Lobby to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Hera Front to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Hera Down Stairs Landing to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or (state.has('Hookshot', player) and state.can_reach_blue(world.get_region('Hera Down Stairs Landing', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('Hera Up Stairs Landing to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or (state.has('Hookshot', player) and state.can_reach_orange(world.get_region('Hera Up Stairs Landing', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('Hera Back to Ranged Crystal', player), lambda state: state.can_shoot_arrows(player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player))  # or state.has_beam_sword(player) or (state.has('Hookshot', player) and state.has('Red Boomerang', player))
    set_rule(world.get_entrance('Hera Front to Back Bypass', player), lambda state: state.can_use_bombs(player) or state.can_shoot_arrows(player) or state.has('Red Boomerang', player) or state.has('Blue Boomerang', player) or state.has('Cane of Somaria', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player)) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('Hera Basement Cage to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Hera Tridorm to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Hera Startile Wide to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Hera 5F Orange Path', player), lambda state: state.can_reach_orange(world.get_region('Hera 5F', player), player))

    set_rule(world.get_entrance('PoD Arena North to Landing Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Arena North', player), player))
    set_rule(world.get_entrance('PoD Arena Landing to North Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Arena Landing', player), player))
    set_rule(world.get_entrance('PoD Arena Main to Landing Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Arena Main', player), player))
    set_rule(world.get_entrance('PoD Arena Landing to Main Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Arena Landing', player), player))
    set_rule(world.get_entrance('PoD Arena Landing to Right Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Arena Landing', player), player))
    set_rule(world.get_entrance('PoD Arena Right to Landing Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Arena Right', player), player))
    set_rule(world.get_entrance('PoD Bow Statue Left to Right Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Bow Statue Left', player), player))
    set_rule(world.get_entrance('PoD Bow Statue Right to Left Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Bow Statue Right', player), player))
    set_rule(world.get_entrance('PoD Dark Pegs Right to Middle Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Dark Pegs Right', player), player))
    set_rule(world.get_entrance('PoD Dark Pegs Middle to Right Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('PoD Dark Pegs Middle', player), player))
    set_rule(world.get_entrance('PoD Dark Pegs Middle to Left Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Dark Pegs Middle', player), player))
    set_rule(world.get_entrance('PoD Dark Pegs Left to Middle Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('PoD Dark Pegs Left', player), player))

    set_rule(world.get_entrance('PoD Arena Main to Ranged Crystal', player), lambda state: True) # Can always throw pots here
    set_rule(world.get_entrance('PoD Arena Main to Landing Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('PoD Arena Main to Right Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('PoD Arena Bridge to Ranged Crystal', player), lambda state: state.can_shoot_arrows(player) or state.has('Red Boomerang', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player)) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('PoD Arena Right to Ranged Crystal', player), lambda state: False) # (state.has('Cane of Somaria', player) and state.has_Boots(player))
    set_rule(world.get_entrance('PoD Arena Ledge to Ranged Crystal', player), lambda state: False) # state.has('Cane of Somaria', player) or state.has_beam_sword(player)
    set_rule(world.get_entrance('PoD Map Balcony to Ranged Crystal', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player)) # or state.has('Red Boomerang', player)
    set_rule(world.get_entrance('PoD Bow Statue Left to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('PoD Bow Statue Right to Ranged Crystal', player), lambda state: state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('PoD Bow Statue Left to Right Bypass', player), lambda state: state.has('Cane of Somaria', player) or state.can_use_bombs(player) or state.can_shoot_arrows(player) or state.has('Red Boomerang', player) or state.has('Ice Rod', player) or state.has('Fire Rod', player)) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('PoD Dark Pegs Landing to Ranged Crystal', player), lambda state: state.has('Cane of Somaria', player)) # or state.can_use_bombs(player) or state.has('Blue boomerang', player) or state.has('Red boomerang', player)
    set_rule(world.get_entrance('PoD Dark Pegs Middle to Ranged Crystal', player), lambda state: state.can_shoot_arrows(player) or state.can_use_bombs(player) or state.has('Red Boomerang', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player) or (state.has('Hookshot', player) and state.can_reach_orange(world.get_region('PoD Dark Pegs Middle', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('PoD Dark Pegs Left to Ranged Crystal', player), lambda state: state.can_shoot_arrows(player) or state.has('Red Boomerang', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player)) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('PoD Dark Pegs Right to Middle Bypass', player), lambda state: state.has('Blue Boomerang', player))
    set_rule(world.get_entrance('PoD Dark Pegs Middle to Left Bypass', player), lambda state: state.can_use_bombs(player))

    set_rule(world.get_entrance('Swamp Crystal Switch Outer to Inner Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Swamp Trench 2 Pots', player), player))
    set_rule(world.get_entrance('Swamp Crystal Switch Inner to Outer Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('Swamp Trench 2 Pots', player), player))
    set_rule(world.get_entrance('Swamp Trench 2 Pots Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Swamp Trench 2 Pots', player), player))
    set_rule(world.get_entrance('Swamp Shortcut Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Swamp Shortcut', player), player))
    set_rule(world.get_entrance('Swamp Barrier Ledge - Orange', player), lambda state: state.can_reach_orange(world.get_region('Swamp Barrier Ledge', player), player))
    set_rule(world.get_entrance('Swamp Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('Swamp Barrier', player), player))

    set_rule(world.get_entrance('Swamp Crystal Switch Inner to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Swamp Crystal Switch Outer to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or state.has_beam_sword(player) or (state.has('Hookshot', player) and state.can_reach_blue(world.get_region('Swamp Crystal Switch Outer', player), player))) # It is the length of the sword, not the beam itself that allows this
    set_rule(world.get_entrance('Swamp Crystal Switch Outer to Inner Bypass', player), lambda state: state.world.can_take_damage or state.has('Cape', player) or state.has('Cane of Byrna', player))
    set_rule(world.get_entrance('Swamp Crystal Switch Inner to Outer Bypass', player), lambda state: state.world.can_take_damage or state.has('Cape', player) or state.has('Cane of Byrna', player))

    set_rule(world.get_entrance('Thieves Hellway Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Thieves Hellway', player), player))
    set_rule(world.get_entrance('Thieves Hellway Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Thieves Hellway', player), player))
    set_rule(world.get_entrance('Thieves Hellway Crystal Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Thieves Hellway N Crystal', player), player))
    set_rule(world.get_entrance('Thieves Hellway Crystal Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Thieves Hellway S Crystal', player), player))
    set_rule(world.get_entrance('Thieves Triple Bypass SE', player), lambda state: state.can_reach_blue(world.get_region('Thieves Triple Bypass', player), player))
    set_rule(world.get_entrance('Thieves Triple Bypass WN', player), lambda state: state.can_reach_blue(world.get_region('Thieves Triple Bypass', player), player))
    set_rule(world.get_entrance('Thieves Triple Bypass EN', player), lambda state: state.can_reach_blue(world.get_region('Thieves Triple Bypass', player), player))

    set_rule(world.get_entrance('Ice Crystal Right Blue Hole', player), lambda state: state.can_reach_blue(world.get_region('Ice Crystal Right', player), player))
    set_rule(world.get_entrance('Ice Crystal Right Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Ice Crystal Right', player), player))
    set_rule(world.get_entrance('Ice Crystal Left Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Ice Crystal Left', player), player))
    set_rule(world.get_entrance('Ice Crystal Left Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Ice Crystal Left', player), player))
    set_rule(world.get_entrance('Ice Backwards Room Hole', player), lambda state: state.can_reach_blue(world.get_region('Ice Backwards Room', player), player))
    set_rule(world.get_entrance('Ice Bomb Jump Ledge Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Ice Bomb Jump Ledge', player), player))
    set_rule(world.get_entrance('Ice Bomb Jump Catwalk Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Ice Bomb Jump Catwalk', player), player))

    set_rule(world.get_entrance('Ice Conveyor to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Ice Refill to Crystal', player), lambda state: state.can_hit_crystal(player) or state.can_reach_blue(world.get_region('Ice Refill', player), player))

    set_rule(world.get_entrance('Mire Crystal Right Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Mire Crystal Right', player), player))
    set_rule(world.get_entrance('Mire Crystal Mid Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Mire Crystal Mid', player), player))
    set_rule(world.get_entrance('Mire Firesnake Skip Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Mire Firesnake Skip', player), player))
    set_rule(world.get_entrance('Mire Antechamber Orange Barrier', player), lambda state: state.can_reach_orange(world.get_region('Mire Antechamber', player), player))
    set_rule(world.get_entrance('Mire Hub Upper Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub', player), player))
    set_rule(world.get_entrance('Mire Hub Lower Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub', player), player))
    set_rule(world.get_entrance('Mire Hub Right Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub Right', player), player))
    set_rule(world.get_entrance('Mire Hub Top Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub Top', player), player))
    set_rule(world.get_entrance('Mire Hub Switch Blue Barrier N', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub Switch', player), player))
    set_rule(world.get_entrance('Mire Hub Switch Blue Barrier S', player), lambda state: state.can_reach_blue(world.get_region('Mire Hub Switch', player), player))
    set_rule(world.get_entrance('Mire Map Spike Side Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Map Spike Side', player), player))
    set_rule(world.get_entrance('Mire Map Spot Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Map Spot', player), player))
    set_rule(world.get_entrance('Mire Crystal Dead End Left Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Crystal Dead End', player), player))
    set_rule(world.get_entrance('Mire Crystal Dead End Right Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Crystal Dead End', player), player))
    set_rule(world.get_entrance('Mire South Fish Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire South Fish', player), player))
    set_rule(world.get_entrance('Mire Compass Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Compass Room', player), player))
    set_rule(world.get_entrance('Mire Crystal Mid Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Crystal Mid', player), player))
    set_rule(world.get_entrance('Mire Crystal Left Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('Mire Crystal Left', player), player))

    set_rule(world.get_entrance('Mire Conveyor to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('Mire Tall Dark and Roomy to Ranged Crystal', player), lambda state: True) # Can always throw pots
    set_rule(world.get_entrance('Mire Fishbone Blue Barrier Bypass', player), lambda state: False) # (state.world.can_take_damage or state.has('Cape', player) or state.has('Cane of Byrna', player)) and state.can_tastate.can_use_bombs(player) // Easy to do but obscure. Should it be in logic?

    set_rule(world.get_location('Turtle Rock - Chain Chomps', player), lambda state: state.can_reach('TR Chain Chomps Top', 'Region', player) and state.can_hit_crystal_through_barrier(player))
    set_rule(world.get_entrance('TR Chain Chomps Top to Bottom Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Chain Chomps Top', player), player))
    set_rule(world.get_entrance('TR Chain Chomps Bottom to Top Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Chain Chomps Bottom', player), player))
    set_rule(world.get_entrance('TR Pokey 2 Top to Bottom Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Pokey 2 Top', player), player))
    set_rule(world.get_entrance('TR Pokey 2 Bottom to Top Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Pokey 2 Bottom', player), player))
    set_rule(world.get_entrance('TR Crystaroller Bottom to Middle Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Crystaroller Bottom', player), player))
    set_rule(world.get_entrance('TR Crystaroller Middle to Bottom Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Crystaroller Middle', player), player))
    set_rule(world.get_entrance('TR Crystaroller Middle to Chest Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystaroller Middle', player), player))
    set_rule(world.get_entrance('TR Crystaroller Middle to Top Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Crystaroller Middle', player), player))
    set_rule(world.get_entrance('TR Crystaroller Top to Middle Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('TR Crystaroller Top', player), player))
    set_rule(world.get_entrance('TR Crystaroller Chest to Middle Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystaroller Chest', player), player))
    set_rule(world.get_entrance('TR Crystal Maze Start to Interior Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystal Maze Start', player), player))
    set_rule(world.get_entrance('TR Crystal Maze Interior to End Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystal Maze Interior', player), player))
    set_rule(world.get_entrance('TR Crystal Maze Interior to Start Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystal Maze Interior', player), player))
    set_rule(world.get_entrance('TR Crystal Maze End to Interior Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('TR Crystal Maze End', player), player))

    set_rule(world.get_entrance('TR Chain Chomps Top to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('TR Pokey 2 Top to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('TR Crystaroller Top to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('TR Crystal Maze Start to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('TR Chain Chomps Bottom to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or (state.has('Hookshot', player) and state.can_reach_orange(world.get_region('TR Chain Chomps Bottom', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('TR Pokey 2 Bottom to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or (state.has('Hookshot', player) and state.can_reach_blue(world.get_region('TR Pokey 2 Bottom', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('TR Crystaroller Bottom to Ranged Crystal', player), lambda state: state.can_shoot_arrows(player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player) or (state.has('Hookshot', player) and state.can_reach_orange(world.get_region('TR Crystaroller Bottom', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('TR Crystaroller Middle to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or (state.has('Hookshot', player) and state.can_reach_orange(world.get_region('TR Crystaroller Middle', player), player))) # or state.has_beam_sword(player)
    set_rule(world.get_entrance('TR Crystaroller Middle to Bottom Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Blue Boomerang', player))
    set_rule(world.get_entrance('TR Crystal Maze End to Ranged Crystal', player), lambda state: state.has('Cane of Somaria', player)) # or state.has('Blue Boomerang', player) or state.has('Red Boomerang', player) // These work by clipping the rang through the two stone blocks, which works sometimes.
    set_rule(world.get_entrance('TR Crystal Maze Interior to End Bypass', player), lambda state: state.can_use_bombs(player) or state.can_shoot_arrows(player) or state.has('Red Boomerang', player) or state.has('Blue Boomerang', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player) or state.has('Cane of Somaria', player)) # Beam sword does NOT work
    set_rule(world.get_entrance('TR Crystal Maze Interior to Start Bypass', player), lambda state: True) # Can always grab a pot from the interior and walk it to the start region and throw it there

    set_rule(world.get_entrance('GT Hookshot Platform Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('GT Hookshot South Platform', player), player))
    set_rule(world.get_entrance('GT Hookshot Entry Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('GT Hookshot South Entry', player), player))
    set_rule(world.get_entrance('GT Double Switch Entry to Pot Corners Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Double Switch Entry', player), player))
    set_rule(world.get_entrance('GT Double Switch Entry to Left Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Double Switch Entry', player), player))
    set_rule(world.get_entrance('GT Double Switch Left to Entry Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Double Switch Left', player), player))
    set_rule(world.get_entrance('GT Double Switch Pot Corners to Entry Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Double Switch Pot Corners', player), player))
    set_rule(world.get_entrance('GT Double Switch Pot Corners to Exit Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('GT Double Switch Pot Corners', player), player))
    set_rule(world.get_entrance('GT Double Switch Exit to Blue Barrier', player), lambda state: state.can_reach_blue(world.get_region('GT Double Switch Exit', player), player))
    set_rule(world.get_entrance('GT Spike Crystal Left to Right Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Spike Crystal Left', player), player))
    set_rule(world.get_entrance('GT Spike Crystal Right to Left Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Spike Crystal Right', player), player))
    set_rule(world.get_entrance('GT Crystal Conveyor to Corner Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('GT Crystal Conveyor', player), player))
    set_rule(world.get_entrance('GT Crystal Conveyor Corner to Barrier - Blue', player), lambda state: state.can_reach_blue(world.get_region('GT Crystal Conveyor Corner', player), player))
    set_rule(world.get_entrance('GT Crystal Conveyor Corner to Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Crystal Conveyor Corner', player), player))
    set_rule(world.get_entrance('GT Crystal Conveyor Left to Corner Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Crystal Conveyor Left', player), player))
    set_rule(world.get_entrance('GT Crystal Circles Barrier - Orange', player), lambda state: state.can_reach_orange(world.get_region('GT Crystal Circles', player), player))

    set_rule(world.get_entrance('GT Hookshot Platform Barrier Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Blue Boomerang', player) or state.has('Red Boomerang', player) or state.has('Cane of Somaria', player))  # or state.has_Boots(player) /// There is a super precise trick where you can throw a pot and climp into the blue barrier, then sprint out of them.
    set_rule(world.get_entrance('GT Hookshot South Entry to Ranged Crystal', player), lambda state: state.can_use_bombs(player) or state.has('Blue Boomerang', player) or state.has('Red Boomerang', player))  # or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('GT Double Switch Left to Crystal', player), lambda state: state.can_hit_crystal(player))
    set_rule(world.get_entrance('GT Double Switch Entry to Ranged Switches', player), lambda state: False) # state.has('Cane of Somaria', player)
    set_rule(world.get_entrance('GT Double Switch Left to Entry Bypass', player), lambda state: True) # Can always use pots
    set_rule(world.get_entrance('GT Double Switch Left to Pot Corners Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player) or state.has('Red Boomerang', player)) # or (state.has('Blue Boomerang', player) and state.has('Hookshot', player)) or (state.has('Ice Rod', player) and state.has('Hookshot', player)) or state.has('Hookshot', player) /// You can do this with just a pot and a hookshot
    set_rule(world.get_entrance('GT Double Switch Left to Exit Bypass', player), lambda state: False) # state.can_use_bombs(player) or (state.has('Cane of Somaria', player) and (state.has('Red Boomerang', player) or (state.has('Hookshot', player) and state.has('Blue Boomerang', player)) or (state.has('Hookshot', player) and state.has('Ice Rod', player))))
    set_rule(world.get_entrance('GT Double Switch Pot Corners to Ranged Switches', player), lambda state: False) # state.can_use_bombs(player) or state.has('Cane of Somaria', player) or (state.has('Cane of Somaria', player) and state.has_Boots(player)) /// There's two ways to interact with the switch. Somaria bounce at the top corner, or timed throws at the bottom corner.
    set_rule(world.get_entrance('GT Spike Crystal Left to Right Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player) or state.has('Red Boomerang', player) or state.has('Blue Boomerang', player) or state.has('Fire Rod', player) or state.has('Ice Rod', player))  # or state.can_use_beam_sword(player)
    set_rule(world.get_entrance('GT Crystal Conveyor to Ranged Crystal', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('GT Crystal Conveyor Corner to Ranged Crystal', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('GT Crystal Conveyor Corner to Left Bypass', player), lambda state: state.can_use_bombs(player) or state.has('Cane of Somaria', player))
    set_rule(world.get_entrance('GT Crystal Circles to Ranged Crystal', player), lambda state: state.can_hit_crystal_through_barrier(player) or state.has_blunt_weapon(player) or state.has('Cane of Byrna', player)) # or state.has_beam_sword(player)

    add_key_logic_rules(world, player)
    # End of door rando rules.

    if world.restrict_boss_items[player] != 'none':
        def add_mc_rule(l):
            boss_location = world.get_location(l, player)
            d_name = boss_location.parent_region.dungeon.name
            compass_name = f'Compass ({d_name})'
            map_name = f'Map ({d_name})'
            add_rule(boss_location, lambda state: state.has(compass_name, player) and state.has(map_name, player))

        for dungeon, info in dungeon_table.items():
            if info.prize:
                d_name = "Thieves' Town" if dungeon.startswith('Thieves') else dungeon
                for loc in [info.prize, f'{d_name} - Boss']:
                    add_mc_rule(loc)
        if world.doorShuffle[player] == 'crossed':
            add_mc_rule('Agahnim 1')
        add_mc_rule('Agahnim 2')

    set_rule(world.get_location('Ganon', player), lambda state: state.has_beam_sword(player) and state.has_fire_source(player) and state.has_crystals(world.crystals_needed_for_ganon[player], player)
                                                                and (state.has('Tempered Sword', player) or state.has('Golden Sword', player) or (state.has('Silver Arrows', player) and state.can_shoot_arrows(player)) or state.has('Lamp', player) or state.can_extend_magic(player, 12)))  # need to light torch a sufficient amount of times
    set_rule(world.get_entrance('Ganon Drop', player), lambda state: state.has_beam_sword(player))  # need to damage ganon to get tiles to drop


def bomb_rules(world, player):
    # todo: kak well, pod hint (bonkable pots), hookshot pot, spike cave pots
    bonkable_doors = ['Two Brothers House Exit (West)', 'Two Brothers House Exit (East)'] # Technically this is incorrectly defined, but functionally the same as what is intended.
    bombable_doors = ['Ice Rod Cave', 'Light World Bomb Hut', 'Light World Death Mountain Shop', 'Mini Moldorm Cave',
                      'Hookshot Cave Back to Middle', 'Hookshot Cave Front to Middle', 'Hookshot Cave Middle to Front',
                      'Hookshot Cave Middle to Back', 'Dark Lake Hylia Ledge Fairy', 'Hype Cave', 'Brewery',
                      'Paradox Cave Chest Area NE', 'Blinds Hideout N', 'Kakariko Well (top to back)',
                      'Light Hype Fairy']
    for entrance in bonkable_doors:
        add_rule(world.get_entrance(entrance, player), lambda state: state.can_use_bombs(player) or state.has_Boots(player))
        add_bunny_rule(world.get_entrance(entrance, player), player)
    for entrance in bombable_doors:
        add_rule(world.get_entrance(entrance, player), lambda state: state.can_use_bombs(player))
        add_bunny_rule(world.get_entrance(entrance, player), player)

    bonkable_items = ['Sahasrahla\'s Hut - Left', 'Sahasrahla\'s Hut - Middle', 'Sahasrahla\'s Hut - Right']
    bombable_items = ['Chicken House', 'Aginah\'s Cave', 'Graveyard Cave',
                      'Hype Cave - Top', 'Hype Cave - Middle Right', 'Hype Cave - Middle Left', 'Hype Cave - Bottom']
    for location in bonkable_items:
        add_rule(world.get_location(location, player), lambda state: state.can_use_bombs(player) or state.has_Boots(player)) 
        add_bunny_rule(world.get_location(location, player), player)
    for location in bombable_items:
        add_rule(world.get_location(location, player), lambda state: state.can_use_bombs(player)) 
        add_bunny_rule(world.get_location(location, player), player)

    cave_kill_locations = ['Mini Moldorm Cave - Far Left', 'Mini Moldorm Cave - Far Right', 'Mini Moldorm Cave - Left', 'Mini Moldorm Cave - Right', 'Mini Moldorm Cave - Generous Guy', 'Spiral Cave']
    for location in cave_kill_locations:
        add_rule(world.get_location(location, player), lambda state: state.can_kill_most_things(player) or state.can_use_bombs(player))
        add_bunny_rule(world.get_location(location, player), player)
    add_rule(world.get_entrance('Spiral Cave (top to bottom)', player), lambda state: state.can_kill_most_things(player) or state.can_use_bombs(player))
    add_bunny_rule(world.get_entrance('Spiral Cave (top to bottom)', player), player)

    paradox_switch_chests = ['Paradox Cave Lower - Far Left', 'Paradox Cave Lower - Left', 'Paradox Cave Lower - Right', 'Paradox Cave Lower - Far Right', 'Paradox Cave Lower - Middle']
    for location in paradox_switch_chests:
        add_rule(world.get_location(location, player), lambda state: state.can_hit_crystal_through_barrier(player))
        add_bunny_rule(world.get_location(location, player), player)
    
    # Dungeon bomb logic
    easy_kill_rooms = [ # Door, bool-bombable
        ('Hyrule Dungeon Armory S', True), # One green guard
        ('Hyrule Dungeon Armory ES', True), # One green guard
        ('Hyrule Dungeon Armory Boomerang WS', True), # One blue guard
        ('Desert Compass NW', True), # Three popos
        ('Desert Four Statues NW', True), # Four popos
        ('Desert Four Statues ES', True), # Four popos
        ('Hera Beetles WS', False), # Three blue beetles and only two pots, and bombs don't work.
        ('Thieves Basement Block WN', True), # One blue and one red zazak and one Stalfos. Two pots. Need to kill the third enemy somehow.
        ('Ice Pengator Trap NE', False), # Five pengators. Bomb-doable?
        ('TR Twin Pokeys EN', False), # Two pokeys
        ('TR Twin Pokeys SW', False), # Two pokeys
        ('GT Petting Zoo SE', False), # Dont make anyone do this room with bombs and/or pots.
        ('GT DMs Room SW', False) # Four red stalfos
    ]
    for killdoor,bombable in easy_kill_rooms:
        if bombable:
            add_rule(world.get_entrance(killdoor, player), lambda state: (state.can_use_bombs(player) or state.can_kill_most_things(player)))
        else:
            add_rule(world.get_entrance(killdoor, player), lambda state: state.can_kill_most_things(player))
    add_rule(world.get_entrance('Ice Stalfos Hint SE', player), lambda state: state.can_use_bombs(player)) # Need bombs for big stalfos knights
    add_rule(world.get_entrance('Mire Cross ES', player), lambda state: state.can_kill_most_things(player)) # 4 Sluggulas. Bombs don't work // or (state.can_use_bombs(player) and state.has('Magic Powder'), player) 

    enemy_kill_drops = [ # Location, bool-bombable
        ('Hyrule Castle - Map Guard Key Drop', True),
        ('Hyrule Castle - Boomerang Guard Key Drop', True),
        ('Hyrule Castle - Key Rat Key Drop', True),
#        ('Hyrule Castle - Big Key Drop', True), # Pots are available
#        ('Eastern Palace - Dark Eyegore Key Drop', True), # Pots are available
        ('Castle Tower - Dark Archer Key Drop', True),
#        ('Castle Tower - Circle of Pots Key Drop', True), # Pots are available 
#        ('Skull Woods - Spike Corner Key Drop', True), # Pots are available
        ('Ice Palace - Jelly Key Drop', True),
        ('Ice Palace - Conveyor Key Drop', True),
        ('Misery Mire - Conveyor Crystal Key Drop', True),
        ('Turtle Rock - Pokey 1 Key Drop', True),
        ('Turtle Rock - Pokey 2 Key Drop', True),
#        ('Ganons Tower - Mini Helmasaur Key Drop', True) # Pots are available
        ('Castle Tower - Room 03', True), # Two spring soliders
        ('Ice Palace - Compass Chest', True) # Pengators
    ]
    for location,bombable in enemy_kill_drops:
        if bombable:
            add_rule(world.get_location(location, player), lambda state: state.can_use_bombs(player) or state.can_kill_most_things(player)) 
        else:
            add_rule(world.get_location(location, player), lambda state: state.can_kill_most_things(player))

    add_rule(world.get_location('Attic Cracked Floor', player), lambda state: state.can_use_bombs(player)) 
    bombable_floors = ['PoD Pit Room Bomb Hole', 'Ice Bomb Drop Hole', 'Ice Freezors Bomb Hole', 'GT Bob\'s Room Hole']
    for entrance in bombable_floors:
        add_rule(world.get_entrance(entrance, player), lambda state: state.can_use_bombs(player)) 

    if world.doorShuffle[player] == 'vanilla':
        add_rule(world.get_entrance('TR Lazy Eyes SE', player), lambda state: state.can_use_bombs(player)) # ToDo: Add always true for inverted, cross-entrance, and door-variants and so on.
        add_rule(world.get_entrance('Turtle Rock Ledge Exit (West)', player), lambda state: state.can_use_bombs(player)) # Is this the same as above?
        
        dungeon_bonkable = ['Sewers Rat Path WS', 'Sewers Rat Path WN',
                            'PoD Warp Hint SE', 'PoD Jelly Hall NW', 'PoD Jelly Hall NE', 'PoD Mimics 1 SW',
                            'Thieves Ambush E', 'Thieves Rail Ledge W',
                            'TR Dash Room NW', 'TR Crystaroller SW', 'TR Dash Room ES',
                            'GT Four Torches NW','GT Fairy Abyss SW'
                            ]
        dungeon_bombable = ['PoD Map Balcony WS', 'PoD Arena Ledge ES', 'PoD Dark Maze E', 'PoD Big Chest Balcony W',
                            'Swamp Pot Row WN','Swamp Map Ledge EN', 'Swamp Hammer Switch WN', 'Swamp Hub Dead Ledge EN', 'Swamp Waterway N', 'Swamp I S',
                            'Skull Pot Circle WN', 'Skull Pull Switch EN', 'Skull Big Key EN', 'Skull Lone Pot WN',
                            'Thieves Rail Ledge NW', 'Thieves Pot Alcove Bottom SW',
                            'Ice Bomb Drop Hole', 'Ice Freezors Bomb Hole',
                            'Mire Crystal Mid NW', 'Mire Tall Dark and Roomy WN', 'Mire Shooter Rupees EN', 'Mire Crystal Top SW',
                            'GT Warp Maze (Rails) WS', 'GT Bob\'s Room Hole', 'GT Randomizer Room ES', 'GT Bomb Conveyor SW', 'GT Crystal Circles NW', 'GT Cannonball Bridge SE', 'GT Refill NE'
                            ]
        for entrance in dungeon_bonkable:
            add_rule(world.get_entrance(entrance, player), lambda state: state.can_use_bombs(player) or state.has_Boots(player)) 
        for entrance in dungeon_bombable:
            add_rule(world.get_entrance(entrance, player), lambda state: state.can_use_bombs(player)) 
    else:
        doors_to_bomb_check = [x for x in world.doors if x.player == player and x.type in [DoorType.Normal, DoorType.Interior]]
        for door in doors_to_bomb_check:
            if door.kind(world) in [DoorKind.Dashable]:
                add_rule(door.entrance, lambda state: state.can_use_bombs(player) or state.has_Boots(player))
            elif door.kind(world) in [DoorKind.Bombable]:
                add_rule(door.entrance, lambda state: state.can_use_bombs(player))


def pot_rules(world, player):
    if world.pottery[player] != 'none':
        blocks = [l for l in world.get_locations() if l.type == LocationType.Pot and l.pot.flags & PotFlags.Block]
        for block_pot in blocks:
            add_rule(block_pot, lambda state: state.can_lift_rocks(player))
        for l in world.get_region('Hookshot Fairy', player).locations:
            if l.type == LocationType.Pot:
                add_rule(l, lambda state: state.has('Hookshot', player))
        for l in world.get_region('Spike Cave', player).locations:
            if l.type == LocationType.Pot:
                add_rule(l, lambda state: state.has('Hammer', player) and state.can_lift_rocks(player) and
                         ((state.has('Cape', player) and state.can_extend_magic(player, 16, True)) or
                         (state.has('Cane of Byrna', player) and
                          (state.can_extend_magic(player, 12, True) or
                          (state.world.can_take_damage and (state.has_Boots(player) or state.has_hearts(player, 4)))))))
        for l in world.get_region('Dark Desert Hint', player).locations:
            if l.type == LocationType.Pot:
                add_rule(l, lambda state: state.can_use_bombs(player))
        for l in world.get_region('Palace of Darkness Hint', player).locations:
            if l.type == LocationType.Pot:
                add_rule(l, lambda state: state.can_use_bombs(player) or state.has_Boots(player))
        for number in ['1', '2']:
            loc = world.get_location_unsafe(f'Dark Lake Hylia Ledge Spike Cave Pot #{number}', player)
            if loc and loc.type == LocationType.Pot:
                add_rule(loc, lambda state: state.world.can_take_damage or state.has('Hookshot', player)
                         or state.has('Cape', player)
                         or (state.has('Cane of Byrna', player)
                             and state.world.difficulty_adjustments[player] == 'normal'))
        for l in world.get_region('Ice Hammer Block', player).locations:
            if l.type == LocationType.Pot:
                add_rule(l, lambda state: state.has('Hammer', player) and state.can_lift_rocks(player))
        for pot in ['Ice Antechamber Pot #3', 'Ice Antechamber Pot #4']:
            loc = world.get_location_unsafe(pot, player)
            if loc:
                set_rule(loc, lambda state: state.has('Hammer', player) and state.can_lift_rocks(player))
        loc = world.get_location_unsafe('Mire Spikes Pot #3', player)
        if loc:
            set_rule(loc, lambda state: (state.world.can_take_damage and state.has_hearts(player, 4))
                     or state.has('Cane of Byrna', player) or state.has('Cape', player))
        for l in world.get_region('Ice Refill', player).locations:
            if l.type == LocationType.Pot:
                # or can_reach_blue is redundant as you have to hit a crystal switch somewhere...
                add_rule(l, lambda state: state.can_hit_crystal(player))



def default_rules(world, player):
    set_rule(world.get_entrance('Other World S&Q', player), lambda state: state.has_Mirror(player) and state.has('Beat Agahnim 1', player))

    # Underworld Logic
    set_rule(world.get_entrance('Old Man Cave Exit (West)', player), lambda state: False)  # drop cannot be climbed up
    set_rule(world.get_entrance('Paradox Cave Push Block Reverse', player), lambda state: state.has_Mirror(player))  # can erase block, overwritten in noglitches
    set_rule(world.get_entrance('Bumper Cave Exit (Top)', player), lambda state: state.has('Cape', player))
    set_rule(world.get_entrance('Bumper Cave Exit (Bottom)', player), lambda state: state.has('Cape', player) or state.has('Hookshot', player))
    set_rule(world.get_entrance('Superbunny Cave Exit (Bottom)', player), lambda state: False)  # Cannot get to bottom exit from top. Just exists for shuffling
    
    # Item Access
    set_rule(world.get_location('Zora\'s Ledge', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_location('Potion Shop', player), lambda state: state.has('Mushroom', player))
    set_rule(world.get_location('Flute Spot', player), lambda state: state.has('Shovel', player))
    set_rule(world.get_location('Ether Tablet', player), lambda state: state.has('Book of Mudora', player) and state.has_beam_sword(player))
    set_rule(world.get_location('Bombos Tablet', player), lambda state: state.has('Book of Mudora', player) and state.has_beam_sword(player))
    
    # Entrance Access
    set_rule(world.get_entrance('Lumberjack Tree Tree', player), lambda state: state.has_Boots(player) and state.has('Beat Agahnim 1', player))
    set_rule(world.get_entrance('Bonk Rock Cave', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('Sanctuary Grave', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Kings Grave', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('Bonk Fairy (Light)', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('Checkerboard Cave', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('50 Rupee Cave', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('20 Rupee Cave', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Skull Woods Final Section', player), lambda state: state.has('Fire Rod', player))
    set_rule(world.get_entrance('Hookshot Cave', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Turtle Rock', player), lambda state: state.has_sword(player) and state.has_turtle_rock_medallion(player) and state.can_reach('Turtle Rock Ledge', 'Region', player))  # sword required to cast magic (!)
    set_rule(world.get_entrance('Dark World Hammer Peg Cave', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Bonk Fairy (Dark)', player), lambda state: state.has_Boots(player))
    set_rule(world.get_entrance('Misery Mire', player), lambda state: state.has_sword(player) and state.has_misery_mire_medallion(player))  # sword required to cast magic (!)
    set_rule(world.get_entrance('Dark Lake Hylia Ledge Spike Cave', player), lambda state: state.can_lift_rocks(player))

    # Region Access    
    set_rule(world.get_entrance('DM Hammer Bridge (West)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('DM Hammer Bridge (East)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('DM Broken Bridge (West)', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('DM Broken Bridge (East)', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Fairy Ascension Rocks (North)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Fairy Ascension Rocks (South)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('TR Pegs Ledge Entry', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('TR Pegs Ledge Leave', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Mountain Entry Entrance Rock (West)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Mountain Entry Entrance Rock (East)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Lost Woods Pass Hammer (North)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Lost Woods Pass Hammer (South)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Lost Woods Pass Rock (North)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Lost Woods Pass Rock (South)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Kings Grave Outer Rocks', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Kings Grave Inner Rocks', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Potion Shop Rock (South)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Potion Shop Rock (North)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Zora Approach Rocks (West)', player), lambda state: state.can_lift_heavy_rocks(player) or state.has_Boots(player))
    set_rule(world.get_entrance('Zora Approach Rocks (East)', player), lambda state: state.can_lift_heavy_rocks(player) or state.has_Boots(player))
    set_rule(world.get_entrance('Hyrule Castle Main Gate (South)', player), lambda state: state.has_Mirror(player))
    set_rule(world.get_entrance('Hyrule Castle Main Gate (North)', player), lambda state: state.has_Mirror(player))
    set_rule(world.get_entrance('Hyrule Castle Inner East Rock', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Hyrule Castle Outer East Rock', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Bat Cave Ledge Peg', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Bat Cave Ledge Peg (East)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Desert Palace Statue Move', player), lambda state: state.has('Book of Mudora', player))
    set_rule(world.get_entrance('Desert Ledge Outer Rocks', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Desert Ledge Inner Rocks', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('C Whirlpool Rock (Bottom)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('C Whirlpool Rock (Top)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Desert Pass Rocks (North)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Desert Pass Rocks (South)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Skull Woods Bush Rock (West)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Skull Woods Bush Rock (East)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Bumper Cave Entrance Rock', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Skull Woods Pass Rock (North)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Skull Woods Pass Rock (South)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Dark Witch Rock (North)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Dark Witch Rock (South)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Catfish Approach Rocks (West)', player), lambda state: state.can_lift_heavy_rocks(player) or state.has_Boots(player))
    set_rule(world.get_entrance('Catfish Approach Rocks (East)', player), lambda state: state.can_lift_heavy_rocks(player) or state.has_Boots(player))
    set_rule(world.get_entrance('Village of Outcasts Pegs', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Grassy Lawn Pegs', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Broken Bridge Hammer Rock (South)', player), lambda state: state.can_lift_rocks(player) or state.has('Hammer', player))
    set_rule(world.get_entrance('Broken Bridge Hammer Rock (North)', player), lambda state: state.can_lift_rocks(player) or state.has('Hammer', player))
    set_rule(world.get_entrance('Broken Bridge Hookshot Gap', player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Peg Area Rocks (West)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Peg Area Rocks (East)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Dig Game To Ledge Drop', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Frog Rock (Inner)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Frog Rock (Outer)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Archery Game Rock (North)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Archery Game Rock (South)', player), lambda state: state.can_lift_heavy_rocks(player))
    set_rule(world.get_entrance('Hammer Bridge Pegs (North)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Hammer Bridge Pegs (South)', player), lambda state: state.has('Hammer', player))
    set_rule(world.get_entrance('Dark C Whirlpool Rock (Bottom)', player), lambda state: state.can_lift_rocks(player))
    set_rule(world.get_entrance('Dark C Whirlpool Rock (Top)', player), lambda state: state.can_lift_rocks(player))
    
    set_rule(world.get_entrance('Zora Waterfall Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Zora Waterfall Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Zora Waterfall Water Approach', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Kakariko Pond Whirlpool', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('River Bend Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('River Bend East Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Potion Shop Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Potion Shop Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Zora Approach Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Wooden Bridge Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Wooden Bridge Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('C Whirlpool Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Statues Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia South Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia Central Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia Island Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Lake Hylia Water D Leave', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Cave SW', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Octoballoon Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Octoballoon Waterfall Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Qirn Jump Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Qirn Jump East Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Dark Witch Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Dark Witch Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Catfish Approach Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Broken Bridge Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Broken Bridge Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Broken Bridge West Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Hammer Bridge Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Dark C Whirlpool Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Hype Cave Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Lake Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Lake Northeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Lake Southwest Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Lake Southeast Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Ice Lake Moat Water Entry', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Shopping Mall SW', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Bomber Corner Water Drop', player), lambda state: state.has('Flippers', player))
    set_rule(world.get_entrance('Bomber Corner Waterfall Water Drop', player), lambda state: state.has('Flippers', player))
    
    if world.swords[player] == 'swordless':
        swordless_rules(world, player)


def ow_rules(world, player):
    if world.is_atgt_swapped(player):
        set_rule(world.get_entrance('Agahnims Tower', player), lambda state: state.has_crystals(world.crystals_needed_for_gt[player], player))
    else:
        set_rule(world.get_entrance('Agahnims Tower', player), lambda state: state.has('Cape', player) or state.has_beam_sword(player) or state.has('Beat Agahnim 1', player))  # barrier gets removed after killing agahnim, relevant for entrance shuffle
        set_rule(world.get_entrance('GT Entry Approach', player), lambda state: state.has_crystals(world.crystals_needed_for_gt[player], player))
        set_rule(world.get_entrance('GT Entry Leave', player), lambda state: state.has_crystals(world.crystals_needed_for_gt[player], player) or state.world.shuffle[player] in ('restricted', 'full', 'lite', 'lean', 'crossed', 'insanity'))

    if not world.is_tile_swapped(0x00, player):
        set_rule(world.get_entrance('Lost Woods East Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Pedestal Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Southwest Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods East (Forgotten) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods West (Forgotten) Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Skull Woods Back Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Forgotten (West) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Forgotten (East) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Portal Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Forgotten (Middle) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Front Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x02, player):
        set_rule(world.get_entrance('Lumberjack Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Lumberjack Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x03, player):
        set_rule(world.get_entrance('West Death Mountain (Top) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Spectacle Rock Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('West Dark Death Mountain (Top) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bubble Boy Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('West Dark Death Mountain (Bottom) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Spectacle Rock Approach', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'] and state.has_Pearl(player))
        set_rule(world.get_entrance('Spectacle Rock Leave', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'] and state.has_Pearl(player))
        
    if not world.is_tile_swapped(0x05, player):
        set_rule(world.get_entrance('East Death Mountain (Top West) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Death Mountain (Top East) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Mimic Cave Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Spiral Cave Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Fairy Ascension Mirror Spot', player), lambda state: state.has_Mirror(player) and state.has_Pearl(player))  # need to lift flowers
        set_rule(world.get_entrance('Isolated Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Death Mountain Bridge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Floating Island Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Death Mountain Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
    else:
        set_rule(world.get_entrance('East Dark Death Mountain (Top West) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Dark Death Mountain (Top East) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('TR Ledge (West) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('TR Ledge (East) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('TR Isolated Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Dark Death Mountain (Bottom Plateau) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Dark Death Mountain (Bottom Left) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Dark Death Mountain (Bottom) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Floating Island Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Death Mountain Teleporter (East)', player), lambda state: state.can_lift_heavy_rocks(player))
        
    if not world.is_tile_swapped(0x07, player):
        set_rule(world.get_entrance('TR Pegs Area Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('TR Pegs Teleporter', player), lambda state: state.has('Hammer', player))
    else:
        set_rule(world.get_entrance('Turtle Rock Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Turtle Rock Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Turtle Rock Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
        set_rule(world.get_entrance('TR Pegs Ledge Drop', player), lambda state: False)
        set_rule(world.get_entrance('TR Pegs Ledge Leave', player), lambda state: state.has('Hammer', player) and state.can_lift_heavy_rocks(player) and state.has_Pearl(player))
        set_rule(world.get_entrance('Turtle Rock Tail Ledge Drop', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        
    if not world.is_tile_swapped(0x0a, player):
        set_rule(world.get_entrance('Mountain Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Mountain Entry Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Mountain Entry Entrance Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Bumper Cave Area Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bumper Cave Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bumper Cave Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x0f, player):
        set_rule(world.get_entrance('Zora Waterfall Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Catfish Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x10, player):
        set_rule(world.get_entrance('Lost Woods Pass West Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Pass East Top Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Pass Portal Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lost Woods Pass East Bottom Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Kakariko Teleporter', player), lambda state: state.can_lift_rocks(player))
    else:
        set_rule(world.get_entrance('Skull Woods Pass West Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Pass East Top Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Pass Portal Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Skull Woods Pass East Bottom Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('West Dark World Teleporter', player), lambda state: state.can_lift_rocks(player))
        
    if not world.is_tile_swapped(0x11, player):
        set_rule(world.get_entrance('Kakariko Fortune Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Outcast Fortune Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x12, player):
        set_rule(world.get_entrance('Kakariko Pond Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Outcast Pond Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x13, player):
        set_rule(world.get_entrance('Sanctuary Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bonk Rock Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Chapel Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Chapel Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x14, player):
        set_rule(world.get_entrance('Graveyard Ledge Mirror Spot', player), lambda state: state.has_Pearl(player) and state.has_Mirror(player))
        set_rule(world.get_entrance('Kings Grave Mirror Spot', player), lambda state: state.has_Pearl(player) and state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Graveyard Ladder (Top)', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'] and state.has_Pearl(player))
        set_rule(world.get_entrance('Graveyard Ladder (Bottom)', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'] and state.has_Pearl(player))
        set_rule(world.get_entrance('Dark Graveyard Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Graveyard Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Graveyard Grave Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x15, player):
        set_rule(world.get_entrance('River Bend Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('River Bend East Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Qirn Jump Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Qirn Jump East Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x16, player):
        set_rule(world.get_entrance('Potion Shop Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Potion Shop Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Witch Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Witch Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x17, player):
        set_rule(world.get_entrance('Zora Approach Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Zora Approach Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Catfish Approach Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Catfish Approach Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x18, player):
        set_rule(world.get_entrance('Kakariko Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Kakariko Grass Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Village of Outcasts Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Village of Outcasts Southwest Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Hammer House Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x1a, player):
        set_rule(world.get_entrance('Forgotton Forest Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Forgotton Forest Fence Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Shield Shop Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x1b, player):
        set_rule(world.get_entrance('Inverted Pyramid Hole', player), lambda state: False)
        set_rule(world.get_entrance('Inverted Pyramid Entrance', player), lambda state: False)
        set_rule(world.get_entrance('Pyramid Hole', player), lambda state: world.open_pyramid[player] or state.has('Beat Agahnim 2', player))
        
        set_rule(world.get_entrance('HC Area Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('HC Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('HC Courtyard Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('HC East Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('HC Courtyard Left Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('HC Area South Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Top of Pyramid', player), lambda state: state.has('Beat Agahnim 1', player))
        set_rule(world.get_entrance('Top of Pyramid (Inner)', player), lambda state: state.has('Beat Agahnim 1', player))
    else:
        set_rule(world.get_entrance('Inverted Pyramid Hole', player), lambda state: world.is_pyramid_open(player) or state.has('Beat Agahnim 2', player))
        set_rule(world.get_entrance('Pyramid Hole', player), lambda state: False)
        set_rule(world.get_entrance('Pyramid Entrance', player), lambda state: False)
        
        set_rule(world.get_entrance('Pyramid Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Pyramid Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Pyramid Courtyard Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Pyramid Uncle Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Pyramid From Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Pyramid Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Post Aga Inverted Teleporter', player), lambda state: state.has('Beat Agahnim 1', player))
        
    if not world.is_tile_swapped(0x1d, player):
        set_rule(world.get_entrance('Wooden Bridge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Wooden Bridge Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Wooden Bridge West Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Broken Bridge West Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Broken Bridge East Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Broken Bridge Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x1e, player):
        set_rule(world.get_entrance('Eastern Palace Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Palace of Darkness Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x22, player):
        set_rule(world.get_entrance('Blacksmith Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Blacksmith Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bat Cave Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Hammer Pegs Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Hammer Pegs Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x25, player):
        set_rule(world.get_entrance('Sand Dunes Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Dunes Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x28, player):
        set_rule(world.get_entrance('Maze Race Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Maze Race Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dig Game Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dig Game Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x29, player):
        set_rule(world.get_entrance('Kakariko Suburb Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Kakariko Suburb South Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Frog Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Frog Prison Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Archery Game Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x2a, player):
        set_rule(world.get_entrance('Flute Boy Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Flute Boy Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Stumpy Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Stumpy Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x2b, player):
        set_rule(world.get_entrance('Central Bonk Rocks Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Bonk Rocks Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x2c, player):
        set_rule(world.get_entrance('Links House Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Big Bomb Shop Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x2d, player):
        set_rule(world.get_entrance('Stone Bridge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Stone Bridge South Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Hobo Mirror Spot', player), lambda state: state.has_Mirror(player) and state.has_Pearl(player) and state.has('Flippers', player))
    else:
        set_rule(world.get_entrance('Hammer Bridge North Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Hammer Bridge South Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark Hobo Mirror Spot', player), lambda state: state.has_Mirror(player) and state.has_Pearl(player) and state.has('Flippers', player))
        
    if not world.is_tile_swapped(0x2e, player):
        set_rule(world.get_entrance('Tree Line Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark Tree Line Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x2f, player):
        set_rule(world.get_entrance('Eastern Nook Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Hyrule Teleporter', player), lambda state: state.has('Hammer', player) and state.can_lift_rocks(player) and state.has_Pearl(player)) # bunny cannot use hammer
    else:
        set_rule(world.get_entrance('Darkness Nook Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('East Dark World Teleporter', player), lambda state: state.has('Hammer', player) and state.can_lift_rocks(player) and state.has_Pearl(player))
        
    if not world.is_tile_swapped(0x30, player):
        set_rule(world.get_entrance('Checkerboard Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Desert Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Desert Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('DP Stairs Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('DP Entrance (North) Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Bombos Tablet Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Desert Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
    else:
        set_rule(world.get_entrance('Misery Mire Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Misery Mire Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Misery Mire Blocked Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Misery Mire Main Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Misery Mire Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
        set_rule(world.get_entrance('Checkerboard Ledge Approach', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        set_rule(world.get_entrance('Checkerboard Ledge Leave', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        
    if not world.is_tile_swapped(0x32, player):
        set_rule(world.get_entrance('Cave 45 Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Flute Boy Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Stumpy Approach Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Stumpy Bush Entry Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Cave 45 Inverted Approach', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        set_rule(world.get_entrance('Cave 45 Inverted Leave', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        
    if not world.is_tile_swapped(0x33, player):
        set_rule(world.get_entrance('C Whirlpool Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('C Whirlpool Outer Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('South Hyrule Teleporter', player), lambda state: state.has('Hammer', player) and state.can_lift_rocks(player) and state.has_Pearl(player)) # bunny cannot use hammer
        set_rule(world.get_entrance('South Teleporter Cliff Ledge Drop', player), lambda state: state.can_lift_rocks(player) and state.has_Pearl(player)) # OWG only, can bomb clip out
    else:
        set_rule(world.get_entrance('Dark C Whirlpool Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Dark C Whirlpool Outer Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('South Dark World Teleporter', player), lambda state: state.has('Hammer', player) and state.can_lift_rocks(player) and state.has_Pearl(player))
        set_rule(world.get_entrance('South Teleporter Cliff Ledge Drop', player), lambda state: state.can_lift_rocks(player) and state.has_Pearl(player))
        
    if not world.is_tile_swapped(0x34, player):
        set_rule(world.get_entrance('Statues Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Hype Cave Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x35, player):
        set_rule(world.get_entrance('Lake Hylia Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lake Hylia Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lake Hylia Island Mirror Spot', player), lambda state: state.has_Mirror(player) and state.has_Pearl(player) and state.has('Flippers', player))
        set_rule(world.get_entrance('Lake Hylia Central Island Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lake Hylia Water Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lake Hylia Water D Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('South Shore Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('South Shore East Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Lake Hylia Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
    else:
        set_rule(world.get_entrance('Ice Lake Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Ice Lake Southwest Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Ice Lake Southeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Ice Lake Northeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Ice Palace Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Ice Palace Teleporter', player), lambda state: state.can_lift_heavy_rocks(player))
        set_rule(world.get_entrance('Lake Hylia Island Pier', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        
    if not world.is_tile_swapped(0x37, player):
        set_rule(world.get_entrance('Ice Cave Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Shopping Mall Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x3a, player):
        set_rule(world.get_entrance('Desert Pass Ledge Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Desert Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Swamp Nook Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Swamp Nook Southeast Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Swamp Nook Pegs Mirror Spot', player), lambda state: state.has_Mirror(player))
        set_rule(world.get_entrance('Desert Pass Ladder (South)', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        set_rule(world.get_entrance('Desert Pass Ladder (North)', player), lambda state: world.logic[player] in ['noglitches', 'minorglitches'])
        
    if not world.is_tile_swapped(0x3b, player):
        set_rule(world.get_entrance('Dam Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Swamp Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x3c, player):
        set_rule(world.get_entrance('South Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Dark South Pass Mirror Spot', player), lambda state: state.has_Mirror(player))
        
    if not world.is_tile_swapped(0x3f, player):
        set_rule(world.get_entrance('Octoballoon Mirror Spot', player), lambda state: state.has_Mirror(player))
    else:
        set_rule(world.get_entrance('Bomber Corner Mirror Spot', player), lambda state: state.has_Mirror(player))


def ow_bunny_rules(world, player):
    add_bunny_rule(world.get_location('Mushroom', player), player)
    add_bunny_rule(world.get_location('Zora\'s Ledge', player), player)
    add_bunny_rule(world.get_location('Maze Race', player), player)
    add_bunny_rule(world.get_location('Flute Spot', player), player)
    add_bunny_rule(world.get_location('Catfish', player), player)

    add_bunny_rule(world.get_entrance('Lost Woods Hideout Drop', player), player)
    add_bunny_rule(world.get_entrance('Lumberjack Tree Tree', player), player)
    add_bunny_rule(world.get_entrance('Waterfall of Wishing', player), player)
    add_bunny_rule(world.get_entrance('Bonk Rock Cave', player), player)
    add_bunny_rule(world.get_entrance('Sanctuary Grave', player), player)
    add_bunny_rule(world.get_entrance('Kings Grave', player), player)
    add_bunny_rule(world.get_entrance('North Fairy Cave Drop', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Secret Entrance Drop', player), player)
    add_bunny_rule(world.get_entrance('Bonk Fairy (Light)', player), player)
    add_bunny_rule(world.get_entrance('Checkerboard Cave', player), player)
    add_bunny_rule(world.get_entrance('50 Rupee Cave', player), player)
    add_bunny_rule(world.get_entrance('20 Rupee Cave', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods First Section Hole (North)', player), player) # bunny cannot lift bush
    add_bunny_rule(world.get_entrance('Skull Woods Second Section Hole', player), player) # bunny cannot lift bush
    add_bunny_rule(world.get_entrance('Skull Woods Final Section', player), player) # bunny cannot use fire rod
    add_bunny_rule(world.get_entrance('Hookshot Cave', player), player)
    add_bunny_rule(world.get_entrance('Turtle Rock', player), player)
    add_bunny_rule(world.get_entrance('Thieves Town', player), player) # bunny cannot pull
    add_bunny_rule(world.get_entrance('Brewery', player), player) # bomb required
    add_bunny_rule(world.get_entrance('Palace of Darkness', player), player) # kiki needs pearl
    add_bunny_rule(world.get_entrance('Dark World Hammer Peg Cave', player), player)
    add_bunny_rule(world.get_entrance('Bonk Fairy (Dark)', player), player)
    add_bunny_rule(world.get_entrance('Misery Mire', player), player)
    add_bunny_rule(world.get_entrance('Hype Cave', player), player) # bomb required
    add_bunny_rule(world.get_entrance('Dark Lake Hylia Ledge Fairy', player), player) # bomb required
    add_bunny_rule(world.get_entrance('Dark Lake Hylia Ledge Spike Cave', player), player)
    
    add_bunny_rule(world.get_entrance('Lost Woods Bush (West)', player), player)
    add_bunny_rule(world.get_entrance('Lost Woods Bush (East)', player), player)
    add_bunny_rule(world.get_entrance('DM Hammer Bridge (West)', player), player)
    add_bunny_rule(world.get_entrance('DM Hammer Bridge (East)', player), player)
    add_bunny_rule(world.get_entrance('Fairy Ascension Rocks (North)', player), player)
    add_bunny_rule(world.get_entrance('Fairy Ascension Rocks (South)', player), player)
    add_bunny_rule(world.get_entrance('DM Broken Bridge (West)', player), player)
    add_bunny_rule(world.get_entrance('DM Broken Bridge (East)', player), player)
    add_bunny_rule(world.get_entrance('TR Pegs Ledge Entry', player), player)
    add_bunny_rule(world.get_entrance('Mountain Entry Entrance Rock (West)', player), player)
    add_bunny_rule(world.get_entrance('Mountain Entry Entrance Rock (East)', player), player)
    add_bunny_rule(world.get_entrance('Lost Woods Pass Hammer (North)', player), player)
    add_bunny_rule(world.get_entrance('Lost Woods Pass Hammer (South)', player), player)
    add_bunny_rule(world.get_entrance('Lost Woods Pass Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Lost Woods Pass Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Kings Grave Outer Rocks', player), player)
    add_bunny_rule(world.get_entrance('Kings Grave Inner Rocks', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Zora Approach Rocks (West)', player), player)
    add_bunny_rule(world.get_entrance('Zora Approach Rocks (East)', player), player)
    add_bunny_rule(world.get_entrance('Kakariko Southwest Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Kakariko Southwest Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Kakariko Yard Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Kakariko Yard Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Southwest Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Southwest Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Courtyard Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Courtyard Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Inner East Rock', player), player)
    add_bunny_rule(world.get_entrance('Hyrule Castle Outer East Rock', player), player)
    add_bunny_rule(world.get_entrance('Wooden Bridge Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Wooden Bridge Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Bat Cave Ledge Peg', player), player)
    add_bunny_rule(world.get_entrance('Bat Cave Ledge Peg (East)', player), player)
    add_bunny_rule(world.get_entrance('Desert Ledge Outer Rocks', player), player)
    add_bunny_rule(world.get_entrance('Desert Ledge Inner Rocks', player), player)
    add_bunny_rule(world.get_entrance('Flute Boy Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Flute Boy Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('C Whirlpool Rock (Bottom)', player), player)
    add_bunny_rule(world.get_entrance('C Whirlpool Rock (Top)', player), player)
    add_bunny_rule(world.get_entrance('Desert Pass Rocks (North)', player), player)
    add_bunny_rule(world.get_entrance('Desert Pass Rocks (South)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Bush Rock (West)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Bush Rock (East)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Forgotten Bush (West)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Forgotten Bush (East)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Second Section Hole', player), player)
    add_bunny_rule(world.get_entrance('Bumper Cave Entrance Rock', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Bush Row (West)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Bush Row (East)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Skull Woods Pass Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Dark Graveyard Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Dark Graveyard Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Catfish Approach Rocks (West)', player), player)
    add_bunny_rule(world.get_entrance('Catfish Approach Rocks (East)', player), player)
    add_bunny_rule(world.get_entrance('Village of Outcasts Pegs', player), player)
    add_bunny_rule(world.get_entrance('Grassy Lawn Pegs', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge Hammer Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge Hammer Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge Hookshot Gap', player), player)
    add_bunny_rule(world.get_entrance('Peg Area Rocks (West)', player), player)
    add_bunny_rule(world.get_entrance('Peg Area Rocks (East)', player), player)
    add_bunny_rule(world.get_entrance('Dig Game To Ledge Drop', player), player)
    add_bunny_rule(world.get_entrance('Frog Rock (Inner)', player), player)
    add_bunny_rule(world.get_entrance('Frog Rock (Outer)', player), player)
    add_bunny_rule(world.get_entrance('Archery Game Rock (North)', player), player)
    add_bunny_rule(world.get_entrance('Archery Game Rock (South)', player), player)
    add_bunny_rule(world.get_entrance('Hammer Bridge Pegs (North)', player), player)
    add_bunny_rule(world.get_entrance('Hammer Bridge Pegs (South)', player), player)
    add_bunny_rule(world.get_entrance('Stumpy Approach Bush (North)', player), player)
    add_bunny_rule(world.get_entrance('Stumpy Approach Bush (South)', player), player)
    add_bunny_rule(world.get_entrance('Dark C Whirlpool Rock (Bottom)', player), player)
    add_bunny_rule(world.get_entrance('Dark C Whirlpool Rock (Top)', player), player)

    add_bunny_rule(world.get_entrance('Zora Waterfall Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Zora Waterfall Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Zora Waterfall Water Approach', player), player)
    add_bunny_rule(world.get_entrance('Kakariko Pond Whirlpool', player), player)
    add_bunny_rule(world.get_entrance('River Bend Water Drop', player), player)
    add_bunny_rule(world.get_entrance('River Bend East Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Zora Approach Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Wooden Bridge Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Wooden Bridge Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('C Whirlpool Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Statues Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia South Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia Central Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia Island Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Ice Cave SW', player), player)
    add_bunny_rule(world.get_entrance('Octoballoon Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Octoballoon Waterfall Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Qirn Jump Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Qirn Jump East Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Catfish Approach Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Broken Bridge West Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Hammer Bridge Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark C Whirlpool Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Hype Cave Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Southwest Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Southeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Moat Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Shopping Mall SW', player), player)
    add_bunny_rule(world.get_entrance('Bomber Corner Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Bomber Corner Waterfall Water Drop', player), player)


def no_glitches_rules(world, player):
    # todo: move some dungeon rules to no glictes logic - see these for examples
    # add_rule(world.get_entrance('Ganons Tower (Hookshot Room)', player), lambda state: state.has('Hookshot', player) or state.has_Boots(player))
    # add_rule(world.get_entrance('Ganons Tower (Double Switch Room)', player), lambda state: state.has('Hookshot', player))
    # DMs_room_chests = ['Ganons Tower - DMs Room - Top Left', 'Ganons Tower - DMs Room - Top Right', 'Ganons Tower - DMs Room - Bottom Left', 'Ganons Tower - DMs Room - Bottom Right']
    # for location in DMs_room_chests:
    #     add_rule(world.get_location(location, player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Paradox Cave Push Block Reverse', player), lambda state: False)  # no glitches does not require block override
    forbid_bomb_jump_requirements(world, player)
    if world.get_region('Big Bomb Shop', player).entrances: # just some location that is placed late in the ER algorithm, prevent underworld rules from applying when trying to search reachability in the overworld
        add_conditional_lamps(world, player)


def fake_flipper_rules(world, player):
    set_rule(world.get_entrance('Zora Waterfall Water Approach', player), lambda state: True) # warning, assumes FF possible on other end of whirlpool or local ancilla splash delete
    set_rule(world.get_entrance('River Bend Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('River Bend East Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Potion Shop Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Potion Shop Northeast Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Zora Approach Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('C Whirlpool Water Entry', player), lambda state: True)
    set_rule(world.get_entrance('Statues Water Entry', player), lambda state: True)
    set_rule(world.get_entrance('Lake Hylia South Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Octoballoon Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Qirn Jump Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Qirn Jump East Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Dark Witch Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Dark Witch Northeast Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Catfish Approach Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Dark C Whirlpool Water Entry', player), lambda state: True)
    set_rule(world.get_entrance('Hype Cave Water Entry', player), lambda state: True)
    set_rule(world.get_entrance('Ice Lake Southeast Water Drop', player), lambda state: True)
    set_rule(world.get_entrance('Bomber Corner Water Drop', player), lambda state: True)
    add_bunny_rule(world.get_entrance('Zora Waterfall Water Approach', player), player)
    add_bunny_rule(world.get_entrance('River Bend Water Drop', player), player)
    add_bunny_rule(world.get_entrance('River Bend East Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Potion Shop Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Zora Approach Water Drop', player), player)
    add_bunny_rule(world.get_entrance('C Whirlpool Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Statues Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Lake Hylia South Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Octoballoon Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Qirn Jump Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Qirn Jump East Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark Witch Northeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Catfish Approach Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Dark C Whirlpool Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Hype Cave Water Entry', player), player)
    add_bunny_rule(world.get_entrance('Ice Lake Southeast Water Drop', player), player)
    add_bunny_rule(world.get_entrance('Bomber Corner Water Drop', player), player)


def forbid_bomb_jump_requirements(world, player):
    DMs_room_chests = ['Ganons Tower - DMs Room - Top Left', 'Ganons Tower - DMs Room - Top Right', 'Ganons Tower - DMs Room - Bottom Left', 'Ganons Tower - DMs Room - Bottom Right']
    for location in DMs_room_chests:
        add_rule(world.get_location(location, player), lambda state: state.has('Hookshot', player))
    set_rule(world.get_entrance('Paradox Cave Bomb Jump', player), lambda state: False)

# Light cones in standard depend on which world we actually are in, not which one the location would normally be
# We add Lamp requirements only to those locations which lie in the dark world (or everything if open
DW_Entrances = ['Bumper Cave (Bottom)', 'Superbunny Cave (Top)', 'Superbunny Cave (Bottom)', 'Hookshot Cave', 'Bumper Cave (Top)', 'Hookshot Cave Back Entrance', 'Dark Death Mountain Ledge (East)',
                'Turtle Rock Isolated Ledge Entrance', 'Thieves Town', 'Skull Woods Final Section', 'Ice Palace', 'Misery Mire', 'Palace of Darkness', 'Swamp Palace', 'Turtle Rock', 'Dark Death Mountain Ledge (West)']

def check_is_dark_world(region):
    for entrance in region.entrances:
        if entrance.name in DW_Entrances:
            return True
    return False

def add_conditional_lamps(world, player):
    def add_conditional_lamp(spot, region, spottype='Location'):
        if spottype == 'Location':
            spot = world.get_location(spot, player)
        else:
            spot = world.get_entrance(spot, player)
        if (not world.dark_world_light_cone and check_is_dark_world(world.get_region(region, player))) or (not world.light_world_light_cone and not check_is_dark_world(world.get_region(region, player))):
            add_lamp_requirement(spot, player)

    dark_rooms = {
        'TR Dark Ride': {'sewer': False, 'entrances': ['TR Dark Ride Up Stairs', 'TR Dark Ride SW', 'TR Dark Ride Path'], 'locations': []},
        'TR Dark Ride Ledges': {'sewer': False, 'entrances': ['TR Dark Ride Ledges Path'], 'locations': []},
        'Mire Dark Shooters': {'sewer': False, 'entrances': ['Mire Dark Shooters Up Stairs', 'Mire Dark Shooters SW', 'Mire Dark Shooters SE'], 'locations': []},
        'Mire Key Rupees': {'sewer': False, 'entrances': ['Mire Key Rupees NE'], 'locations': []},
        'Mire Block X': {'sewer': False, 'entrances': ['Mire Block X NW', 'Mire Block X WS'], 'locations': []},
        'Mire Tall Dark and Roomy': {'sewer': False, 'entrances': ['Mire Tall Dark and Roomy ES', 'Mire Tall Dark and Roomy WS', 'Mire Tall Dark and Roomy WN', 'Mire Tall Dark and Roomy to Ranged Crystal'], 'locations': []},
        'Mire Crystal Right': {'sewer': False, 'entrances': ['Mire Crystal Right ES'], 'locations': []},
        'Mire Crystal Mid': {'sewer': False, 'entrances': ['Mire Crystal Mid NW'], 'locations': []},
        'Mire Crystal Left': {'sewer': False, 'entrances': ['Mire Crystal Left WS'], 'locations': []},
        'Mire Crystal Top': {'sewer': False, 'entrances': ['Mire Crystal Top SW'], 'locations': []},
        'Mire Shooter Rupees': {'sewer': False, 'entrances': ['Mire Shooter Rupees EN'], 'locations': []},
        'PoD Dark Alley': {'sewer': False, 'entrances': ['PoD Dark Alley NE'], 'locations': []},
        'PoD Callback': {'sewer': False, 'entrances': ['PoD Callback WS', 'PoD Callback Warp'], 'locations': []},
        'PoD Turtle Party': {'sewer': False, 'entrances': ['PoD Turtle Party ES', 'PoD Turtle Party NW'], 'locations': []},
        'PoD Lonely Turtle': {'sewer': False, 'entrances': ['PoD Lonely Turtle SW', 'PoD Lonely Turtle EN'], 'locations': []},
        'PoD Dark Pegs Landing': {'sewer': False, 'entrances': ['PoD Dark Pegs Up Ladder', 'PoD Dark Pegs Landing to Right', 'PoD Dark Pegs Landing to Ranged Crystal'], 'locations': []},
        'PoD Dark Pegs Left': {'sewer': False, 'entrances': ['PoD Dark Pegs WN', 'PoD Dark Pegs Left to Middle Barrier - Blue', 'PoD Dark Pegs Left to Ranged Crystal'], 'locations': []},
        'PoD Dark Basement': {'sewer': False, 'entrances': ['PoD Dark Basement W Up Stairs', 'PoD Dark Basement E Up Stairs'], 'locations': ['Palace of Darkness - Dark Basement - Left', 'Palace of Darkness - Dark Basement - Right']},
        'PoD Dark Maze': {'sewer': False, 'entrances': ['PoD Dark Maze EN', 'PoD Dark Maze E'], 'locations': ['Palace of Darkness - Dark Maze - Top', 'Palace of Darkness - Dark Maze - Bottom']},
        'Eastern Dark Square': {'sewer': False, 'entrances': ['Eastern Dark Square NW', 'Eastern Dark Square Key Door WN', 'Eastern Dark Square EN'], 'locations': []},
        'Eastern Dark Pots': {'sewer': False, 'entrances': ['Eastern Dark Pots WN'], 'locations': ['Eastern Palace - Dark Square Pot Key']},
        'Eastern Darkness': {'sewer': False, 'entrances': ['Eastern Darkness S', 'Eastern Darkness Up Stairs', 'Eastern Darkness NE'], 'locations': ['Eastern Palace - Dark Eyegore Key Drop']},
        'Eastern Rupees': {'sewer': False, 'entrances': ['Eastern Rupees SE'], 'locations': []},
        'Tower Lone Statue': {'sewer': False, 'entrances': ['Tower Lone Statue Down Stairs', 'Tower Lone Statue WN'], 'locations': []},
        'Tower Dark Maze': {'sewer': False, 'entrances': ['Tower Dark Maze EN', 'Tower Dark Maze ES'], 'locations': ['Castle Tower - Dark Maze']},
        'Tower Dark Chargers': {'sewer': False, 'entrances': ['Tower Dark Chargers WS', 'Tower Dark Chargers Up Stairs'], 'locations': []},
        'Tower Dual Statues': {'sewer': False, 'entrances': ['Tower Dual Statues Down Stairs', 'Tower Dual Statues WS'], 'locations': []},
        'Tower Dark Pits': {'sewer': False, 'entrances': ['Tower Dark Pits ES', 'Tower Dark Pits EN'], 'locations': []},
        'Tower Dark Archers': {'sewer': False, 'entrances': ['Tower Dark Archers WN', 'Tower Dark Archers Up Stairs'], 'locations': ['Castle Tower - Dark Archer Key Drop']},
        'Sewers Dark Cross': {'sewer': True, 'entrances': ['Sewers Dark Cross Key Door N', 'Sewers Dark Cross South Stairs'], 'locations': ['Sewers - Dark Cross']},
        'Sewers Behind Tapestry': {'sewer': True, 'entrances': ['Sewers Behind Tapestry S', 'Sewers Behind Tapestry Down Stairs'], 'locations': []},
        'Sewers Rope Room': {'sewer': True, 'entrances': ['Sewers Rope Room Up Stairs', 'Sewers Rope Room North Stairs'], 'locations': []},
        'Sewers Water': {'sewer': True, 'entrances': ['Sewers Water S', 'Sewers Water W'], 'locations': []},
        'Sewers Key Rat': {'sewer': True, 'entrances': ['Sewers Key Rat E', 'Sewers Key Rat Key Door N'], 'locations': ['Hyrule Castle - Key Rat Key Drop']},
        'Old Man Cave': {'sewer': False, 'entrances': ['Old Man Cave Exit (East)']},
        'Old Man House Back': {'sewer': False, 'entrances': ['Old Man House Back to Front', 'Old Man House Exit (Top)']},
        'Death Mountain Return Cave (left)': {'sewer': False, 'entrances': ['Death Mountain Return Cave E', 'Death Mountain Return Cave Exit (West)']},
        'Death Mountain Return Cave (right)': {'sewer': False, 'entrances': ['Death Mountain Return Cave Exit (East)', 'Death Mountain Return Cave W']},
    }

    dark_debug_set = set()
    for region, info in dark_rooms.items():
        is_dark = False
        if not world.sewer_light_cone[player]:
            is_dark = True
        elif world.doorShuffle[player] != 'crossed' and not info['sewer']:
            is_dark = True
        elif world.doorShuffle[player] == 'crossed':
            sewer_builder = world.dungeon_layouts[player]['Hyrule Castle']
            is_dark = region not in sewer_builder.master_sector.region_set()
        if is_dark:
            dark_debug_set.add(region)
            for ent in info['entrances']:
                add_conditional_lamp(ent, region, 'Entrance')
            r = world.get_region(region, player)
            for loc in r.locations:
                add_conditional_lamp(loc, region, 'Location')
    logging.getLogger('').debug('Non Dark Regions: ' + ', '.join(set(dark_rooms.keys()).difference(dark_debug_set)))

    add_conditional_lamp('Old Man House Front to Back', 'Old Man House', 'Entrance')

def open_rules(world, player):
    # softlock protection as you can reach the sewers small key door with a guard drop key
    set_rule(world.get_location('Hyrule Castle - Boomerang Chest', player), lambda state: state.has_sm_key('Small Key (Escape)', player))
    set_rule(world.get_location('Hyrule Castle - Zelda\'s Chest', player), lambda state: state.has_sm_key('Small Key (Escape)', player))


def swordless_rules(world, player):
    set_rule(world.get_entrance('Tower Altar NW', player), lambda state: True)
    set_rule(world.get_entrance('Skull Vines NW', player), lambda state: True)
    set_rule(world.get_entrance('Ice Lobby WS', player), lambda state: state.has('Fire Rod', player) or state.has('Bombos', player))
    set_rule(world.get_location('Ice Palace - Freezor Chest', player), lambda state: state.has('Fire Rod', player) or state.has('Bombos', player))

    set_rule(world.get_location('Ether Tablet', player), lambda state: state.has('Book of Mudora', player) and state.has('Hammer', player))
    set_rule(world.get_location('Bombos Tablet', player), lambda state: state.has('Book of Mudora', player) and state.has('Hammer', player))
    set_rule(world.get_location('Ganon', player), lambda state: state.has('Hammer', player) and state.has_fire_source(player) and state.has('Silver Arrows', player) and state.can_shoot_arrows(player) and state.has_crystals(world.crystals_needed_for_ganon[player], player))
    set_rule(world.get_entrance('Ganon Drop', player), lambda state: state.has('Hammer', player))  # need to damage ganon to get tiles to drop
    
    if not world.is_atgt_swapped(player):
        set_rule(world.get_entrance('Agahnims Tower', player), lambda state: state.has('Cape', player) or state.has('Hammer', player) or state.has('Beat Agahnim 1', player))  # barrier gets removed after killing agahnim, relevant for entrance shuffle

    set_rule(world.get_entrance('Misery Mire', player), lambda state: state.has_misery_mire_medallion(player))   # sword not required to use medallion for opening in swordless (!)
    set_rule(world.get_entrance('Turtle Rock', player), lambda state: state.has_turtle_rock_medallion(player) and state.can_reach('Turtle Rock Ledge', 'Region', player))   # sword not required to use medallion for opening in swordless (!)
    add_bunny_rule(world.get_entrance('Misery Mire', player), player)
    add_bunny_rule(world.get_entrance('Turtle Rock', player), player)

std_kill_rooms = {
    'Hyrule Dungeon Armory Main': ['Hyrule Dungeon Armory S', 'Hyrule Dungeon Armory ES'], # One green guard
    'Hyrule Dungeon Armory Boomerang': ['Hyrule Dungeon Armory Boomerang WS'], # One blue guard
    'Eastern Stalfos Spawn': ['Eastern Stalfos Spawn ES', 'Eastern Stalfos Spawn NW'], # Can use pots
    'Desert Compass Room': ['Desert Compass NW'], # Three popos
    'Desert Four Statues': ['Desert Four Statues NW', 'Desert Four Statues ES'], # Four popos
    'Hera Beetles': ['Hera Beetles WS'], # Three blue beetles and only two pots, and bombs don't work.
    'Tower Gold Knights': ['Tower Gold Knights SW', 'Tower Gold Knights EN'], # Two ball and chain 
    'Tower Dark Archers': ['Tower Dark Archers WN'],  # Not a kill room
    'Tower Red Spears': ['Tower Red Spears WN'],  # Two spear soldiers 
    'Tower Red Guards': ['Tower Red Guards EN', 'Tower Red Guards SW'], # Two usain bolts
    'Tower Circle of Pots': ['Tower Circle of Pots NW'], # Two spear soldiers. Plenty of pots.
    'PoD Turtle Party': ['PoD Turtle Party ES', 'PoD Turtle Party NW'],  # Lots of turtles.
    'Thieves Basement Block': ['Thieves Basement Block WN'], # One blue and one red zazak and one Stalfos. Two pots. Need weapon. 
    'Ice Stalfos Hint': ['Ice Stalfos Hint SE'], # Need bombs for big stalfos knights
    'Ice Pengator Trap': ['Ice Pengator Trap NE'], # Five pengators. Bomb-doable?
    'Mire 2': ['Mire 2 NE'], # Wizzrobes. Bombs dont work.
    'Mire Cross': ['Mire Cross ES'], # 4 Sluggulas. Bombs don't work
    'TR Twin Pokeys': ['TR Twin Pokeys EN', 'TR Twin Pokeys SW'], # Two pokeys
    'GT Petting Zoo': ['GT Petting Zoo SE'], # Dont make anyone do this room with bombs.
    'GT DMs Room': ['GT DMs Room SW'], # Four red stalfos
    'GT Gauntlet 1': ['GT Gauntlet 1 WN'], # Stalfos/zazaks
    'GT Gauntlet 2': ['GT Gauntlet 2 EN', 'GT Gauntlet 2 SW'], # Red stalfos
    'GT Gauntlet 3': ['GT Gauntlet 3 NW', 'GT Gauntlet 3 SW'], # Blue zazaks
    'GT Gauntlet 4': ['GT Gauntlet 4 NW', 'GT Gauntlet 4 SW'], # Red zazaks
    'GT Gauntlet 5': ['GT Gauntlet 5 NW', 'GT Gauntlet 5 WS'], # Stalfos and zazak
    'GT Wizzrobes 1': ['GT Wizzrobes 1 SW'], # Wizzrobes. Bombs don't work
    'GT Wizzrobes 2': ['GT Wizzrobes 2 SE', 'GT Wizzrobes 2 NE'] # Wizzrobes. Bombs don't work
}  # all trap rooms?

def add_connection(parent_name, target_name, entrance_name, world, player):
    parent = world.get_region(parent_name, player)
    target = world.get_region(target_name, player)
    connection = Entrance(player, entrance_name, parent)
    parent.exits.append(connection)
    connection.connect(target)


def standard_rules(world, player):
    add_connection('Menu', 'Hyrule Castle Secret Entrance', 'Uncle S&Q', world, player)
    world.get_entrance('Uncle S&Q', player).hide_path = True
    set_rule(world.get_entrance('Links House S&Q', player), lambda state: state.has('Zelda Delivered', player))
    set_rule(world.get_entrance('Sanctuary S&Q', player), lambda state: state.has('Zelda Delivered', player))
    # these are because of rails
    if world.shuffle[player] != 'vanilla':
        # where ever these happen to be
        for portal_name in ['Hyrule Castle East', 'Hyrule Castle West']:
            entrance = world.get_portal(portal_name, player).door.entrance
            set_rule(entrance, lambda state: state.has('Zelda Delivered', player))
    set_rule(world.get_entrance('Sanctuary Exit', player), lambda state: state.has('Zelda Delivered', player))
    set_rule(world.get_entrance('Hyrule Castle Ledge Drop', player), lambda state: state.has('Zelda Delivered', player))
    set_rule(world.get_entrance('Hyrule Castle Main Gate (North)', player), lambda state: state.has('Zelda Delivered', player))
    # zelda should be saved before agahnim is in play
    add_rule(world.get_location('Agahnim 1', player), lambda state: state.has('Zelda Delivered', player))

    # too restrictive for crossed?
    def uncle_item_rule(item):
        copy_state = CollectionState(world)
        copy_state.collect(item)
        copy_state.sweep_for_events()
        return copy_state.has('Zelda Delivered', player)

    def bomb_escape_rule():
        loc = world.get_location("Link's Uncle", player)
        return loc.item and loc.item.name in ['Bomb Upgrade (+10)' if world.bombbag[player] else 'Bombs (10)']

    def standard_escape_rule(state):
        return state.can_kill_most_things(player) or bomb_escape_rule() 

    add_item_rule(world.get_location('Link\'s Uncle', player), uncle_item_rule)

    # ensures the required weapon for escape lands on uncle (unless player has it pre-equipped)
    for location in ['Link\'s House', 'Sanctuary', 'Sewers - Secret Room - Left', 'Sewers - Secret Room - Middle',
                     'Sewers - Secret Room - Right']:
        add_rule(world.get_location(location, player), lambda state: standard_escape_rule(state))
    add_rule(world.get_location('Secret Passage', player), lambda state: standard_escape_rule(state))

    escape_builder = world.dungeon_layouts[player]['Hyrule Castle']
    for region in escape_builder.master_sector.regions:
        for loc in region.locations:
            add_rule(loc, lambda state: standard_escape_rule(state))
        if region.name in std_kill_rooms:
            for ent in std_kill_rooms[region.name]:
                add_rule(world.get_entrance(ent, player), lambda state: standard_escape_rule(state))

    set_rule(world.get_location('Zelda Pickup', player), lambda state: state.has('Big Key (Escape)', player))
    set_rule(world.get_entrance('Hyrule Castle Throne Room Tapestry', player), lambda state: state.has('Zelda Herself', player))
    set_rule(world.get_entrance('Hyrule Castle Tapestry Backwards', player), lambda state: state.has('Zelda Herself', player))

    def check_rule_list(state, r_list):
        return True if len(r_list) <= 0 else r_list[0](state) and check_rule_list(state, r_list[1:])
    rule_list, debug_path = find_rules_for_zelda_delivery(world, player)
    set_rule(world.get_location('Zelda Drop Off', player), lambda state: state.has('Zelda Herself', player) and check_rule_list(state, rule_list))

    add_rule(world.get_entrance('Links House SC', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Links House ES', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Central Bonk Rocks SW', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Hyrule Castle WN', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Hyrule Castle ES', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Hyrule Castle Main Gate (South)', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Hyrule Castle Main Gate (North)', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Hyrule Castle Ledge Drop', player), lambda state: state.has('Zelda Delivered', player))
    add_rule(world.get_entrance('Bonk Fairy (Light)', player), lambda state: state.has('Zelda Delivered', player))

    # don't allow bombs to get past here before zelda is rescued
    set_rule(world.get_entrance('GT Hookshot South Entry to Ranged Crystal', player), lambda state: (state.can_use_bombs(player) and state.has('Zelda Delivered', player)) or state.has('Blue Boomerang', player) or state.has('Red Boomerang', player))  # or state.has('Cane of Somaria', player))

def find_rules_for_zelda_delivery(world, player):
    # path rules for backtracking
    start_region = world.get_region('Hyrule Dungeon Cellblock', player)
    queue = deque([(start_region, [], [])])
    visited = {start_region}
    blank_state = CollectionState(world)
    while len(queue) > 0:
        region, path_rules, path = queue.popleft()
        for ext in region.exits:
            connect = ext.connected_region
            valid_region = connect and connect not in visited and\
                (connect.type == RegionType.Dungeon or connect.name == 'Hyrule Castle Ledge')
            if valid_region:
                rule = ext.access_rule
                rule_list = list(path_rules)
                next_path = list(path)
                if not rule(blank_state):
                    rule_list.append(rule)
                    next_path.append(ext.name)
                if connect.name == 'Sanctuary':
                    return rule_list, next_path
                else:
                    visited.add(connect)
                    queue.append((connect, rule_list, next_path))
    raise Exception('No path to Sanctuary found')


def set_bunny_rules(world, player, inverted):

    # regions for the exits of multi-entrace caves/drops that bunny cannot pass
    # Note spiral cave may be technically passible, but it would be too absurd to require since OHKO mode is a thing.
    bunny_impassable_caves = ['Bumper Cave', 'Two Brothers House', 'Hookshot Cave (Middle)',
                              'Pyramid', 'Spiral Cave (Top)', 'Fairy Ascension Cave (Drop)']
    bunny_accessible_locations = ['Link\'s Uncle', 'Sahasrahla', 'Sick Kid', 'Lost Woods Hideout', 'Lumberjack Tree',
                                  'Checkerboard Cave', 'Potion Shop', 'Spectacle Rock Cave', 'Pyramid',
                                  'Hype Cave - Generous Guy', 'Peg Cave', 'Bumper Cave Ledge',
                                  'Frog', 'Missing Smith', 'Dark Blacksmith Ruins', 'Purple Chest', 'Pyramid Crack', 'Big Bomb',
                                  'Spectacle Rock', 'Bombos Tablet', 'Ether Tablet', 'Blacksmith',
                                  'Master Sword Pedestal', 'Bottle Merchant', 'Sunken Treasure', 'Desert Ledge',
                                  'Kakariko Shop - Left', 'Kakariko Shop - Middle', 'Kakariko Shop - Right',
                                  'Lake Hylia Shop - Left', 'Lake Hylia Shop - Middle', 'Lake Hylia Shop - Right',
                                  'Potion Shop - Left', 'Potion Shop - Middle', 'Potion Shop - Right',
                                  'Capacity Upgrade - Left', 'Capacity Upgrade - Right',
                                  'Village of Outcasts Shop - Left', 'Village of Outcasts Shop - Middle', 'Village of Outcasts Shop - Right',
                                  'Dark Lake Hylia Shop - Left', 'Dark Lake Hylia Shop - Middle', 'Dark Lake Hylia Shop - Right',
                                  'Dark Death Mountain Shop - Left', 'Dark Death Mountain Shop - Middle', 'Dark Death Mountain Shop - Right',
                                  'Dark Lumberjack Shop - Left', 'Dark Lumberjack Shop - Middle', 'Dark Lumberjack Shop - Right',
                                  'Dark Potion Shop - Left', 'Dark Potion Shop - Middle', 'Dark Potion Shop - Right',
                                  'Red Shield Shop - Left', 'Red Shield Shop - Middle', 'Red Shield Shop - Right',
                                  'Old Man Sword Cave Item 1',
                                  'Take - Any  # 1 Item 1', 'Take - Any  # 1 Item 2',
                                  'Take - Any  # 2 Item 1', 'Take - Any  # 2 Item 2',
                                  'Take - Any  # 3 Item 1', 'Take - Any  # 3 Item 2',
                                  'Take - Any  # 4 Item 1', 'Take - Any  # 4 Item 2',
                                  ]

    def path_to_access_rule(path, entrance):
        return lambda state: state.can_reach(entrance) and all(rule_func(state) for rule_func in path)

    def options_to_access_rule(options):
        return lambda state: any(rule_func(state) for rule_func in options)

    # Helper functions to determine if the moon pearl is required
    def is_bunny(region):
        if inverted:
            return region.is_light_world
        else:
            return region.is_dark_world
    def is_link(region):
        if inverted:
            return region.is_dark_world
        else:
            return region.is_light_world

    def get_rule_to_add(region, location = None, connecting_entrance = None):
        # In OWG, a location can potentially be superbunny-mirror accessible or
        # bunny revival accessible.
        if world.logic[player] == 'owglitches':
            if region.type != RegionType.Dungeon \
                    and (location is None or location.name not in OverworldGlitchRules.get_superbunny_accessible_locations()) \
                    and not is_link(region):
                return lambda state: state.has_Pearl(player)
        else:
            if not is_link(region):
                return lambda state: state.has_Pearl(player)

        # in this case we are mixed region.
        # we collect possible options.

        # The base option is having the moon pearl
        possible_options = [lambda state: state.has_Pearl(player)]

        # We will search entrances recursively until we find
        # one that leads to an exclusively light world region
        # for each such entrance a new option is added that consist of:
        #    a) being able to reach it, and
        #    b) being able to access all entrances from there to `region`
        seen = {region}
        queue = deque([(region, [])])
        while queue:
            (current, path) = queue.popleft()
            for entrance in current.entrances:
                new_region = entrance.parent_region
                if new_region.type in (RegionType.Cave, RegionType.Dungeon) and new_region in seen:
                    continue
                new_path = path + [entrance.access_rule]
                seen.add(new_region)
                if not is_link(new_region):
                    if world.logic[player] == 'owglitches':
                        if region.type == RegionType.Dungeon and new_region.type != RegionType.Dungeon:
                            if entrance.name in OverworldGlitchRules.get_invalid_mirror_bunny_entrances():
                                continue
                            if entrance.name in drop_dungeon_entrances:
                                lobby = entrance.connected_region
                            else:
                                lobby = next(exit.connected_region for exit in current.exits if exit.connected_region.type == RegionType.Dungeon)
                            if lobby.name in bunny_revivable_entrances:
                                possible_options.append(path_to_access_rule(new_path, entrance))
                            elif lobby.name in superbunny_revivable_entrances:
                                possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player)], entrance))
                            elif lobby.name in superbunny_sword_revivable_entrances:
                                possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player) and state.has_sword(player)], entrance))
                            continue
                        elif region.type == RegionType.Cave and new_region.type != RegionType.Cave:
                            if entrance.name in OverworldGlitchRules.get_invalid_mirror_bunny_entrances():
                                continue
                            if region.name in OverworldGlitchRules.get_sword_required_superbunny_mirror_regions():
                                possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player) and state.has_sword(player)], entrance))
                            elif region.name in OverworldGlitchRules.get_boots_required_superbunny_mirror_regions():
                                possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player) and state.has_Boots(player)], entrance))
                            elif location and location.name in OverworldGlitchRules.get_superbunny_accessible_locations():
                                if location.name in OverworldGlitchRules.get_boots_required_superbunny_mirror_locations():
                                    possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player) and state.has_Boots(player)], entrance))
                                elif region.name == 'Kakariko Well (top)':
                                    possible_options.append(path_to_access_rule(new_path, entrance))
                                else:
                                    possible_options.append(path_to_access_rule(new_path + [lambda state: state.has_Mirror(player)], entrance))
                            continue
                        elif region.name == 'Superbunny Cave (Top)' and new_region.name == 'Superbunny Cave (Bottom)' and location and location.name in OverworldGlitchRules.get_superbunny_accessible_locations():
                            possible_options.append(path_to_access_rule(new_path, entrance))
                    else:
                        continue
                if is_bunny(new_region):
                    queue.append((new_region, new_path))
                else:
                    # we have reached pure light world, so we have a new possible option
                    possible_options.append(path_to_access_rule(new_path, entrance))
        return options_to_access_rule(possible_options)

    # Add requirements for bunny-impassible caves if they occur in the light world
    for region in [world.get_region(name, player) for name in bunny_impassable_caves]:

        if not is_bunny(region):
            continue
        rule = get_rule_to_add(region)
        for ext in region.exits:
            add_rule(ext, rule)

    paradox_shop = world.get_region('Light World Death Mountain Shop', player)
    if is_bunny(paradox_shop):
        add_rule(paradox_shop.entrances[0], get_rule_to_add(paradox_shop))

    for ent_name in bunny_impassible_doors:
        bunny_exit = world.get_entrance(ent_name, player)
        if bunny_exit.connected_region and is_bunny(bunny_exit.parent_region):
            add_rule(bunny_exit, get_rule_to_add(bunny_exit.parent_region))

    doors_to_check = [x for x in world.doors if x.player == player and x not in bunny_impassible_doors]
    doors_to_check = [x for x in doors_to_check if x.type in [DoorType.Normal, DoorType.Interior] and not x.blocked]
    for door in doors_to_check:
        room = world.get_room(door.roomIndex, player)
        if is_bunny(door.entrance.parent_region) and room.kind(door) in [DoorKind.Dashable, DoorKind.Bombable, DoorKind.Hidden]:
            add_rule(door.entrance, get_rule_to_add(door.entrance.parent_region))

    for region in world.get_regions():
        if region.player == player and is_bunny(region):
            for location in region.locations:
                if location.name in bunny_accessible_locations:
                    continue
                add_rule(location, get_rule_to_add(region, location))


drop_dungeon_entrances = {
    "Sewer Drop",
    "Skull Left Drop",
    "Skull Pinball",
    "Skull Pot Circle",
    "Skull Back Drop"
}


bunny_revivable_entrances = {
    "Sewers Pull Switch", "TR Dash Room", "Swamp Boss", "Hera Boss",
    "Tower Agahnim 1", "Ice Lobby", "Sewers Rat Path", "PoD Falling Bridge",
    "PoD Harmless Hellway", "PoD Mimics 2", "Ice Cross Bottom", "GT Agahnim 2",
    "Sewers Water", "TR Lazy Eyes", "TR Big Chest Entrance", "Swamp Push Statue",
    "PoD Arena Main", "PoD Arena Bridge", "PoD Map Balcony", "Sewers Dark Cross",
    "Desert Boss", "Swamp Hub", "Skull Spike Corner", "PoD Pit Room",
    "PoD Conveyor", "GT Crystal Circles", "Sewers Behind Tapestry",
    "Desert Tiles 2", "Skull Star Pits", "Hyrule Castle West Hall",
    "Hyrule Castle Throne Room", "Hyrule Castle East Hall", "Skull 2 West Lobby",
    "Skull 2 East Lobby", "Skull Pot Prison", "Skull 1 Lobby", "Skull Map Room",
    "Skull 3 Lobby", "PoD Boss", "GT Hidden Spikes", "GT Gauntlet 3",
    "Ice Spike Cross", "Hyrule Castle West Lobby", "Hyrule Castle Lobby",
    "Hyrule Castle East Lobby", "Desert Back Lobby", "Hyrule Dungeon Armory Main",
    "Hyrule Dungeon North Abyss", "Desert Sandworm Corner", "Desert Dead End",
    "Desert North Hall", "Desert Arrow Pot Corner", "GT DMs Room",
    "GT Petting Zoo", "Ice Tall Hint", "Desert West Lobby", "Desert Main Lobby",
    "Desert East Lobby", "GT Big Chest", "GT Bob\'s Room", "GT Speed Torch",
    "Mire Boss", "GT Conveyor Bridge", "Mire Lobby", "Eastern Darkness",
    "Ice Many Pots", "Mire South Fish", "Mire Right Bridge", "Mire Left Bridge",
    "TR Boss", "Eastern Hint Tile Blocked Path", "Thieves Spike Switch",
    "Thieves Boss", "Mire Spike Barrier", "Mire Cross", "Mire Hidden Shooters",
    "Mire Spikes", "TR Final Abyss Balcony", "TR Dark Ride", "TR Pokey 1", "TR Tile Room",
    "TR Roller Room", "Eastern Cannonball", "Thieves Hallway", "Ice Switch Room",
    "Mire Tile Room", "Mire Conveyor Crystal", "Mire Hub", "TR Dash Bridge",
    "TR Hub", "Eastern Boss", "Eastern Lobby", "Thieves Ambush",
    "Thieves BK Corner", "TR Eye Bridge", "Thieves Lobby", "Tower Lobby",
    "Sewer Drop", "Skull Left Drop", "Skull Pinball", "Skull Back Drop",
    "Skull Pot Circle",  # You automatically get superbunny by dropping
}

# Revive as superbunny or use superbunny to get the item in a dead end
superbunny_revivable_entrances = {
    "TR Main Lobby", "Sanctuary", "Thieves Pot Alcove Bottom"
}

superbunny_sword_revivable_entrances = {
    "Hera Lobby"
}

bunny_impassible_doors = {
    'Hyrule Dungeon Armory S', 'Hyrule Dungeon Armory ES', 'Sewers Pull Switch S',
    'Eastern Lobby N', 'Eastern Courtyard Ledge W', 'Eastern Courtyard Ledge E', 'Eastern Pot Switch SE',
    'Eastern Map Balcony Hook Path', 'Eastern Stalfos Spawn ES', 'Eastern Stalfos Spawn NW',
    'Eastern Darkness S', 'Eastern Darkness NE', 'Eastern Darkness Up Stairs',
    'Eastern Attic Start WS', 'Eastern Single Eyegore NE', 'Eastern Duo Eyegores NE', 'Desert Main Lobby Left Path',
    'Desert Main Lobby Right Path', 'Desert Left Alcove Path', 'Desert Right Alcove Path', 'Desert Compass NW',
    'Desert West Lobby NW', 'Desert Back Lobby NW', 'Desert Four Statues NW',  'Desert Four Statues ES',
    'Desert Beamos Hall WS', 'Desert Beamos Hall NE', 'Desert Wall Slide NW',
    'Hera Lobby to Front Barrier - Blue', 'Hera Front to Lobby Barrier - Blue', 'Hera Front to Down Stairs Barrier - Blue',
    'Hera Down Stairs to Front Barrier - Blue', 'Hera Tile Room EN', 'Hera Tridorm SE', 'Hera Beetles WS',
    'Hera 4F Down Stairs', 'Tower Gold Knights SW', 'Tower Dark Maze EN', 'Tower Dark Pits ES', 'Tower Dark Archers WN',
    'Tower Red Spears WN', 'Tower Red Guards EN', 'Tower Red Guards SW', 'Tower Circle of Pots NW', 'Tower Altar NW',
    'PoD Left Cage SW', 'PoD Middle Cage SE', 'PoD Pit Room Bomb Hole', 'PoD Stalfos Basement Warp',
    'PoD Arena Main to Landing Barrier - Blue', 'PoD Arena Landing to Right Barrier - Blue',
    'PoD Arena Right to Landing Barrier - Blue', 'PoD Arena Main to Landing Barrier - Blue',
    'PoD Arena Landing Bonk Path', 'PoD Sexy Statue NW', 'PoD Map Balcony Drop Down',
    'PoD Mimics 1 NW', 'PoD Falling Bridge Path N', 'PoD Falling Bridge Path S',
    'PoD Mimics 2 NW', 'PoD Bow Statue Down Ladder', 'PoD Dark Pegs Landing to Right',
    'PoD Dark Pegs Left to Middle Barrier - Blue', 'PoD Dark Pegs Left to Ranged Crystal', 
    'PoD Turtle Party ES', 'PoD Turtle Party NW', 'PoD Callback Warp', 'Swamp Lobby Moat', 'Swamp Entrance Moat',
    'Swamp Trench 1 Approach Swim Depart', 'Swamp Trench 1 Approach Key', 'Swamp Trench 1 Key Approach',
    'Swamp Trench 1 Key Ledge Depart', 'Swamp Trench 1 Departure Approach', 'Swamp Trench 1 Departure Key',
    'Swamp Hub Hook Path', 'Swamp Shortcut Blue Barrier', 'Swamp Trench 2 Pots Blue Barrier',
    'Swamp Trench 2 Pots Wet', 'Swamp Trench 2 Departure Wet', 'Swamp West Ledge Hook Path', 'Swamp Barrier Ledge Hook Path',
    'Swamp Attic Left Pit', 'Swamp Attic Right Pit', 'Swamp Push Statue NW', 'Swamp Push Statue NE',
    'Swamp Drain Right Switch', 'Swamp Waterway NE', 'Swamp Waterway N', 'Swamp Waterway NW', 
    'Skull Pot Circle WN', 'Skull Pot Circle Star Path', 'Skull Pull Switch S', 'Skull Big Chest N',
    'Skull Big Chest Hookpath', 'Skull 2 East Lobby NW', 'Skull Back Drop Star Path', 'Skull 2 West Lobby NW',
    'Skull 3 Lobby EN', 'Skull Star Pits SW', 'Skull Star Pits ES', 'Skull Torch Room WN', 'Skull Vines NW',
    'Thieves Conveyor Maze EN', 'Thieves Triple Bypass EN', 'Thieves Triple Bypass SE', 'Thieves Triple Bypass WN',
    'Thieves Hellway Blue Barrier', 'Thieves Hellway Crystal Blue Barrier', 'Thieves Attic ES',
    'Thieves Basement Block Path', 'Thieves Blocked Entry Path', 'Thieves Conveyor Bridge Block Path',
    'Thieves Conveyor Block Path', 'Ice Lobby WS', 'Ice Cross Left Push Block', 'Ice Cross Bottom Push Block Left',
    'Ice Bomb Drop Hole', 'Ice Pengator Switch WS', 'Ice Pengator Switch ES', 'Ice Big Key Push Block', 'Ice Stalfos Hint SE', 'Ice Bomb Jump EN',
    'Ice Pengator Trap NE', 'Ice Hammer Block ES', 'Ice Tongue Pull WS', 'Ice Freezors Bomb Hole', 'Ice Tall Hint WS',
    'Ice Hookshot Ledge Path', 'Ice Hookshot Balcony Path', 'Ice Many Pots SW', 'Ice Many Pots WS',
    'Ice Crystal Right Blue Hole', 'Ice Crystal Left Blue Barrier', 'Ice Big Chest Landing Push Blocks',
    'Ice Backwards Room Hole', 'Ice Switch Room SE', 'Ice Antechamber NE', 'Ice Antechamber Hole', 'Mire Lobby Gap',
    'Mire Post-Gap Gap', 'Mire 2 NE', 'Mire Hub Upper Blue Barrier', 'Mire Hub Lower Blue Barrier',
    'Mire Hub Right Blue Barrier', 'Mire Hub Top Blue Barrier', 'Mire Hub Switch Blue Barrier N',
    'Mire Hub Switch Blue Barrier S', 'Mire Falling Bridge WN', 'Mire Map Spike Side Blue Barrier',
    'Mire Map Spot Blue Barrier', 'Mire Crystal Dead End Left Barrier', 'Mire Crystal Dead End Right Barrier',
    'Mire Cross ES', 'Mire Left Bridge Hook Path', 'Mire Fishbone Blue Barrier',
    'Mire South Fish Blue Barrier', 'Mire Tile Room NW', 'Mire Compass Blue Barrier', 'Mire Attic Hint Hole',
    'Mire Dark Shooters SW', 'Mire Crystal Mid Blue Barrier', 'Mire Crystal Left Blue Barrier', 'TR Main Lobby Gap',
    'TR Lobby Ledge Gap', 'TR Hub SW', 'TR Hub SE', 'TR Hub ES', 'TR Hub EN', 'TR Hub NW', 'TR Hub NE', 'TR Hub Path',
    'TR Hub Ledges Path', 'TR Torches NW', 'TR Pokey 2 Bottom to Top Barrier - Blue',
    'TR Pokey 2 Top to Bottom Barrier - Blue', 'TR Twin Pokeys SW', 'TR Twin Pokeys EN', 'TR Big Chest Gap',
    'TR Big Chest Entrance Gap', 'TR Lazy Eyes ES', 'TR Tongue Pull WS', 'TR Tongue Pull NE', 'TR Dark Ride Up Stairs',
    'TR Dark Ride SW', 'TR Dark Ride Path', 'TR Dark Ride Ledges Path',
    'TR Crystal Maze Start to Interior Barrier - Blue', 'TR Crystal Maze End to Interior Barrier - Blue',
    'TR Final Abyss Balcony Path', 'TR Final Abyss Ledge Path', 'GT Hope Room EN', 'GT Blocked Stairs Block Path',
    'GT Bob\'s Room Hole', 'GT Speed Torch SE', 'GT Speed Torch South Path', 'GT Speed Torch North Path',
    'GT Crystal Conveyor NE', 'GT Crystal Conveyor WN', 'GT Conveyor Cross EN', 'GT Conveyor Cross WN',
    'GT Hookshot East-Mid Path', 'GT Hookshot South-Mid Path', 'GT Hookshot North-Mid Path',
    'GT Hookshot Mid-South Path', 'GT Hookshot Mid-East Path', 'GT Hookshot Mid-North Path',
    'GT Hookshot Platform Blue Barrier', 'GT Hookshot Entry Blue Barrier', 'GT Double Switch Pot Corners to Exit Barrier - Blue',
    'GT Double Switch Exit to Blue Barrier', 'GT Firesnake Room Hook Path', 'GT Falling Bridge WN', 'GT Falling Bridge WS',
    'GT Ice Armos NE', 'GT Ice Armos WS', 'GT Crystal Paths SW', 'GT Mimics 1 NW', 'GT Mimics 1 ES', 'GT Mimics 2 WS',
    'GT Mimics 2 NE', 'GT Hidden Spikes EN', 'GT Cannonball Bridge SE', 'GT Gauntlet 1 WN', 'GT Gauntlet 2 EN',
    'GT Gauntlet 2 SW', 'GT Gauntlet 3 NW',  'GT Gauntlet 3 SW', 'GT Gauntlet 4 NW', 'GT Gauntlet 4 SW',
    'GT Gauntlet 5 NW', 'GT Gauntlet 5 WS', 'GT Lanmolas 2 ES', 'GT Lanmolas 2 NW', 'GT Wizzrobes 1 SW',
    'GT Wizzrobes 2 SE', 'GT Wizzrobes 2 NE', 'GT Torch Cross ES', 'GT Falling Torches NE', 'GT Moldorm Gap',
    'GT Validation Block Path'
}


def add_key_logic_rules(world, player):
    key_logic = world.key_logic[player]
    for d_name, d_logic in key_logic.items():
        for door_name, rule in d_logic.door_rules.items():
            door_entrance = world.get_entrance(door_name, player)
            add_rule(door_entrance, eval_small_key_door(door_name, d_name, player))
            if door_entrance.door.dependents:
                for dep in door_entrance.door.dependents:
                    add_rule(dep.entrance, eval_small_key_door(door_name, d_name, player))
        for location in d_logic.bk_restricted:
            if not location.forced_item:
                forbid_item(location, d_logic.bk_name, player)
        for location in d_logic.sm_restricted:
            forbid_item(location, d_logic.small_key_name, player)
        for door in d_logic.bk_doors:
            add_rule(world.get_entrance(door.name, player), create_rule(d_logic.bk_name, player))
        for chest in d_logic.bk_chests:
            big_chest = world.get_location(chest.name, player)
            add_rule(big_chest, create_rule(d_logic.bk_name, player))
            if len(d_logic.bk_doors) == 0 and len(d_logic.bk_chests) <= 1:
                set_always_allow(big_chest, allow_big_key_in_big_chest(d_logic.bk_name, player))
    if world.retro[player]:
        for d_name, layout in world.key_layout[player].items():
            for door in layout.flat_prop:
                if world.mode[player] != 'standard' or not retro_in_hc(door.entrance):
                    add_rule(door.entrance, create_key_rule('Small Key (Universal)', player, 1))


def eval_small_key_door_main(state, door_name, dungeon, player):
    if state.is_door_open(door_name, player):
        return True
    key_logic = state.world.key_logic[player][dungeon]
    door_rule = key_logic.door_rules[door_name]
    door_openable = False
    for ruleType, number in door_rule.new_rules.items():
        if door_openable:
            return True
        if ruleType == KeyRuleType.WorstCase:
            door_openable |= state.has_sm_key(key_logic.small_key_name, player, number)
        elif ruleType == KeyRuleType.AllowSmall:
            if (door_rule.small_location.item and door_rule.small_location.item.name == key_logic.small_key_name
               and door_rule.small_location.item.player == player):
                return True  # always okay if allow small is on
        elif isinstance(ruleType, tuple):
            lock, lock_item = ruleType
            # this doesn't track logical locks yet, i.e. hammer locks the item and hammer is there, but the item isn't
            for loc in door_rule.alternate_big_key_loc:
                spot = state.world.get_location(loc, player)
                if spot.item and spot.item.name == lock_item:
                    door_openable |= state.has_sm_key(key_logic.small_key_name, player, number)
                    break
    return door_openable


def eval_small_key_door(door_name, dungeon, player):
    return lambda state: eval_small_key_door_main(state, door_name, dungeon, player)


def allow_big_key_in_big_chest(bk_name, player):
    return lambda state, item: item.name == bk_name and item.player == player


def retro_in_hc(spot):
    return spot.parent_region.dungeon.name == 'Hyrule Castle' if spot.parent_region.dungeon else False


def create_rule(item_name, player):
    return lambda state: state.has(item_name, player)


def create_key_rule(small_key_name, player, keys):
    return lambda state: state.has_sm_key(small_key_name, player, keys)


def create_key_rule_allow_small(small_key_name, player, keys, location):
    loc = location.name
    return lambda state: state.has_sm_key(small_key_name, player, keys) or (item_name(state, loc, player) in [(small_key_name, player)] and state.has_sm_key(small_key_name, player, keys-1))


def create_key_rule_bk_exception(small_key_name, big_key_name, player, keys, bk_keys, bk_locs):
    chest_names = [x.name for x in bk_locs]
    return lambda state: (state.has_sm_key(small_key_name, player, keys) and not item_in_locations(state, big_key_name, player, zip(chest_names, [player] * len(chest_names)))) or (item_in_locations(state, big_key_name, player, zip(chest_names, [player] * len(chest_names))) and state.has_sm_key(small_key_name, player, bk_keys))


def create_key_rule_bk_exception_or_allow(small_key_name, big_key_name, player, keys, location, bk_keys, bk_locs):
    loc = location.name
    chest_names = [x.name for x in bk_locs]
    return lambda state: (state.has_sm_key(small_key_name, player, keys) and not item_in_locations(state, big_key_name, player, zip(chest_names, [player] * len(chest_names)))) or (item_name(state, loc, player) in [(small_key_name, player)] and state.has_sm_key(small_key_name, player, keys-1)) or (item_in_locations(state, big_key_name, player, zip(chest_names, [player] * len(chest_names))) and state.has_sm_key(small_key_name, player, bk_keys))


def create_advanced_key_rule(key_logic, player, rule):
    if not rule.allow_small and rule.alternate_small_key is None:
        return create_key_rule(key_logic.small_key_name, player, rule.small_key_num)
    if rule.allow_small and rule.alternate_small_key is None:
        return create_key_rule_allow_small(key_logic.small_key_name, player, rule.small_key_num, rule.small_location)
    if not rule.allow_small and rule.alternate_small_key is not None:
        return create_key_rule_bk_exception(key_logic.small_key_name, key_logic.bk_name, player, rule.small_key_num,
                                            rule.alternate_small_key, rule.alternate_big_key_loc)
    if rule.allow_small and rule.alternate_small_key is not None:
        return create_key_rule_bk_exception_or_allow(key_logic.small_key_name, key_logic.bk_name, player,
                                                     rule.small_key_num, rule.small_location, rule.alternate_small_key,
                                                     rule.alternate_big_key_loc)

import RaceRandom as random, logging, copy
from collections import OrderedDict, defaultdict
from DungeonGenerator import GenerationException
from BaseClasses import OWEdge, WorldType, RegionType, Direction, Terrain, PolSlot, Entrance
from Regions import mark_dark_world_regions, mark_light_world_regions
from OWEdges import OWTileRegions, OWEdgeGroups, OWExitTypes, OpenStd, parallel_links, IsParallel
from Utils import bidict

version_number = '0.2.8.0'
version_branch = ''
__version__ = '%s%s' % (version_number, version_branch)

def link_overworld(world, player):
    # setup mandatory connections
    for exitname, regionname in mandatory_connections:
        connect_simple(world, exitname, regionname, player)

    def performSwap(groups, swaps):
        def getParallel(edgename):
            if edgename in parallel_links:
                return parallel_links[edgename]
            elif edgename in parallel_links.inverse:
                return parallel_links.inverse[edgename][0]
            else:
                raise Exception('No parallel edge found for edge %s', edgename)
        
        def getNewSets(all_set, other_set):
            new_all_set = list(map(getParallel, all_set))
            if not all(edge in orig_swaps for edge in new_all_set):
                raise Exception('Cannot move a parallel edge without the other')
            else:
                for edge in new_all_set:
                    swaps.remove(edge)
            new_other_set = getNewSet(other_set)
            return (new_all_set, new_other_set)
        
        def getNewSet(edge_set):
            new_set = []
            for edge in edge_set:
                if edge in orig_swaps:
                    new_edge = getParallel(edge)
                    if new_edge not in orig_swaps:
                        raise Exception('Cannot move a parallel edge without the other')
                    new_set.append(new_edge)
                    swaps.remove(new_edge)
                else:
                    new_set.append(edge)
            return new_set
        
        # swaps edges from one pool to another
        orig_swaps = copy.deepcopy(swaps)
        new_groups = {}
        for group in groups.keys():
            new_groups[group] = ([],[])
        
        for group in groups.keys():
            (mode, wrld, dir, terrain, parallel, count) = group
            for (forward_set, back_set) in zip(groups[group][0], groups[group][1]):
                anyF = any(edge in orig_swaps for edge in forward_set)
                anyB = any(edge in orig_swaps for edge in back_set)
                allF = all(edge in orig_swaps for edge in forward_set)
                allB = all(edge in orig_swaps for edge in back_set)
                if not (anyF or anyB):
                    # no change
                    new_groups[group][0].append(forward_set)
                    new_groups[group][1].append(back_set)
                elif allF and allB:
                    # move both sets
                    if parallel == IsParallel.Yes and not (all(edge in orig_swaps for edge in map(getParallel, forward_set)) and all(edge in orig_swaps for edge in map(getParallel, back_set))):
                        raise Exception('Cannot move a parallel edge without the other')
                    new_mode = OpenStd.Open
                    if tuple((OpenStd.Open, WorldType((int(wrld) + 1) % 2), dir, terrain, parallel, count)) not in new_groups.keys():
                        # when Links House tile is swapped, the DW edges need to get put into existing Standard group
                        new_mode = OpenStd.Standard
                    new_groups[(new_mode, WorldType((int(wrld) + 1) % 2), dir, terrain, parallel, count)][0].append(forward_set)
                    new_groups[(new_mode, WorldType((int(wrld) + 1) % 2), dir, terrain, parallel, count)][1].append(back_set)
                    for edge in forward_set:
                        swaps.remove(edge)
                    for edge in back_set:
                        swaps.remove(edge)
                elif anyF or anyB:
                    if parallel == IsParallel.Yes:
                        if allF or allB:
                            # move one set
                            if allF and not (world.owKeepSimilar[player] and anyB):
                                (new_forward_set, new_back_set) = getNewSets(forward_set, back_set)
                            elif allB and not (world.owKeepSimilar[player] and anyF):
                                (new_back_set, new_forward_set) = getNewSets(back_set, forward_set)
                            else:
                                raise Exception('Cannot move an edge out of a Similar group')
                            new_groups[group][0].append(new_forward_set)
                            new_groups[group][1].append(new_back_set)
                        else:
                            # move individual edges
                            if not world.owKeepSimilar[player]:
                                new_groups[group][0].append(getNewSet(forward_set) if anyF else forward_set)
                                new_groups[group][1].append(getNewSet(back_set) if anyB else back_set)
                            else:
                                raise Exception('Cannot move an edge out of a Similar group')
                    else:
                        raise NotImplementedError('Cannot move one side of a non-parallel connection')
                else:
                    raise NotImplementedError('Invalid OW Edge swap scenario')
        return new_groups

    tile_groups = define_tile_groups(world, player, False)
    trimmed_groups = copy.deepcopy(OWEdgeGroups)
    swapped_edges = list()

    # restructure Maze Race/Suburb/Frog/Dig Game manually due to NP/P relationship
    if world.owKeepSimilar[player]:
        for group in trimmed_groups.keys():
            (std, region, axis, terrain, parallel, _) = group
            if parallel == IsParallel.Yes:
                (forward_edges, back_edges) = trimmed_groups[group]
                if ['Maze Race ES'] in forward_edges:
                    forward_edges = list(filter((['Maze Race ES']).__ne__, forward_edges))
                    trimmed_groups[(std, region, axis, terrain, IsParallel.No, 1)][0].append(['Maze Race ES'])
                if ['Kakariko Suburb WS'] in back_edges:
                    back_edges = list(filter((['Kakariko Suburb WS']).__ne__, back_edges))
                    trimmed_groups[(std, region, axis, terrain, IsParallel.No, 1)][1].append(['Kakariko Suburb WS'])
                trimmed_groups[group] = (forward_edges, back_edges)
    else:
        for group in trimmed_groups.keys():
            (std, region, axis, terrain, _, _) = group
            (forward_edges, back_edges) = trimmed_groups[group]
            if ['Dig Game EC', 'Dig Game ES'] in forward_edges:
                forward_edges = list(filter((['Dig Game EC', 'Dig Game ES']).__ne__, forward_edges))
                trimmed_groups[(std, region, axis, terrain, IsParallel.Yes, 1)][0].append(['Dig Game ES'])
                trimmed_groups[(std, region, axis, terrain, IsParallel.No, 1)][0].append(['Dig Game EC'])
            if ['Frog WC', 'Frog WS'] in back_edges:
                back_edges = list(filter((['Frog WC', 'Frog WS']).__ne__, back_edges))
                trimmed_groups[(std, region, axis, terrain, IsParallel.Yes, 1)][1].append(['Frog WS'])
                trimmed_groups[(std, region, axis, terrain, IsParallel.No, 1)][1].append(['Frog WC'])
            trimmed_groups[group] = (forward_edges, back_edges)

    connected_edges = []
    if world.owShuffle[player] != 'vanilla':
        trimmed_groups = remove_reserved(world, trimmed_groups, connected_edges, player)
        trimmed_groups = reorganize_groups(world, trimmed_groups, player)

    # tile shuffle
    logging.getLogger('').debug('Swapping overworld tiles')
    if world.owMixed[player]:
        swapped_edges = shuffle_tiles(world, tile_groups, world.owswaps[player], False, player)
        
        update_world_regions(world, player)

        # update spoiler
        s = list(map(lambda x: ' ' if x not in world.owswaps[player][0] else 'S', [i for i in range(0x40, 0x82)]))
        text_output = tile_swap_spoiler_table.replace('s', '%s') % (                         s[0x02],                                s[0x07],
                                                                                 s[0x00],                s[0x03],        s[0x05],
            s[0x00],        s[0x02],s[0x03],        s[0x05],        s[0x07],                 s[0x0a],                                s[0x0f],
                            s[0x0a],                                s[0x0f],
            s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17], s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17],
            s[0x18],        s[0x1a],s[0x1b],        s[0x1d],s[0x1e],
                            s[0x22],                s[0x25],                                 s[0x1a],                s[0x1d],
            s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],     s[0x18],                s[0x1b],                s[0x1e],
            s[0x30],        s[0x32],s[0x33],s[0x34],s[0x35],        s[0x37],                 s[0x22],                s[0x25],
                            s[0x3a],s[0x3b],s[0x3c],                s[0x3f],
                                                                             s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],
                                                                    s[0x40],                 s[0x32],s[0x33],s[0x34],                s[0x37],
                                                                                 s[0x30],                                s[0x35],
                                                                    s[0x41],                 s[0x3a],s[0x3b],s[0x3c],                s[0x3f])
        world.spoiler.set_map('swaps', text_output, world.owswaps[player][0], player)
    
    # apply tile logical connections
    for owid in ow_connections.keys():
        if not world.is_tile_swapped(owid, player):
            for (exitname, regionname) in ow_connections[owid][0]:
                connect_simple(world, exitname, regionname, player)
        else:
            for (exitname, regionname) in ow_connections[owid][1]:
                connect_simple(world, exitname, regionname, player)

    categorize_world_regions(world, player)
    
    # crossed shuffle
    logging.getLogger('').debug('Crossing overworld edges')
    crossed_edges = list()

    # more Maze Race/Suburb/Frog/Dig Game fixes
    parallel_links_new = bidict(parallel_links) # shallow copy is enough (deep copy is broken)
    if world.owKeepSimilar[player]:
        del parallel_links_new['Maze Race ES']
        del parallel_links_new['Kakariko Suburb WS']

    #TODO: Revisit with changes to Limited/Allowed
    if world.owCrossed[player] not in ['none', 'grouped', 'polar', 'chaos']:
        for edge in swapped_edges:
            if edge not in parallel_links_new and edge not in parallel_links_new.inverse:
                crossed_edges.append(edge)
    
    if world.owCrossed[player] in ['grouped', 'limited'] or (world.owShuffle[player] == 'vanilla' and world.owCrossed[player] == 'chaos'):
        if world.owCrossed[player] == 'grouped':
            # the idea is to XOR the new swaps with the ones from Mixed so that non-parallel edges still work
            # Polar corresponds to Grouped with no swaps in ow_crossed_tiles_mask
            ow_crossed_tiles_mask = [[],[],[]]
            crossed_edges = shuffle_tiles(world, define_tile_groups(world, player, True), ow_crossed_tiles_mask, True, player)
            ow_crossed_tiles = [i for i in range(0x82) if (i in world.owswaps[player][0]) != (i in ow_crossed_tiles_mask[0])]

            # update spoiler
            s = list(map(lambda x: 'O' if x not in ow_crossed_tiles else 'X', [i for i in range(0x40, 0x82)]))
            text_output = tile_swap_spoiler_table.replace('s', '%s') % (                         s[0x02],                                s[0x07],
                                                                                     s[0x00],                s[0x03],        s[0x05],
                s[0x00],        s[0x02],s[0x03],        s[0x05],        s[0x07],                 s[0x0a],                                s[0x0f],
                                s[0x0a],                                s[0x0f],
                s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17], s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17],
                s[0x18],        s[0x1a],s[0x1b],        s[0x1d],s[0x1e],
                                s[0x22],                s[0x25],                                 s[0x1a],                s[0x1d],
                s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],     s[0x18],                s[0x1b],                s[0x1e],
                s[0x30],        s[0x32],s[0x33],s[0x34],s[0x35],        s[0x37],                 s[0x22],                s[0x25],
                                s[0x3a],s[0x3b],s[0x3c],                s[0x3f],
                                                                                 s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],
                                                                        s[0x40],                 s[0x32],s[0x33],s[0x34],                s[0x37],
                                                                                    s[0x30],                                s[0x35],
                                                                        s[0x41],                 s[0x3a],s[0x3b],s[0x3c],                s[0x3f])
            world.spoiler.set_map('groups', text_output, ow_crossed_tiles, player)
        else:
            crossed_candidates = list()
            for group in trimmed_groups.keys():
                (mode, wrld, dir, terrain, parallel, count) = group
                if wrld == WorldType.Light and mode != OpenStd.Standard:
                    for (forward_set, back_set) in zip(trimmed_groups[group][0], trimmed_groups[group][1]):
                        if forward_set[0] in parallel_links_new or forward_set[0] in parallel_links_new.inverse:
                            if world.owKeepSimilar[player]:
                                if world.owCrossed[player] == 'chaos' and random.randint(0, 1):
                                    for edge in forward_set:
                                        crossed_edges.append(edge)
                                elif world.owCrossed[player] == 'limited':
                                    crossed_candidates.append(forward_set)
                            else:
                                for edge in forward_set:
                                    if world.owCrossed[player] == 'chaos' and random.randint(0, 1):
                                        crossed_edges.append(edge)
                                    elif world.owCrossed[player] == 'limited':
                                        crossed_candidates.append([edge])
            if world.owCrossed[player] == 'limited':
                random.shuffle(crossed_candidates)
                for edge_set in crossed_candidates[:9]:
                    for edge in edge_set:
                        crossed_edges.append(edge)
            for edge in copy.deepcopy(crossed_edges):
                if edge in parallel_links_new:
                    crossed_edges.append(parallel_links_new[edge])
                elif edge in parallel_links_new.inverse:
                    crossed_edges.append(parallel_links_new.inverse[edge][0])

    # after tile swap and crossed, determine edges that need to swap
    edges_to_swap = [e for e in swapped_edges+crossed_edges if (e not in swapped_edges) or (e not in crossed_edges)]

    # whirlpool shuffle
    logging.getLogger('').debug('Shuffling whirlpools')

    if not world.owWhirlpoolShuffle[player]:
        for (_, from_whirlpool, from_region), (_, to_whirlpool, to_region) in default_whirlpool_connections:
            connect_simple(world, from_whirlpool, to_region, player)
            connect_simple(world, to_whirlpool, from_region, player)
    else:
        whirlpool_candidates = [[],[]]
        world.owwhirlpools[player] = [None] * 8
        for (from_owid, from_whirlpool, from_region), (to_owid, to_whirlpool, to_region) in default_whirlpool_connections:
            if world.owCrossed[player] == 'polar' and world.owMixed[player] and from_owid == 0x55:
                # connect the 2 DW whirlpools in Polar Mixed
                connect_simple(world, from_whirlpool, to_region, player)
                connect_simple(world, to_whirlpool, from_region, player)
                world.owwhirlpools[player][7] = from_owid
                world.owwhirlpools[player][6] = to_owid
                world.spoiler.set_overworld(from_whirlpool, to_whirlpool, 'both', player)
            else:
                if ((world.owCrossed[player] == 'none' or (world.owCrossed[player] == 'polar' and not world.owMixed[player])) and (world.get_region(from_region, player).type == RegionType.LightWorld)) \
                        or world.owCrossed[player] not in ['none', 'polar', 'grouped'] \
                        or (world.owCrossed[player] == 'grouped' and ((world.get_region(from_region, player).type == RegionType.LightWorld) == (from_owid not in ow_crossed_tiles))):
                    whirlpool_candidates[0].append(tuple((from_owid, from_whirlpool, from_region)))
                else:
                    whirlpool_candidates[1].append(tuple((from_owid, from_whirlpool, from_region)))
                
                if ((world.owCrossed[player] == 'none' or (world.owCrossed[player] == 'polar' and not world.owMixed[player])) and (world.get_region(to_region, player).type == RegionType.LightWorld)) \
                        or world.owCrossed[player] not in ['none', 'polar', 'grouped'] \
                        or (world.owCrossed[player] == 'grouped' and ((world.get_region(to_region, player).type == RegionType.LightWorld) == (to_owid not in ow_crossed_tiles))):
                    whirlpool_candidates[0].append(tuple((to_owid, to_whirlpool, to_region)))
                else:
                    whirlpool_candidates[1].append(tuple((to_owid, to_whirlpool, to_region)))

        # shuffle happens here
        whirlpool_map = [ 0x35, 0x0f, 0x15, 0x33, 0x12, 0x3f, 0x55, 0x7f ]
        for whirlpools in whirlpool_candidates:
            random.shuffle(whirlpools)
            while len(whirlpools):
                from_owid, from_whirlpool, from_region = whirlpools.pop()
                to_owid, to_whirlpool, to_region = whirlpools.pop()
                connect_simple(world, from_whirlpool, to_region, player)
                connect_simple(world, to_whirlpool, from_region, player)
                world.owwhirlpools[player][next(i for i, v in enumerate(whirlpool_map) if v == to_owid)] = from_owid
                world.owwhirlpools[player][next(i for i, v in enumerate(whirlpool_map) if v == from_owid)] = to_owid
                world.spoiler.set_overworld(from_whirlpool, to_whirlpool, 'both', player)

    # layout shuffle
    logging.getLogger('').debug('Shuffling overworld layout')

    if world.owShuffle[player] == 'vanilla':
        # apply outstanding swaps
        trimmed_groups = performSwap(trimmed_groups, edges_to_swap)
        assert len(edges_to_swap) == 0, 'Not all edges were swapped successfully: ' + ', '.join(edges_to_swap)
        
        # vanilla transitions
        groups = list(trimmed_groups.values())
        for (forward_edge_sets, back_edge_sets) in groups:
            assert len(forward_edge_sets) == len(back_edge_sets)
            for (forward_set, back_set) in zip(forward_edge_sets, back_edge_sets):
                assert len(forward_set) == len(back_set)
                for (forward_edge, back_edge) in zip(forward_set, back_set):
                    connect_two_way(world, forward_edge, back_edge, player, connected_edges)

        world.owsectors[player] = build_sectors(world, player)
    else:
        if world.owKeepSimilar[player] and world.owShuffle[player] in ['vanilla', 'parallel']:
            for exitname, destname in parallelsimilar_connections:
                connect_two_way(world, exitname, destname, player, connected_edges)

        #TODO: Remove, just for testing
        for exitname, destname in test_connections:
            connect_two_way(world, exitname, destname, player, connected_edges)
        
        connect_custom(world, connected_edges, player)
        
        # layout shuffle
        groups = adjust_edge_groups(world, trimmed_groups, edges_to_swap, player)
        
        tries = 20
        valid_layout = False
        connected_edge_cache = connected_edges.copy()
        while not valid_layout and tries > 0:
            connected_edges = connected_edge_cache.copy()

            if world.mode[player] == 'standard':
                random.shuffle(groups[2:]) # keep first 2 groups (Standard) first
            else:
                random.shuffle(groups)

            for (forward_edge_sets, back_edge_sets) in groups:
                assert len(forward_edge_sets) == len(back_edge_sets)
                random.shuffle(forward_edge_sets)
                random.shuffle(back_edge_sets)
                if len(forward_edge_sets) > 0:
                    f = 0
                    b = 0
                    while f < len(forward_edge_sets) and b < len(back_edge_sets):
                        forward_set = forward_edge_sets[f]
                        back_set = back_edge_sets[b]
                        while forward_set[0] in connected_edges:
                            f += 1
                            if f < len(forward_edge_sets):
                                forward_set = forward_edge_sets[f]
                            else:
                                forward_set = None
                                break
                        f += 1
                        while back_set[0] in connected_edges:
                            b += 1
                            if b < len(back_edge_sets):
                                back_set = back_edge_sets[b]
                            else:
                                back_set = None
                                break
                        b += 1
                        if forward_set is not None and back_set is not None:
                            assert len(forward_set) == len(back_set)
                            for (forward_edge, back_edge) in zip(forward_set, back_set):
                                connect_two_way(world, forward_edge, back_edge, player, connected_edges)
                        elif forward_set is not None:
                            logging.getLogger('').warning("Edge '%s' could not find a valid connection" % forward_set[0])
                        elif back_set is not None:
                            logging.getLogger('').warning("Edge '%s' could not find a valid connection" % back_set[0])
            assert len(connected_edges) == len(default_connections) * 2, connected_edges
            
            world.owsectors[player] = build_sectors(world, player)
            valid_layout = validate_layout(world, player)

            tries -= 1
        assert valid_layout, 'Could not find a valid OW layout'

    # flute shuffle
    logging.getLogger('').debug('Shuffling flute spots')
    def connect_flutes(flute_destinations):
        for o in range(0, len(flute_destinations)):
            owslot = flute_destinations[o]
            regions = flute_data[owslot][0]
            if not world.is_tile_swapped(flute_data[owslot][1], player):
                connect_simple(world, 'Flute Spot ' + str(o + 1), regions[0], player)
            else:
                connect_simple(world, 'Flute Spot ' + str(o + 1), regions[1], player)
    
    if world.owFluteShuffle[player] == 'vanilla':
        connect_flutes(default_flute_connections)
    else:
        flute_pool = list(flute_data.keys())
        new_spots = list()
        ignored_regions = set()

        def addSpot(owid, ignore_proximity):
            if world.owFluteShuffle[player] == 'balanced':
                def getIgnored(regionname, base_owid, owid):
                    region = world.get_region(regionname, player)
                    for exit in region.exits:
                        if exit.connected_region is not None and exit.connected_region.type in [RegionType.LightWorld, RegionType.DarkWorld] and exit.connected_region.name not in new_ignored:
                            if exit.connected_region.name in OWTileRegions and (OWTileRegions[exit.connected_region.name] in [base_owid, owid] or OWTileRegions[regionname] == base_owid):
                                new_ignored.add(exit.connected_region.name)
                                getIgnored(exit.connected_region.name, base_owid, OWTileRegions[exit.connected_region.name])

                if not world.is_tile_swapped(flute_data[owid][1], player):
                    new_region = flute_data[owid][0][0]
                else:
                    new_region = flute_data[owid][0][1]

                if new_region in ignored_regions:
                    return False
                
                new_ignored = {new_region}
                getIgnored(new_region, OWTileRegions[new_region], OWTileRegions[new_region])
                if not ignore_proximity and random.randint(0, 31) != 0 and new_ignored.intersection(ignored_regions):
                    return False
                ignored_regions.update(new_ignored)
            flute_pool.remove(owid)
            if ignore_proximity:
                logging.getLogger('').warning(f'Warning: Adding flute spot within proximity: {hex(owid)}')
            new_spots.append(owid)
            return True
        
        # determine sectors (isolated groups of regions) to place flute spots
        flute_regions = {(f[0][0] if (f[1] not in world.owswaps[player][0]) != (world.mode[player] == 'inverted') else f[0][1]) : o for o, f in flute_data.items()}
        flute_sectors = [(len([r for l in s for r in l]), [r for l in s for r in l if r in flute_regions]) for s in world.owsectors[player]]
        flute_sectors = [s for s in flute_sectors if len(s[1]) > 0]
        region_total = sum([c for c,_ in flute_sectors])
        sector_total = len(flute_sectors)

        # reserve a number of flute spots for each sector
        flute_spots = 8
        for sector in flute_sectors:
            sector_total -= 1
            spots_to_place = min(flute_spots - sector_total, max(1, round((sector[0] * (flute_spots - sector_total) / region_total) + 0.5)))
            target_spots = len(new_spots) + spots_to_place
            
            if 'Desert Palace Teleporter Ledge' in sector[1] or 'Misery Mire Teleporter Ledge' in sector[1]:
                addSpot(0x38, False) # guarantee desert/mire access

            random.shuffle(sector[1])
            f = 0
            t = 0
            while len(new_spots) < target_spots:
                if f >= len(sector[1]):
                    f = 0
                    t += 1
                    if t > 5:
                        raise GenerationException('Infinite loop detected in flute shuffle')
                if sector[1][f] not in new_spots:
                    addSpot(flute_regions[sector[1][f]], t > 0)
                f += 1

            region_total -= sector[0]
            flute_spots -= spots_to_place
        
        # connect new flute spots
        new_spots.sort()
        world.owflutespots[player] = new_spots
        connect_flutes(new_spots)

        # update spoiler
        new_spots = list(map(lambda o: flute_data[o][1], new_spots))
        s = list(map(lambda x: ' ' if x not in new_spots else 'F', [i for i in range(0x40)]))
        text_output = flute_spoiler_table.replace('s', '%s') % (                             s[0x02],                                s[0x07],
                                                                                 s[0x00],                s[0x03],        s[0x05],
            s[0x00],        s[0x02],s[0x03],        s[0x05],        s[0x07],                 s[0x0a],                                s[0x0f],
                            s[0x0a],                                s[0x0f],
            s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17], s[0x10],s[0x11],s[0x12],s[0x13],s[0x14],s[0x15],s[0x16],s[0x17],
            s[0x18],        s[0x1a],s[0x1b],        s[0x1d],s[0x1e],
                            s[0x22],                s[0x25],                                 s[0x1a],                s[0x1d],
            s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],     s[0x18],                s[0x1b],                s[0x1e],
            s[0x30],        s[0x32],s[0x33],s[0x34],s[0x35],        s[0x37],                 s[0x22],                s[0x25],
                            s[0x3a],s[0x3b],s[0x3c],                s[0x3f],
                                                                             s[0x28],s[0x29],s[0x2a],s[0x2b],s[0x2c],s[0x2d],s[0x2e],s[0x2f],
                                                                                             s[0x32],s[0x33],s[0x34],                s[0x37],
                                                                                 s[0x30],                                s[0x35],
                                                                                             s[0x3a],s[0x3b],s[0x3c],                s[0x3f])
        world.spoiler.set_map('flute', text_output, new_spots, player)

def connect_custom(world, connected_edges, player):
    if hasattr(world, 'custom_overworld') and world.custom_overworld[player]:
        for edgename1, edgename2 in world.custom_overworld[player]:
            if edgename1 in connected_edges or edgename2 in connected_edges:
                owedge1 = world.check_for_owedge(edgename1, player)
                owedge2 = world.check_for_owedge(edgename2, player)
                if owedge1.dest is not None and owedge1.dest.name == owedge2.name:
                    continue # if attempting to connect a pair that was already connected earlier, allow it to continue
                raise RuntimeError('Invalid plando connection: rule violation based on current settings')
            connect_two_way(world, edgename1, edgename2, player, connected_edges)
            if world.owKeepSimilar[player]: #TODO: If connecting an edge that belongs to a similar pair, the remaining edges need to get connected automatically
                continue

def connect_simple(world, exitname, regionname, player):
    world.get_entrance(exitname, player).connect(world.get_region(regionname, player))

def connect_two_way(world, edgename1, edgename2, player, connected_edges=None):
    edge1 = world.get_entrance(edgename1, player)
    edge2 = world.get_entrance(edgename2, player)
    x = world.check_for_owedge(edgename1, player)
    y = world.check_for_owedge(edgename2, player)
    
    if x is None:
        raise Exception('%s is not a valid edge.', edgename1)
    elif y is None:
        raise Exception('%s is not a valid edge.', edgename2)
    if connected_edges is not None:
        if edgename1 in connected_edges or edgename2 in connected_edges:
            if (x.dest and x.dest.name == edgename2) and (y.dest and y.dest.name == edgename1):
                return
            else:
                raise Exception('Edges \'%s\' and \'%s\' already connected elsewhere', edgename1, edgename2)
    
    # if these were already connected somewhere, remove the backreference
    if edge1.connected_region is not None:
        edge1.connected_region.entrances.remove(edge1)
    if edge2.connected_region is not None:
        edge2.connected_region.entrances.remove(edge2)

    edge1.connect(edge2.parent_region)
    edge2.connect(edge1.parent_region)
    x.dest = y
    y.dest = x

    if world.owShuffle[player] != 'vanilla' or world.owMixed[player] or world.owCrossed[player] != 'none':
        world.spoiler.set_overworld(edgename2, edgename1, 'both', player)

    if connected_edges is not None:
        connected_edges.append(edgename1)
        connected_edges.append(edgename2)
    
        # connecting parallel connections
        if world.owShuffle[player] in ['vanilla', 'parallel']:
            if (edgename1 in parallel_links.keys() or edgename1 in parallel_links.inverse.keys()):
                try:
                    parallel_forward_edge = parallel_links[edgename1] if edgename1 in parallel_links.keys() else parallel_links.inverse[edgename1][0]
                    parallel_back_edge = parallel_links[edgename2] if edgename2 in parallel_links.keys() else parallel_links.inverse[edgename2][0]
                    if not (parallel_forward_edge in connected_edges) and not (parallel_back_edge in connected_edges):
                        connect_two_way(world, parallel_forward_edge, parallel_back_edge, player, connected_edges)
                except KeyError:
                    raise KeyError('No parallel edge for edge %s' % edgename2)

def shuffle_tiles(world, groups, result_list, do_grouped, player):
    swapped_edges = list()
    group_parity = {}
    for group_data in groups:
        group = group_data[0]
        parity = [0, 0, 0, 0, 0]
        # vertical land
        if 0x00 in group:
            parity[0] += 1
        if 0x0f in group:
            parity[0] += 1
        if 0x80 in group:
            parity[0] -= 1
        if 0x81 in group:
            parity[0] -= 1
        # horizontal land
        if 0x1a in group:
            parity[1] -= 1
        if 0x1b in group:
            parity[1] += 1
        if 0x28 in group:
            parity[1] += 1
        if 0x29 in group:
            parity[1] -= 1
        if 0x30 in group:
            parity[1] -= 2
        if 0x3a in group:
            parity[1] += 2
        # horizontal water
        if 0x2d in group:
            parity[2] += 1
        if 0x80 in group:
            parity[2] -= 1
        # whirlpool
        if 0x0f in group:
            parity[3] += 1
        if 0x12 in group:
            parity[3] += 1
        if 0x33 in group:
            parity[3] += 1
        if 0x35 in group:
            parity[3] += 1
        # dropdown exit
        if 0x00 in group or 0x02 in group or 0x13 in group or 0x15 in group or 0x18 in group or 0x22 in group:
            parity[4] += 1
        if 0x1b in group and world.mode[player] != 'standard':
            parity[4] += 1
        if 0x1b in group and world.shuffle_ganon:
            parity[4] -= 1
        group_parity[group[0]] = parity

    attempts = 1000
    while True:
        if attempts == 0: # expected to only occur with custom swaps
            raise GenerationException('Could not find valid tile swaps')

        # tile shuffle happens here
        removed = list()
        for group in groups:
            # if 0x1b in group[0] or (0x1a in group[0] and world.owCrossed[player] == 'none'): # TODO: Standard + Inverted
            if random.randint(0, 1):
                removed.append(group)

        # save shuffled tiles to list
        new_results = [[],[],[]]
        for group in groups:
            if group not in removed:
                (owids, lw_regions, dw_regions) = group
                (exist_owids, exist_lw_regions, exist_dw_regions) = new_results
                exist_owids.extend(owids)
                exist_lw_regions.extend(lw_regions)
                exist_dw_regions.extend(dw_regions)

        parity = [sum(group_parity[group[0][0]][i] for group in groups if group not in removed) for i in range(5)]
        parity[3] %= 2 # actual parity
        if (world.owCrossed[player] == 'none' or do_grouped) and parity[:4] != [0, 0, 0, 0]:
            attempts -= 1
            continue
        # ensure sanc can be placed in LW in certain modes
        if not do_grouped and world.shuffle[player] not in ['vanilla', 'dungeonssimple', 'dungeonsfull', 'lean', 'crossed', 'insanity'] and world.mode[player] != 'inverted' and (world.doorShuffle[player] != 'crossed' or world.intensity[player] < 3 or world.mode[player] == 'standard'):
            free_dw_drops = parity[4] + (1 if world.shuffle_ganon else 0)
            free_drops = 6 + (1 if world.mode[player] != 'standard' else 0) + (1 if world.shuffle_ganon else 0)
            if free_dw_drops == free_drops:
                    attempts -= 1
                    continue
        break

    (exist_owids, exist_lw_regions, exist_dw_regions) = result_list
    exist_owids.extend(new_results[0])
    exist_lw_regions.extend(new_results[1])
    exist_dw_regions.extend(new_results[2])

    # replace LW edges with DW
    if world.owCrossed[player] not in ['polar', 'grouped', 'chaos'] or do_grouped:
        # in polar, the actual edge connections remain vanilla
        def getSwappedEdges(world, lst, player):
            for regionname in lst:
                region = world.get_region(regionname, player)
                for exit in region.exits:
                    if exit.spot_type == 'OWEdge':
                        swapped_edges.append(exit.name)

        getSwappedEdges(world, result_list[1], player)
        getSwappedEdges(world, result_list[2], player)

    return swapped_edges

def define_tile_groups(world, player, do_grouped):
    groups = [[i, i + 0x40] for i in range(0x40)]

    def get_group(id):
        for group in groups:
            if id in group:
                return group

    def merge_groups(tile_links):
        for link in tile_links:
            merged_group = []
            for id in link:
                if id not in merged_group:
                    group = get_group(id)
                    groups.remove(group)
                    merged_group += group
            groups.append(merged_group)

    def can_shuffle_group(group):
        # escape sequence should stay normal in standard
        if world.mode[player] == 'standard' and (0x1b in group or 0x2b in group or 0x2c in group):
            return False
        
        # sanctuary/chapel should not be swapped if S+Q guaranteed to output on that screen
        if 0x13 in group and ((world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull'] \
                    and (world.mode[player] in ['standard', 'inverted'] or world.doorShuffle[player] != 'crossed' or world.intensity[player] < 3)) \
                or (world.shuffle[player] == 'lite' and world.mode[player] == 'inverted')):
            return False
        
        return True

    for i in [0x00, 0x03, 0x05, 0x18, 0x1b, 0x1e, 0x30, 0x35]:
        groups.remove(get_group(i + 1))
        groups.remove(get_group(i + 8))
        groups.remove(get_group(i + 9))
    groups.append([0x80])
    groups.append([0x81])

    if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull', 'simple']:
        merge_groups([[0x03, 0x0a], [0x28, 0x29]])

    if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull', 'simple', 'restricted', 'full', 'lite']:
        merge_groups([[0x13, 0x14]])

    if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'simple', 'restricted']:
        merge_groups([[0x05, 0x07]])

    if world.shuffle[player] == 'vanilla' or (world.mode[player] == 'standard' and world.shuffle[player] in ['dungeonssimple', 'dungeonsfull']):
        merge_groups([[0x13, 0x14, 0x1b]])

    if world.owShuffle[player] == 'vanilla' and (world.owCrossed[player] == 'none' or do_grouped):
        merge_groups([[0x00, 0x2d, 0x80], [0x0f, 0x81], [0x1a, 0x1b], [0x28, 0x29], [0x30, 0x3a]])

    if world.owShuffle[player] == 'parallel' and world.owKeepSimilar[player] and world.owCrossed[player] == 'none':
        merge_groups([[0x28, 0x29]])

    if not world.owWhirlpoolShuffle[player] and (world.owCrossed[player] == 'none' or do_grouped):
        merge_groups([[0x0f, 0x35], [0x12, 0x15, 0x33, 0x3f]])

    tile_groups = []
    for group in groups:
        if can_shuffle_group(group):
            lw_regions = []
            dw_regions = []
            for id in group:
                (lw_regions if id < 0x40 or id >= 0x80 else dw_regions).extend(OWTileRegions.inverse[id])
            tile_groups.append((group, lw_regions, dw_regions))

    return tile_groups

def remove_reserved(world, groupedlist, connected_edges, player):
    new_grouping = {}
    for group in groupedlist.keys():
        new_grouping[group] = ([], [])

    for group in groupedlist.keys():
        (forward_edges, back_edges) = groupedlist[group]

        # remove edges already connected (thru plando and other forced connections)
        for edge in connected_edges:
            forward_edges = list(list(filter((edge).__ne__, i)) for i in forward_edges)
            back_edges = list(list(filter((edge).__ne__, i)) for i in back_edges)

        forward_edges = list(filter(([]).__ne__, forward_edges))
        back_edges = list(filter(([]).__ne__, back_edges))

        (exist_forward_edges, exist_back_edges) = new_grouping[group]
        exist_forward_edges.extend(forward_edges)
        exist_back_edges.extend(back_edges)
        if len(exist_forward_edges) > 0:
            new_grouping[group] = (exist_forward_edges, exist_back_edges)

    return new_grouping

def reorganize_groups(world, groups, player):
    def get_group_key(group):
        #(std, region, axis, terrain, parallel, count) = group
        new_group = list(group)
        if world.mode[player] != "standard":
            new_group[0] = None
        if world.owShuffle[player] != 'parallel':
            new_group[4] = None
        if not world.owKeepSimilar[player]:
            new_group[5] = None
        return tuple(new_group)

    # predefined shuffle groups get reorganized here
    # this restructures the candidate pool based on the chosen settings
    for grouping in (groups,):
        new_grouping = {}

        for group in grouping.keys():
            new_grouping[get_group_key(group)] = ([], [])
        
        for group in grouping.keys():
            new_group = get_group_key(group)
            (forward_edges, back_edges) = grouping[group]
            if not world.owKeepSimilar[player]:
                forward_edges = [[i] for l in forward_edges for i in l]
                back_edges = [[i] for l in back_edges for i in l]
            (exist_forward_edges, exist_back_edges) = new_grouping[new_group]
            exist_forward_edges.extend(forward_edges)
            exist_back_edges.extend(back_edges)
            new_grouping[new_group] = (exist_forward_edges, exist_back_edges)

        return new_grouping

def adjust_edge_groups(world, trimmed_groups, edges_to_swap, player):
    groups = defaultdict(lambda: ([],[]))
    for (key, group) in trimmed_groups.items():
        (mode, wrld, dir, terrain, parallel, count) = key
        if mode == OpenStd.Standard:
            groups[key] = group
        else:
            if world.owCrossed[player] == 'chaos':
                groups[(mode, None, dir, terrain, parallel, count)][0].extend(group[0])
                groups[(mode, None, dir, terrain, parallel, count)][1].extend(group[1])
            else:
                for i in range(2):
                    for edge_set in group[i]:
                        new_world = int(wrld)
                        if edge_set[0] in edges_to_swap:
                            new_world += 1
                        groups[(mode, WorldType(new_world % 2), dir, terrain, parallel, count)][i].append(edge_set)
    return list(groups.values())

def create_flute_exits(world, player):
    for region in (r for r in world.regions if r.player == player and r.terrain == Terrain.Land and r.name not in ['Zoras Domain', 'Master Sword Meadow', 'Hobo Bridge']):
        if region.type == (RegionType.LightWorld if world.mode != 'inverted' else RegionType.DarkWorld):
            exitname = 'Flute From ' + region.name
            exit = Entrance(region.player, exitname, region)
            exit.spot_type = 'Flute'
            exit.access_rule = lambda state: state.can_flute(player)
            exit.connect(world.get_region('Flute Sky', player))
            region.exits.append(exit)
    world.initialize_regions()

def categorize_world_regions(world, player):
    for type in OWExitTypes:
        for exitname in OWExitTypes[type]:
            world.get_entrance(exitname, player).spot_type = type
    
    mark_light_world_regions(world, player)
    mark_dark_world_regions(world, player)

def update_world_regions(world, player):
    if world.owMixed[player]:
        for name in world.owswaps[player][1]:
            world.get_region(name, player).type = RegionType.DarkWorld
        for name in world.owswaps[player][2]:
            world.get_region(name, player).type = RegionType.LightWorld

def can_reach_smith(world, player):
    from Items import ItemFactory
    from BaseClasses import CollectionState

    invFlag = world.mode[player] == 'inverted'
    
    def explore_region(region_name, region=None):
        nonlocal found
        explored_regions.append(region_name)
        if not found:
            if not region:
                region = world.get_region(region_name, player)
            for exit in region.exits:
                if not found and exit.connected_region is not None:
                    if any(map(lambda i: i.name in ['Ocarina', 'Ocarina (Activated)'], world.precollected_items)) and exit.spot_type == 'Flute':
                        fluteregion = exit.connected_region
                        for flutespot in fluteregion.exits:
                            if flutespot.connected_region and flutespot.connected_region.name not in explored_regions:
                                explore_region(flutespot.connected_region.name, flutespot.connected_region)
                    elif exit.connected_region.name not in explored_regions \
                            and exit.connected_region.type in [RegionType.LightWorld, RegionType.DarkWorld] \
                            and exit.access_rule(blank_state):
                        explore_region(exit.connected_region.name, exit.connected_region)
                    elif exit.name == 'Sanctuary S':
                        sanc_region = exit.connected_region
                        if len(sanc_region.exits) and sanc_region.exits[0].name == 'Sanctuary Exit':
                            explore_region(sanc_region.exits[0].connected_region.name, sanc_region.exits[0].connected_region)
                    elif exit.connected_region.name == 'Blacksmiths Hut' and exit.access_rule(blank_state):
                        found = True
    
    blank_state = CollectionState(world)
    if world.mode[player] == 'standard':
        blank_state.collect(ItemFactory('Zelda Delivered', player), True)
    if world.logic[player] in ['noglitches', 'minorglitches'] and world.get_region('Frog Prison', player).type == (RegionType.DarkWorld if not invFlag else RegionType.LightWorld):
        blank_state.collect(ItemFactory('Titans Mitts', player), True)
    
    found = False
    explored_regions = list()
    if not world.is_bombshop_start(player):
        start_region = 'Links House'
    else:
        start_region = 'Big Bomb Shop'
    explore_region(start_region)
    if not found:
        if not invFlag:
            explore_region('Sanctuary')
        else:
            explore_region('Dark Sanctuary Hint')
    return found

def build_sectors(world, player):
    from Main import copy_world
    from OWEdges import OWTileRegions
    
    # perform accessibility check on duplicate world
    for p in range(1, world.players + 1):
        world.key_logic[p] = {}
    base_world = copy_world(world, True)
    
    # build lists of contiguous regions accessible with full inventory (excl portals/mirror/flute/entrances)
    regions = list(OWTileRegions.copy().keys())
    sectors = list()
    while(len(regions) > 0):
        explored_regions = build_accessible_region_list(base_world, regions[0], player, False, False, False, False)
        regions = [r for r in regions if r not in explored_regions]
        unique_regions = [_ for i in range(len(sectors)) for _ in sectors[i]]
        if (any(r in unique_regions for r in explored_regions)):
            for s in range(len(sectors)):
                if (any(r in sectors[s] for r in explored_regions)):
                    sectors[s] = list(dict.fromkeys(list(sectors[s]) + list(explored_regions)))
                    break
        else:
            sectors.append(explored_regions)
    
    # remove water regions if Flippers not in starting inventory
    if not any(map(lambda i: i.name == 'Flippers', world.precollected_items)):
        for s in range(len(sectors)):
            terrains = list()
            for regionname in sectors[s]:
                region = world.get_region(regionname, player)
                if region.terrain == Terrain.Land:
                    terrains.append(regionname)
            sectors[s] = terrains
    
    # within each group, split into contiguous regions accessible only with starting inventory
    for s in range(len(sectors)):
        regions = list(sectors[s]).copy()
        sectors2 = list()
        while(len(regions) > 0):
            explored_regions = build_accessible_region_list(base_world, regions[0], player, False, False, True, False)
            regions = [r for r in regions if r not in explored_regions]
            unique_regions = [_ for i in range(len(sectors2)) for _ in sectors2[i]]
            if (any(r in unique_regions for r in explored_regions)):
                for s2 in range(len(sectors2)):
                    if (any(r in sectors2[s2] for r in explored_regions)):
                        sectors2[s2] = list(dict.fromkeys(sectors2[s2] + explored_regions))
                        break
            else:
                sectors2.append(explored_regions)
        sectors[s] = sectors2

    return sectors

def build_accessible_region_list(world, start_region, player, build_copy_world=False, cross_world=False, region_rules=True, ignore_ledges = False):
    from Main import copy_world
    from BaseClasses import CollectionState
    from Items import ItemFactory
    from Utils import stack_size3a
    
    def explore_region(region_name, region=None):
        if stack_size3a() > 500:
            raise GenerationException(f'Infinite loop detected for "{start_region}" located at \'build_accessible_region_list\'')

        explored_regions.append(region_name)
        if not region:
            region = base_world.get_region(region_name, player)
        for exit in region.exits:
            if exit.connected_region is not None:
                if any(map(lambda i: i.name in ['Ocarina', 'Ocarina (Activated)'], base_world.precollected_items)) and exit.spot_type == 'Flute':
                    fluteregion = exit.connected_region
                    for flutespot in fluteregion.exits:
                        if flutespot.connected_region and flutespot.connected_region.name not in explored_regions:
                            explore_region(flutespot.connected_region.name, flutespot.connected_region)
                elif exit.connected_region.name not in explored_regions \
                        and (exit.connected_region.type == region.type 
                            or exit.name in OWExitTypes['OWEdge'] or (cross_world and exit.name in (OWExitTypes['Portal'] + OWExitTypes['Mirror']))) \
                        and (not region_rules or exit.access_rule(blank_state)) and (not ignore_ledges or exit.name not in OWExitTypes['Ledge']):
                    explore_region(exit.connected_region.name, exit.connected_region)
    
    if build_copy_world:
        for p in range(1, world.players + 1):
            world.key_logic[p] = {}
        base_world = copy_world(world, True)
        base_world.override_bomb_check = True
    else:
        base_world = world
    
    connect_simple(base_world, 'Links House S&Q', start_region, player)
    blank_state = CollectionState(base_world)
    if base_world.mode[player] == 'standard':
        blank_state.collect(ItemFactory('Zelda Delivered', player), True)
    explored_regions = list()
    explore_region(start_region)

    return explored_regions

def validate_layout(world, player):
    if world.accessibility[player] == 'none':
        return True
    
    entrance_connectors = {
        'East Death Mountain (Bottom)':       ['East Death Mountain (Top East)'],
        'Kakariko Suburb Area':               ['Maze Race Ledge'],
        'Maze Race Ledge':                    ['Kakariko Suburb Area'],
        'Desert Area':                        ['Desert Ledge', 'Desert Palace Mouth'],
        'East Dark Death Mountain (Top)':     ['Dark Death Mountain Floating Island'],
        'East Dark Death Mountain (Bottom)':  ['East Dark Death Mountain (Top)'],
        'Turtle Rock Area':                   ['Dark Death Mountain Ledge',
                                               'Dark Death Mountain Isolated Ledge'],
        'Dark Death Mountain Ledge':          ['Turtle Rock Area'],
        'Dark Death Mountain Isolated Ledge': ['Turtle Rock Area']
    }
    sane_connectors = {
        # guaranteed dungeon access
        'Skull Woods Forest':                 ['Skull Woods Forest (West)'],
        'Skull Woods Forest (West)':          ['Skull Woods Forest'],
        # guaranteed dropdown access
        'Graveyard Area':                     ['Sanctuary Area'],
        'Pyramid Area':                       ['Pyramid Exit Ledge']
    }

    if not world.is_tile_swapped(0x0a, player):
        if not world.is_tile_swapped(0x03, player):
            entrance_connectors['Mountain Entry Entrance'] = ['West Death Mountain (Bottom)']
            entrance_connectors['Mountain Entry Ledge'] = ['West Death Mountain (Bottom)']
            entrance_connectors['West Death Mountain (Bottom)'] = ['Mountain Entry Ledge']
        else:
            entrance_connectors['Mountain Entry Entrance'] = ['West Dark Death Mountain (Bottom)']
        entrance_connectors['Bumper Cave Entrance'] = ['Bumper Cave Ledge']
    else:
        if not world.is_tile_swapped(0x03, player):
            entrance_connectors['Bumper Cave Entrance'] = ['West Death Mountain (Bottom)']
            entrance_connectors['Bumper Cave Ledge'] = ['West Death Mountain (Bottom)']
            entrance_connectors['West Death Mountain (Bottom)'] = ['Bumper Cave Ledge']
        else:
            entrance_connectors['Bumper Cave Entrance'] = ['West Dark Death Mountain (Bottom)']
        entrance_connectors['Mountain Entry Entrance'] = ['Mountain Entry Ledge']
    
    from Main import copy_world
    from Utils import stack_size3a
    from EntranceShuffle import default_dungeon_connections, default_connector_connections, default_item_connections, default_shop_connections, default_drop_connections, default_dropexit_connections
    
    dungeon_entrances = list(zip(*default_dungeon_connections + [('Ganons Tower', '')]))[0]
    connector_entrances = list(zip(*default_connector_connections))[0]
    item_entrances = list(zip(*default_item_connections))[0]
    shop_entrances = list(zip(*default_shop_connections))[0]
    drop_entrances = list(zip(*default_drop_connections + default_dropexit_connections))[0]
    
    def explore_region(region_name, region=None):
        if stack_size3a() > 500:
            raise GenerationException(f'Infinite loop detected for "{region_name}" located at \'validate_layout\'')

        explored_regions.append(region_name)
        if not region:
            region = base_world.get_region(region_name, player)
        for exit in region.exits:
            if exit.connected_region is not None and exit.connected_region.name not in explored_regions \
                    and exit.connected_region.type in [RegionType.LightWorld, RegionType.DarkWorld]:
                explore_region(exit.connected_region.name, exit.connected_region)
        if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull', 'simple'] \
                and region_name in entrance_connectors:
            for dest_region in entrance_connectors[region_name]:
                if dest_region not in explored_regions:
                    explore_region(dest_region)
        if world.shuffle[player] not in ['insanity'] and region_name in sane_connectors:
            for dest_region in sane_connectors[region_name]:
                if dest_region not in explored_regions:
                    explore_region(dest_region)
    
    for p in range(1, world.players + 1):
        world.key_logic[p] = {}
    base_world = copy_world(world, True)
    explored_regions = list()

    if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull'] or not world.shufflelinks[player]:
        if not world.is_bombshop_start(player):
            start_region = 'Links House Area'
        else:
            start_region = 'Big Bomb Shop Area'
        explore_region(start_region)

    if world.shuffle[player] in ['vanilla', 'dungeonssimple', 'dungeonsfull', 'lite', 'lean'] and world.mode == 'inverted':
        start_region = 'Dark Chapel Area'
        explore_region(start_region)

    if not world.is_tile_swapped(0x30, player):
        start_region = 'Desert Palace Teleporter Ledge'
    else:
        start_region = 'Misery Mire Teleporter Ledge'
    explore_region(start_region)
    
    if not world.is_tile_swapped(0x1b, player):
        start_region = 'Pyramid Area'
    else:
        start_region = 'Hyrule Castle Ledge'
    explore_region(start_region)

    unreachable_regions = OrderedDict()
    unreachable_count = -1
    while unreachable_count != len(unreachable_regions):
        # find unreachable regions
        unreachable_regions = {}
        for region_name in list(OWTileRegions.copy().keys()):
            if region_name not in explored_regions and region_name not in isolated_regions:
                region = base_world.get_region(region_name, player)
                unreachable_regions[region_name] = region
        
        # loop thru unreachable regions to check if some can be excluded
        unreachable_count = len(unreachable_regions)
        for region_name in reversed(unreachable_regions):
            # check if can be accessed flute
            if unreachable_regions[region_name].type == RegionType.LightWorld:
                owid = OWTileRegions[region_name]
                if owid < 0x80 and any(f[1] == owid and region_name in f[0] for f in flute_data.values()):
                    if world.owFluteShuffle[player] != 'vanilla' or owid % 0x40 in [0x03, 0x16, 0x18, 0x2c, 0x2f, 0x3b, 0x3f]:
                        unreachable_regions.pop(region_name)
                        explore_region(region_name)
                        break
            # check if entrances in region could be used to access region
            if world.shuffle[player] != 'vanilla':
                for entrance in [e for e in unreachable_regions[region_name].exits if e.spot_type == 'Entrance']:
                    if (entrance.name == 'Links House' and (world.mode == 'inverted' or not world.shufflelinks[player] or world.shuffle[player] in ['dungeonssimple', 'dungeonsfull', 'lite', 'lean'])) \
                            or (entrance.name == 'Big Bomb Shop' and (world.mode != 'inverted' or not world.shufflelinks[player] or world.shuffle[player] in ['dungeonssimple', 'dungeonsfull', 'lite', 'lean'])) \
                            or (entrance.name == 'Ganons Tower' and (world.mode != 'inverted' and not world.shuffle_ganon[player])) \
                            or (entrance.name in ['Skull Woods First Section Door', 'Skull Woods Second Section Door (East)', 'Skull Woods Second Section Door (West)'] and world.shuffle[player] not in ['insanity']) \
                            or entrance.name == 'Tavern North':
                        continue # these are fixed entrances and cannot be used for gaining access to region
                    if entrance.name not in drop_entrances \
                            and ((entrance.name in dungeon_entrances and world.shuffle[player] not in ['dungeonssimple', 'simple', 'restricted']) \
                                or (entrance.name in connector_entrances and world.shuffle[player] not in ['dungeonssimple', 'dungeonsfull', 'simple']) \
                                or (entrance.name in item_entrances + (tuple() if world.shopsanity[player] else shop_entrances) and world.shuffle[player] not in ['dungeonssimple', 'dungeonsfull', 'lite', 'lean'])):
                        unreachable_regions.pop(region_name)
                        explore_region(region_name)
                        break
                if unreachable_count != len(unreachable_regions):
                    break
    
    if len(unreachable_regions):
        return False
    
    return True
    
test_connections = [
                    #('Links House ES', 'Octoballoon WS'),
                    #('Links House NE', 'Lost Woods Pass SW')
                    ]

# these are connections that cannot be shuffled and always exist. They link together separate parts of the world we need to divide into regions
mandatory_connections = [# Intra-tile OW Connections
                         ('Lost Woods Bush (West)', 'Lost Woods East Area'), #pearl
                         ('Lost Woods Bush (East)', 'Lost Woods West Area'), #pearl
                         ('West Death Mountain Drop', 'West Death Mountain (Bottom)'),
                         ('Spectacle Rock Drop', 'West Death Mountain (Top)'),
                         ('DM Hammer Bridge (West)', 'East Death Mountain (Top East)'), #hammer
                         ('DM Hammer Bridge (East)', 'East Death Mountain (Top West)'), #hammer
                         ('East Death Mountain Spiral Ledge Drop', 'Spiral Cave Ledge'),
                         ('Spiral Ledge Drop', 'East Death Mountain (Bottom)'),
                         ('East Death Mountain Fairy Ledge Drop', 'Fairy Ascension Ledge'),
                         ('Fairy Ascension Ledge Drop', 'Fairy Ascension Plateau'),
                         ('Fairy Ascension Plateau Ledge Drop', 'East Death Mountain (Bottom)'),
                         ('Fairy Ascension Rocks (North)', 'East Death Mountain (Bottom)'), #mitts
                         ('Fairy Ascension Rocks (South)', 'Fairy Ascension Plateau'), #mitts
                         ('DM Broken Bridge (West)', 'East Death Mountain (Bottom)'), #hookshot
                         ('DM Broken Bridge (East)', 'East Death Mountain (Bottom Left)'), #hookshot
                         ('TR Pegs Ledge Entry', 'Death Mountain TR Pegs Ledge'), #mitts
                         ('TR Pegs Ledge Leave', 'Death Mountain TR Pegs'), #mitts
                         ('TR Pegs Ledge Drop', 'Death Mountain TR Pegs'),
                         ('Mountain Entry Entrance Rock (West)', 'Mountain Entry Entrance'), #glove
                         ('Mountain Entry Entrance Rock (East)', 'Mountain Entry Area'), #glove
                         ('Mountain Entry Entrance Ledge Drop', 'Mountain Entry Area'),
                         ('Mountain Entry Ledge Drop', 'Mountain Entry Area'),
                         ('Zora Waterfall Landing', 'Zora Waterfall Area'),
                         ('Zora Waterfall Water Drop', 'Zora Waterfall Water'), #flippers
                         ('Zora Waterfall Water Entry', 'Zora Waterfall Water'), #flippers
                         ('Zora Waterfall Water Approach', 'Zora Waterfall Entryway'), #flippers
                         ('Lost Woods Pass Hammer (North)', 'Lost Woods Pass Portal Area'), #hammer
                         ('Lost Woods Pass Hammer (South)', 'Lost Woods Pass East Top Area'), #hammer
                         ('Lost Woods Pass Rock (North)', 'Lost Woods Pass East Bottom Area'), #mitts
                         ('Lost Woods Pass Rock (South)', 'Lost Woods Pass Portal Area'), #mitts
                         ('Bonk Rock Ledge Drop', 'Sanctuary Area'),
                         ('Graveyard Ledge Drop', 'Graveyard Area'),
                         ('Kings Grave Outer Rocks', 'Kings Grave Area'), #mitts
                         ('Kings Grave Inner Rocks', 'Graveyard Area'), #mitts
                         ('River Bend Water Drop', 'River Bend Water'), #flippers
                         ('River Bend East Water Drop', 'River Bend Water'), #flippers
                         ('River Bend West Pier', 'River Bend Area'),
                         ('River Bend East Pier', 'River Bend East Bank'),
                         ('Potion Shop Water Drop', 'Potion Shop Water'), #flippers
                         ('Potion Shop Northeast Water Drop', 'Potion Shop Water'), #flippers
                         ('Potion Shop Rock (South)', 'Potion Shop Northeast'), #glove
                         ('Potion Shop Rock (North)', 'Potion Shop Area'), #glove
                         ('Zora Approach Water Drop', 'Zora Approach Water'), #flippers
                         ('Zora Approach Rocks (West)', 'Zora Approach Ledge'), #mitts/boots
                         ('Zora Approach Rocks (East)', 'Zora Approach Area'), #mitts/boots
                         ('Zora Approach Bottom Ledge Drop', 'Zora Approach Ledge'),
                         ('Zora Approach Ledge Drop', 'Zora Approach Area'),
                         ('Kakariko Southwest Bush (North)', 'Kakariko Southwest'), #pearl
                         ('Kakariko Southwest Bush (South)', 'Kakariko Area'), #pearl
                         ('Kakariko Yard Bush (South)', 'Kakariko Grass Yard'), #pearl
                         ('Kakariko Yard Bush (North)', 'Kakariko Area'), #pearl
                         ('Hyrule Castle Southwest Bush (North)', 'Hyrule Castle Southwest'), #pearl
                         ('Hyrule Castle Southwest Bush (South)', 'Hyrule Castle Area'), #pearl
                         ('Hyrule Castle Courtyard Bush (North)', 'Hyrule Castle Courtyard'), #pearl
                         ('Hyrule Castle Courtyard Bush (South)', 'Hyrule Castle Courtyard Northeast'), #pearl
                         ('Hyrule Castle Main Gate (South)', 'Hyrule Castle Courtyard'), #aga+mirror
                         ('Hyrule Castle Main Gate (North)', 'Hyrule Castle Area'), #aga+mirror
                         ('Hyrule Castle Ledge Drop', 'Hyrule Castle Area'),
                         ('Hyrule Castle Ledge Courtyard Drop', 'Hyrule Castle Courtyard'),
                         ('Hyrule Castle Inner East Rock', 'Hyrule Castle East Entry'), #glove
                         ('Hyrule Castle Outer East Rock', 'Hyrule Castle Area'), #glove
                         ('Wooden Bridge Bush (South)', 'Wooden Bridge Northeast'), #pearl
                         ('Wooden Bridge Bush (North)', 'Wooden Bridge Area'), #pearl
                         ('Wooden Bridge Water Drop', 'Wooden Bridge Water'), #flippers
                         ('Wooden Bridge Northeast Water Drop', 'Wooden Bridge Water'), #flippers
                         ('Bat Cave Ledge Peg', 'Bat Cave Ledge'), #hammer
                         ('Bat Cave Ledge Peg (East)', 'Blacksmith Area'), #hammer
                         ('Maze Race Game', 'Maze Race Prize'), #pearl
                         ('Maze Race Ledge Drop', 'Maze Race Area'),
                         ('Desert Palace Statue Move', 'Desert Palace Stairs'), #book
                         ('Desert Ledge Drop', 'Desert Area'),
                         ('Desert Ledge Outer Rocks', 'Desert Palace Entrance (North) Spot'), #glove
                         ('Desert Ledge Inner Rocks', 'Desert Ledge'), #glove
                         ('Checkerboard Ledge Drop', 'Desert Area'),
                         ('Desert Mouth Drop', 'Desert Area'),
                         ('Desert Teleporter Drop', 'Desert Area'),
                         ('Bombos Tablet Drop', 'Desert Area'),
                         ('Flute Boy Bush (North)', 'Flute Boy Approach Area'), #pearl
                         ('Flute Boy Bush (South)', 'Flute Boy Bush Entry'), #pearl
                         ('Cave 45 Ledge Drop', 'Flute Boy Approach Area'),
                         ('C Whirlpool Water Entry', 'C Whirlpool Water'), #flippers
                         ('C Whirlpool Landing', 'C Whirlpool Area'),
                         ('C Whirlpool Rock (Bottom)', 'C Whirlpool Outer Area'), #glove
                         ('C Whirlpool Rock (Top)', 'C Whirlpool Area'), #glove
                         ('Statues Water Entry', 'Statues Water'), #flippers
                         ('Statues Landing', 'Statues Area'),
                         ('Lake Hylia Water Drop', 'Lake Hylia Water'), #flippers
                         ('Lake Hylia South Water Drop', 'Lake Hylia Water'), #flippers
                         ('Lake Hylia Northeast Water Drop', 'Lake Hylia Water'), #flippers
                         ('Lake Hylia Central Water Drop', 'Lake Hylia Water'), #flippers
                         ('Lake Hylia Island Water Drop', 'Lake Hylia Water'), #flippers
                         ('Lake Hylia Central Island Pier', 'Lake Hylia Central Island'),
                         ('Lake Hylia West Pier', 'Lake Hylia Area'),
                         ('Lake Hylia East Pier', 'Lake Hylia Northeast Bank'),
                         ('Lake Hylia Water D Approach', 'Lake Hylia Water D'),
                         ('Lake Hylia Water D Leave', 'Lake Hylia Water'), #flippers
                         ('Desert Pass Ledge Drop', 'Desert Pass Area'),
                         ('Desert Pass Rocks (North)', 'Desert Pass Southeast'), #glove
                         ('Desert Pass Rocks (South)', 'Desert Pass Area'), #glove
                         ('Middle Aged Man', 'Middle Aged Man'),
                         ('Octoballoon Water Drop', 'Octoballoon Water'), #flippers
                         ('Octoballoon Waterfall Water Drop', 'Octoballoon Water'), #flippers
                         ('Octoballoon Pier', 'Octoballoon Area'),

                         ('Skull Woods Bush Rock (West)', 'Skull Woods Forest'), #glove
                         ('Skull Woods Bush Rock (East)', 'Skull Woods Portal Entry'), #glove
                         ('Skull Woods Forgotten Bush (West)', 'Skull Woods Forgotten Path (Northeast)'), #pearl
                         ('Skull Woods Forgotten Bush (East)', 'Skull Woods Forgotten Path (Southwest)'), #pearl
                         ('Dark Death Mountain Drop (West)', 'West Dark Death Mountain (Bottom)'),
                         ('GT Entry Approach', 'GT Approach'),
                         ('GT Entry Leave', 'West Dark Death Mountain (Top)'),
                         ('Floating Island Drop', 'East Dark Death Mountain (Top)'),
                         ('Dark Death Mountain Drop (East)', 'East Dark Death Mountain (Bottom)'),
                         ('Turtle Rock Ledge Drop', 'Turtle Rock Area'),
                         ('Bumper Cave Entrance Rock', 'Bumper Cave Entrance'), #glove
                         ('Bumper Cave Ledge Drop', 'Bumper Cave Area'),
                         ('Bumper Cave Entrance Drop', 'Bumper Cave Area'),
                         ('Skull Woods Pass Bush Row (West)', 'Skull Woods Pass East Top Area'), #pearl
                         ('Skull Woods Pass Bush Row (East)', 'Skull Woods Pass West Area'), #pearl
                         ('Skull Woods Pass Bush (North)', 'Skull Woods Pass Portal Area'), #pearl
                         ('Skull Woods Pass Bush (South)', 'Skull Woods Pass East Top Area'), #pearl
                         ('Skull Woods Pass Rock (North)', 'Skull Woods Pass East Bottom Area'), #mitts
                         ('Skull Woods Pass Rock (South)', 'Skull Woods Pass Portal Area'), #mitts
                         ('Dark Graveyard Bush (South)', 'Dark Graveyard North'), #pearl
                         ('Dark Graveyard Bush (North)', 'Dark Graveyard Area'), #pearl
                         ('Qirn Jump Water Drop', 'Qirn Jump Water'), #flippers
                         ('Qirn Jump East Water Drop', 'Qirn Jump Water'), #flippers
                         ('Qirn Jump Pier', 'Qirn Jump East Bank'),
                         ('Dark Witch Water Drop', 'Dark Witch Water'), #flippers
                         ('Dark Witch Northeast Water Drop', 'Dark Witch Water'), #flippers
                         ('Dark Witch Rock (North)', 'Dark Witch Area'), #glove
                         ('Dark Witch Rock (South)', 'Dark Witch Northeast'), #glove
                         ('Catfish Approach Rocks (West)', 'Catfish Approach Ledge'), #mitts/boots
                         ('Catfish Approach Rocks (East)', 'Catfish Approach Area'), #mitts/boots
                         ('Catfish Approach Bottom Ledge Drop', 'Catfish Approach Ledge'),
                         ('Catfish Approach Ledge Drop', 'Catfish Approach Area'),
                         ('Catfish Approach Water Drop', 'Catfish Approach Water'), #flippers
                         ('Village of Outcasts Pegs', 'Dark Grassy Lawn'), #hammer
                         ('Grassy Lawn Pegs', 'Village of Outcasts Area'), #hammer
                         ('Shield Shop Fence (Outer) Ledge Drop', 'Shield Shop Fence'),
                         ('Shield Shop Fence (Inner) Ledge Drop', 'Shield Shop Area'),
                         ('Pyramid Exit Ledge Drop', 'Pyramid Area'),
                         ('Pyramid Crack', 'Pyramid Crack'),
                         ('Broken Bridge Hammer Rock (South)', 'Broken Bridge Northeast'), #hammer/glove
                         ('Broken Bridge Hammer Rock (North)', 'Broken Bridge Area'), #hammer/glove
                         ('Broken Bridge Hookshot Gap', 'Broken Bridge West'), #hookshot
                         ('Broken Bridge Water Drop', 'Broken Bridge Water'), #flippers
                         ('Broken Bridge Northeast Water Drop', 'Broken Bridge Water'), #flippers
                         ('Broken Bridge West Water Drop', 'Broken Bridge Water'), #flippers
                         ('Peg Area Rocks (West)', 'Hammer Pegs Area'), #mitts
                         ('Peg Area Rocks (East)', 'Hammer Pegs Entry'), #mitts
                         ('Dig Game To Ledge Drop', 'Dig Game Ledge'), #mitts
                         ('Dig Game Ledge Drop', 'Dig Game Area'),
                         ('Frog Ledge Drop', 'Archery Game Area'),
                         ('Frog Rock (Inner)', 'Frog Area'), #mitts
                         ('Frog Rock (Outer)', 'Frog Prison'), #mitts
                         ('Archery Game Rock (North)', 'Archery Game Area'), #mitts
                         ('Archery Game Rock (South)', 'Frog Area'), #mitts
                         ('Hammer Bridge Pegs (North)', 'Hammer Bridge South Area'), #hammer
                         ('Hammer Bridge Pegs (South)', 'Hammer Bridge North Area'), #hammer
                         ('Hammer Bridge Water Drop', 'Hammer Bridge Water'), #flippers
                         ('Hammer Bridge Pier', 'Hammer Bridge North Area'),
                         ('Misery Mire Teleporter Ledge Drop', 'Misery Mire Area'),
                         ('Stumpy Approach Bush (North)', 'Stumpy Approach Area'), #pearl
                         ('Stumpy Approach Bush (South)', 'Stumpy Approach Bush Entry'), #pearl
                         ('Dark C Whirlpool Water Entry', 'Dark C Whirlpool Water'), #flippers
                         ('Dark C Whirlpool Landing', 'Dark C Whirlpool Area'),
                         ('Dark C Whirlpool Rock (Bottom)', 'Dark C Whirlpool Outer Area'), #glove
                         ('Dark C Whirlpool Rock (Top)', 'Dark C Whirlpool Area'), #glove
                         ('Hype Cave Water Entry', 'Hype Cave Water'), #flippers
                         ('Hype Cave Landing', 'Hype Cave Area'),
                         ('Ice Lake Water Drop', 'Ice Lake Water'), #flippers
                         ('Ice Lake Northeast Water Drop', 'Ice Lake Water'), #flippers
                         ('Ice Lake Southwest Water Drop', 'Ice Lake Water'), #flippers
                         ('Ice Lake Southeast Water Drop', 'Ice Lake Water'), #flippers
                         ('Ice Lake Moat Water Entry', 'Ice Lake Water'), #flippers
                         ('Ice Lake Northeast Pier', 'Ice Lake Northeast Bank'),
                         ('Bomber Corner Water Drop', 'Bomber Corner Water'), #flippers
                         ('Bomber Corner Waterfall Water Drop', 'Bomber Corner Water'), #flippers
                         ('Bomber Corner Pier', 'Bomber Corner Area'),

                         # OWG Connections
                         ('Sand Dunes Ledge Drop', 'Sand Dunes Area'),
                         ('Stone Bridge East Ledge Drop', 'Stone Bridge Area'),
                         ('Tree Line Ledge Drop', 'Tree Line Area'),
                         ('Eastern Palace Ledge Drop', 'Eastern Palace Area'),
                         
                         ('Links House Cliff Ledge Drop', 'Links House Area'),
                         ('Central Bonk Rocks Cliff Ledge Drop', 'Central Bonk Rocks Area'),
                         ('Stone Bridge Cliff Ledge Drop', 'Stone Bridge Area'),
                         ('Lake Hylia Area Cliff Ledge Drop', 'Lake Hylia Area'),
                         ('C Whirlpool Cliff Ledge Drop', 'C Whirlpool Area'),
                         ('C Whirlpool Outer Cliff Ledge Drop', 'C Whirlpool Outer Area'),
                         ('South Teleporter Cliff Ledge Drop', 'Dark Central Cliffs'),
                         ('Statues Cliff Ledge Drop', 'Statues Area'),
                         ('Lake Hylia Island FAWT Ledge Drop', 'Lake Hylia Island'),
                         ('Stone Bridge EC Cliff Water Drop', 'Stone Bridge Water'), #fake flipper
                         ('Tree Line WC Cliff Water Drop', 'Tree Line Water'), #fake flipper
                         
                         ('Desert Boss Cliff Ledge Drop', 'Desert Palace Entrance (North) Spot'),
                         ('Checkerboard Cliff Ledge Drop', 'Desert Checkerboard Ledge'),
                         ('Suburb Cliff Ledge Drop', 'Kakariko Suburb Area'),
                         ('Cave 45 Cliff Ledge Drop', 'Cave 45 Ledge'),
                         ('Desert Pass Cliff Ledge Drop', 'Desert Pass Area'),
                         ('Desert Pass Southeast Cliff Ledge Drop', 'Desert Pass Southeast'),
                         ('Desert C Whirlpool Cliff Ledge Drop', 'C Whirlpool Outer Area'),
                         ('Dam Cliff Ledge Drop', 'Dam Area'),

                         ('Dark Dunes Ledge Drop', 'Dark Dunes Area'),
                         ('Hammer Bridge North Ledge Drop', 'Hammer Bridge North Area'),
                         ('Dark Tree Line Ledge Drop', 'Dark Tree Line Area'),
                         ('Palace of Darkness Ledge Drop', 'Palace of Darkness Area'),

                         ('Mire Cliff Ledge Drop', 'Misery Mire Area'),
                         ('Archery Game Cliff Ledge Drop', 'Archery Game Area'),
                         ('Stumpy Approach Cliff Ledge Drop', 'Stumpy Approach Area'),
                         ('Swamp Nook Cliff Ledge Drop', 'Swamp Nook Area'),
                         ('Mire C Whirlpool Cliff Ledge Drop', 'Dark C Whirlpool Outer Area'),
                         ('Swamp Cliff Ledge Drop', 'Swamp Area'),

                         ('Bomb Shop Cliff Ledge Drop', 'Big Bomb Shop Area'),
                         ('Dark Bonk Rocks Cliff Ledge Drop', 'Dark Bonk Rocks Area'),
                         ('Hammer Bridge South Cliff Ledge Drop', 'Hammer Bridge South Area'),
                         ('Ice Lake Area Cliff Ledge Drop', 'Ice Lake Area'),
                         ('Ice Lake Northeast Pier Hop', 'Ice Lake Northeast Bank'),
                         ('Ice Lake Moat Bomb Jump', 'Ice Lake Moat'),
                         ('Dark C Whirlpool Cliff Ledge Drop', 'Dark C Whirlpool Area'),
                         ('Dark C Whirlpool Outer Cliff Ledge Drop', 'Dark C Whirlpool Outer Area'),
                         ('Hype Cliff Ledge Drop', 'Hype Cave Area'),
                         ('Ice Palace Island FAWT Ledge Drop', 'Ice Lake Moat'),
                         ('Hammer Bridge EC Cliff Water Drop', 'Hammer Bridge Water'), #fake flipper
                         ('Dark Tree Line WC Cliff Water Drop', 'Dark Tree Line Water') #fake flipper
                         ]

default_whirlpool_connections = [
    ((0x33, 'C Whirlpool', 'C Whirlpool Water'),              (0x15, 'River Bend Whirlpool', 'River Bend Water')),
    ((0x35, 'Lake Hylia Whirlpool', 'Lake Hylia Water'),      (0x0f, 'Zora Whirlpool', 'Zora Waterfall Water')),
    ((0x12, 'Kakariko Pond Whirlpool', 'Kakariko Pond Area'), (0x3f, 'Octoballoon Whirlpool', 'Octoballoon Water')),
    ((0x55, 'Qirn Jump Whirlpool', 'Qirn Jump Water'),        (0x7f, 'Bomber Corner Whirlpool', 'Bomber Corner Water'))
]                         

default_flute_connections = [
    0x0b, 0x16, 0x18, 0x2c, 0x2f, 0x38, 0x3b, 0x3f
]
                         
ow_connections = {
    0x00: ([
            ('Lost Woods East Mirror Spot', 'Lost Woods East Area'),
            ('Lost Woods Entry Mirror Spot', 'Lost Woods West Area'),
            ('Lost Woods Pedestal Mirror Spot', 'Lost Woods West Area'),
            ('Lost Woods Southwest Mirror Spot', 'Lost Woods West Area'),
            ('Lost Woods East (Forgotten) Mirror Spot', 'Lost Woods East Area'),
            ('Lost Woods West (Forgotten) Mirror Spot', 'Lost Woods West Area')
        ], [
            ('Skull Woods Back Mirror Spot', 'Skull Woods Forest (West)'),
            ('Skull Woods Forgotten (West) Mirror Spot', 'Skull Woods Forgotten Path (Southwest)'),
            ('Skull Woods Forgotten (East) Mirror Spot', 'Skull Woods Forgotten Path (Northeast)'),
            ('Skull Woods Portal Entry Mirror Spot', 'Skull Woods Portal Entry'),
            ('Skull Woods Forgotten (Middle) Mirror Spot', 'Skull Woods Forgotten Path (Northeast)'),
            ('Skull Woods Front Mirror Spot', 'Skull Woods Forest')
        ]),
    0x02: ([
            ('Lumberjack Mirror Spot', 'Lumberjack Area')
        ], [
            ('Dark Lumberjack Mirror Spot', 'Dark Lumberjack Area')
        ]),
    0x03: ([
            ('Spectacle Rock Mirror Spot', 'Spectacle Rock Ledge'),
            ('West Death Mountain (Top) Mirror Spot', 'West Death Mountain (Top)'),
            ('West Death Mountain Teleporter', 'West Dark Death Mountain (Bottom)')
        ], [
            ('Spectacle Rock Leave', 'West Death Mountain (Top)'),
            ('Spectacle Rock Approach', 'Spectacle Rock Ledge'),
            ('West Dark Death Mountain (Top) Mirror Spot', 'West Dark Death Mountain (Top)'),
            ('Bubble Boy Mirror Spot', 'West Dark Death Mountain (Bottom)'),
            ('West Dark Death Mountain (Bottom) Mirror Spot', 'West Dark Death Mountain (Bottom)'),
            ('Dark Death Mountain Teleporter (West)', 'West Death Mountain (Bottom)')
        ]),
    0x05: ([
            ('East Death Mountain (Top West) Mirror Spot', 'East Death Mountain (Top West)'),
            ('East Death Mountain (Top East) Mirror Spot', 'East Death Mountain (Top East)'),
            ('Spiral Cave Mirror Spot', 'Spiral Cave Ledge'),
            ('Mimic Cave Mirror Spot', 'Mimic Cave Ledge'),
            ('Isolated Ledge Mirror Spot', 'Fairy Ascension Ledge'),
            ('Fairy Ascension Mirror Spot', 'Fairy Ascension Plateau'),
            ('Death Mountain Bridge Mirror Spot', 'East Death Mountain (Bottom Left)'),
            ('Floating Island Mirror Spot', 'Death Mountain Floating Island'),
            ('East Death Mountain Teleporter', 'East Dark Death Mountain (Bottom)')
        ], [
            ('Floating Island Bridge (West)', 'East Death Mountain (Top East)'),
            ('Floating Island Bridge (East)', 'Death Mountain Floating Island'),
            ('East Death Mountain Mimic Ledge Drop', 'Mimic Cave Ledge'),
            ('Mimic Ledge Drop', 'East Death Mountain (Bottom)'),
            ('Spiral Mimic Bridge (West)', 'Spiral Mimic Ledge Extend'),
            ('Spiral Mimic Bridge (East)', 'Spiral Mimic Ledge Extend'),
            ('Spiral Ledge Approach', 'Spiral Cave Ledge'),
            ('Mimic Ledge Approach', 'Mimic Cave Ledge'),
            ('Spiral Mimic Ledge Drop', 'Fairy Ascension Ledge'),
            ('East Dark Death Mountain (Top West) Mirror Spot', 'East Dark Death Mountain (Top)'),
            ('East Dark Death Mountain (Top East) Mirror Spot', 'East Dark Death Mountain (Top)'),
            ('TR Ledge (West) Mirror Spot', 'Dark Death Mountain Ledge'),
            ('TR Ledge (East) Mirror Spot', 'Dark Death Mountain Ledge'),
            ('TR Isolated Mirror Spot', 'Dark Death Mountain Isolated Ledge'),
            ('East Dark Death Mountain (Bottom Plateau) Mirror Spot', 'East Dark Death Mountain (Bottom)'),
            ('East Dark Death Mountain (Bottom Left) Mirror Spot', 'East Dark Death Mountain (Bottom Left)'),
            ('East Dark Death Mountain (Bottom) Mirror Spot', 'East Dark Death Mountain (Bottom)'),
            ('Dark Floating Island Mirror Spot', 'Dark Death Mountain Floating Island'),
            ('Dark Death Mountain Teleporter (East)', 'East Death Mountain (Bottom)')
        ]),
    0x07: ([
            ('TR Pegs Area Mirror Spot', 'Death Mountain TR Pegs'),
            ('TR Pegs Teleporter', 'Turtle Rock Ledge')
        ], [
            ('Turtle Rock Tail Ledge Drop', 'Turtle Rock Ledge'),
            ('Turtle Rock Mirror Spot', 'Turtle Rock Area'),
            ('Turtle Rock Ledge Mirror Spot', 'Turtle Rock Ledge'),
            ('Turtle Rock Teleporter', 'Death Mountain TR Pegs Ledge')
        ]),
    0x0a: ([
            ('Mountain Entry Mirror Spot', 'Mountain Entry Area'),
            ('Mountain Entry Entrance Mirror Spot', 'Mountain Entry Entrance'),
            ('Mountain Entry Ledge Mirror Spot', 'Mountain Entry Ledge')
        ], [
            ('Bumper Cave Area Mirror Spot', 'Bumper Cave Area'),
            ('Bumper Cave Entry Mirror Spot', 'Bumper Cave Entrance'),
            ('Bumper Cave Ledge Mirror Spot', 'Bumper Cave Ledge')
        ]),
    0x0f: ([
            ('Zora Waterfall Mirror Spot', 'Zora Waterfall Area')
        ], [
            ('Catfish Mirror Spot', 'Catfish Area')
        ]),
    0x10: ([
            ('Lost Woods Pass West Mirror Spot', 'Lost Woods Pass West Area'),
            ('Lost Woods Pass East Top Mirror Spot', 'Lost Woods Pass East Top Area'),
            ('Lost Woods Pass Portal Mirror Spot', 'Lost Woods Pass Portal Area'),
            ('Lost Woods Pass East Bottom Mirror Spot', 'Lost Woods Pass East Bottom Area'),
            ('Kakariko Teleporter', 'Skull Woods Pass Portal Area')
        ], [
            ('Skull Woods Pass West Mirror Spot', 'Skull Woods Pass West Area'),
            ('Skull Woods Pass East Top Mirror Spot', 'Skull Woods Pass East Top Area'),
            ('Skull Woods Pass Portal Mirror Spot', 'Skull Woods Pass Portal Area'),
            ('Skull Woods Pass East Bottom Mirror Spot', 'Skull Woods Pass East Bottom Area'),
            ('West Dark World Teleporter', 'Lost Woods Pass Portal Area')
        ]),
    0x11: ([
            ('Kakariko Fortune Mirror Spot', 'Kakariko Fortune Area')
        ], [
            ('Outcast Fortune Mirror Spot', 'Dark Fortune Area')
        ]),
    0x12: ([
            ('Kakariko Pond Mirror Spot', 'Kakariko Pond Area')
        ], [
            ('Outcast Pond Mirror Spot', 'Outcast Pond Area')
        ]),
    0x13: ([
            ('Sanctuary Mirror Spot', 'Sanctuary Area'),
            ('Bonk Rock Ledge Mirror Spot', 'Bonk Rock Ledge')
        ], [
            ('Dark Chapel Mirror Spot', 'Dark Chapel Area'),
            ('Dark Chapel Ledge Mirror Spot', 'Dark Chapel Area')
        ]),
    0x14: ([
            ('Graveyard Ledge Mirror Spot', 'Graveyard Ledge'),
            ('Kings Grave Mirror Spot', 'Kings Grave Area')
        ], [
            ('Graveyard Ladder (Top)', 'Graveyard Area'),
            ('Graveyard Ladder (Bottom)', 'Graveyard Ledge'),
            ('Dark Graveyard Mirror Spot', 'Dark Graveyard Area'),
            ('Dark Graveyard Ledge Mirror Spot', 'Dark Graveyard Area'),
            ('Dark Graveyard Grave Mirror Spot', 'Dark Graveyard Area')
        ]),
    0x15: ([
            ('River Bend Mirror Spot', 'River Bend Area'),
            ('River Bend East Mirror Spot', 'River Bend East Bank')
        ], [
            ('Qirn Jump Mirror Spot', 'Qirn Jump Area'),
            ('Qirn Jump East Mirror Spot', 'Qirn Jump East Bank')
        ]),
    0x16: ([
            ('Potion Shop Mirror Spot', 'Potion Shop Area'),
            ('Potion Shop Northeast Mirror Spot', 'Potion Shop Northeast')
        ], [
            ('Dark Witch Mirror Spot', 'Dark Witch Area'),
            ('Dark Witch Northeast Mirror Spot', 'Dark Witch Northeast')
        ]),
    0x17: ([
            ('Zora Approach Mirror Spot', 'Zora Approach Area'),
            ('Zora Approach Ledge Mirror Spot', 'Zora Approach Ledge')
        ], [
            ('Catfish Approach Mirror Spot', 'Catfish Approach Area'),
            ('Catfish Approach Ledge Mirror Spot', 'Catfish Approach Ledge')
        ]),
    0x18: ([
            ('Kakariko Mirror Spot', 'Kakariko Area'),
            ('Kakariko Grass Mirror Spot', 'Kakariko Area')
        ], [
            ('Village of Outcasts Mirror Spot', 'Village of Outcasts Area'),
            ('Village of Outcasts Southwest Mirror Spot', 'Village of Outcasts Area'),
            ('Hammer House Mirror Spot', 'Dark Grassy Lawn')
        ]),
    0x1a: ([
            ('Forgotton Forest Mirror Spot', 'Forgotten Forest Area'),
            ('Forgotton Forest Fence Mirror Spot', 'Forgotten Forest Area')
        ], [
            ('Shield Shop Mirror Spot', 'Shield Shop Area')
        ]),
    0x1b: ([
            ('HC Ledge Mirror Spot', 'Hyrule Castle Ledge'),
            ('HC Courtyard Mirror Spot', 'Hyrule Castle Courtyard'),
            ('HC Area Mirror Spot', 'Hyrule Castle Area'),
            ('HC Courtyard Left Mirror Spot', 'Hyrule Castle Courtyard'),
            ('HC Area South Mirror Spot', 'Hyrule Castle Area'),
            ('HC East Entry Mirror Spot', 'Hyrule Castle East Entry'),
            ('Top of Pyramid', 'Pyramid Area'),
            ('Top of Pyramid (Inner)', 'Pyramid Area')
        ], [
            ('Pyramid Mirror Spot', 'Pyramid Area'),
            ('Pyramid Pass Mirror Spot', 'Pyramid Pass'),
            ('Pyramid Courtyard Mirror Spot', 'Pyramid Area'),
            ('Pyramid Uncle Mirror Spot', 'Pyramid Area'),
            ('Pyramid From Ledge Mirror Spot', 'Pyramid Area'),
            ('Pyramid Entry Mirror Spot', 'Pyramid Area'),
            ('Post Aga Inverted Teleporter', 'Hyrule Castle Area')
        ]),
    0x1d: ([
            ('Wooden Bridge Mirror Spot', 'Wooden Bridge Area'),
            ('Wooden Bridge Northeast Mirror Spot', 'Wooden Bridge Area'),
            ('Wooden Bridge West Mirror Spot', 'Wooden Bridge Area')
        ], [
            ('Broken Bridge West Mirror Spot', 'Broken Bridge West'),
            ('Broken Bridge East Mirror Spot', 'Broken Bridge Area'),
            ('Broken Bridge Northeast Mirror Spot', 'Broken Bridge Northeast')
        ]),
    0x1e: ([
            ('Eastern Palace Mirror Spot', 'Eastern Palace Area')
        ], [
            ('Palace of Darkness Mirror Spot', 'Palace of Darkness Area')
        ]),
    0x22: ([
            ('Blacksmith Mirror Spot', 'Blacksmith Area'),
            ('Blacksmith Entry Mirror Spot', 'Blacksmith Area'),
            ('Bat Cave Ledge Mirror Spot', 'Bat Cave Ledge')
        ], [
            ('Hammer Pegs Mirror Spot', 'Hammer Pegs Area'),
            ('Hammer Pegs Entry Mirror Spot', 'Hammer Pegs Entry')
        ]),
    0x25: ([
            ('Sand Dunes Mirror Spot', 'Sand Dunes Area')
        ], [
            ('Dark Dunes Mirror Spot', 'Dark Dunes Area')
        ]),
    0x28: ([
            ('Maze Race Mirror Spot', 'Maze Race Ledge'),
            ('Maze Race Ledge Mirror Spot', 'Maze Race Ledge')
        ], [
            ('Dig Game Mirror Spot', 'Dig Game Area'),
            ('Dig Game Ledge Mirror Spot', 'Dig Game Ledge')
        ]),
    0x29: ([
            ('Kakariko Suburb Mirror Spot', 'Kakariko Suburb Area'),
            ('Kakariko Suburb South Mirror Spot', 'Kakariko Suburb Area')
        ], [
            ('Frog Mirror Spot', 'Frog Area'),
            ('Frog Prison Mirror Spot', 'Frog Prison'),
            ('Archery Game Mirror Spot', 'Archery Game Area')
        ]),
    0x2a: ([
            ('Flute Boy Mirror Spot', 'Flute Boy Area'),
            ('Flute Boy Pass Mirror Spot', 'Flute Boy Pass')
        ], [
            ('Stumpy Mirror Spot', 'Stumpy Area'),
            ('Stumpy Pass Mirror Spot', 'Stumpy Pass')
        ]),
    0x2b: ([
            ('Central Bonk Rocks Mirror Spot', 'Central Bonk Rocks Area')
        ], [
            ('Dark Bonk Rocks Mirror Spot', 'Dark Bonk Rocks Area')
        ]),
    0x2c: ([
            ('Links House Mirror Spot', 'Links House Area')
        ], [
            ('Big Bomb Shop Mirror Spot', 'Big Bomb Shop Area')
        ]),
    0x2d: ([
            ('Stone Bridge Mirror Spot', 'Stone Bridge Area'),
            ('Stone Bridge South Mirror Spot', 'Stone Bridge Area'),
            ('Hobo Mirror Spot', 'Stone Bridge Water')
        ], [
            ('Hammer Bridge North Mirror Spot', 'Hammer Bridge North Area'),
            ('Hammer Bridge South Mirror Spot', 'Hammer Bridge South Area'),
            ('Dark Hobo Mirror Spot', 'Hammer Bridge Water')
        ]),
    0x2e: ([
            ('Tree Line Mirror Spot', 'Tree Line Area')
        ], [
            ('Dark Tree Line Mirror Spot', 'Dark Tree Line Area')
        ]),
    0x2f: ([
            ('Eastern Nook Mirror Spot', 'Eastern Nook Area'),
            ('East Hyrule Teleporter', 'Palace of Darkness Nook Area')
        ], [
            ('Darkness Nook Mirror Spot', 'Palace of Darkness Nook Area'),
            ('East Dark World Teleporter', 'Eastern Nook Area')
        ]),
    0x30: ([
            ('Desert Mirror Spot', 'Desert Area'),
            ('Desert Ledge Mirror Spot', 'Desert Ledge'),
            ('Checkerboard Mirror Spot', 'Desert Checkerboard Ledge'),
            ('DP Stairs Mirror Spot', 'Desert Palace Stairs'),
            ('DP Entrance (North) Mirror Spot', 'Desert Palace Entrance (North) Spot'),
            ('Bombos Tablet Ledge Mirror Spot', 'Bombos Tablet Ledge'),
            ('Desert Teleporter', 'Misery Mire Teleporter Ledge')
        ], [
            ('Checkerboard Ledge Approach', 'Desert Checkerboard Ledge'),
            ('Checkerboard Ledge Leave', 'Desert Area'),
            ('Misery Mire Mirror Spot', 'Misery Mire Area'),
            ('Misery Mire Ledge Mirror Spot', 'Misery Mire Area'),
            ('Misery Mire Blocked Mirror Spot', 'Misery Mire Area'),
            ('Misery Mire Main Mirror Spot', 'Misery Mire Area'),
            ('Misery Mire Teleporter', 'Desert Palace Teleporter Ledge')
        ]),
    0x32: ([
            ('Flute Boy Entry Mirror Spot', 'Flute Boy Bush Entry'),
            ('Cave 45 Mirror Spot', 'Cave 45 Ledge')
        ], [
            ('Cave 45 Inverted Leave', 'Flute Boy Approach Area'),
            ('Cave 45 Inverted Approach', 'Cave 45 Ledge'),
            ('Stumpy Approach Mirror Spot', 'Stumpy Approach Area'),
            ('Stumpy Bush Entry Mirror Spot', 'Stumpy Approach Bush Entry')
        ]),
    0x33: ([
            ('C Whirlpool Mirror Spot', 'C Whirlpool Area'),
            ('C Whirlpool Outer Mirror Spot', 'C Whirlpool Outer Area'),
            ('South Hyrule Teleporter', 'Dark C Whirlpool Area')
        ], [
            ('Dark C Whirlpool Mirror Spot', 'Dark C Whirlpool Area'),
            ('Dark C Whirlpool Outer Mirror Spot', 'Dark C Whirlpool Outer Area'),
            ('South Dark World Teleporter', 'C Whirlpool Area'),
            ('Dark South Teleporter Cliff Ledge Drop', 'Central Cliffs') #OWG only, needs glove
        ]),
    0x34: ([
            ('Statues Mirror Spot', 'Statues Area')
        ], [
            ('Hype Cave Mirror Spot', 'Hype Cave Area')
        ]),
    0x35: ([
            ('Lake Hylia Mirror Spot', 'Lake Hylia Area'),
            ('Lake Hylia Northeast Mirror Spot', 'Lake Hylia Northeast Bank'),
            ('South Shore Mirror Spot', 'Lake Hylia South Shore'),
            ('South Shore East Mirror Spot', 'Lake Hylia South Shore'),
            ('Lake Hylia Island Mirror Spot', 'Lake Hylia Island'),
            ('Lake Hylia Central Island Mirror Spot', 'Lake Hylia Central Island'),
            ('Lake Hylia Water Mirror Spot', 'Lake Hylia Water'),
            ('Lake Hylia Water D Mirror Spot', 'Lake Hylia Water D'),
            ('Lake Hylia Teleporter', 'Ice Palace Area')
        ], [
            ('Lake Hylia Island Pier', 'Lake Hylia Island'),
            ('Ice Lake Mirror Spot', 'Ice Lake Area'),
            ('Ice Lake Southwest Mirror Spot', 'Ice Lake Ledge (West)'),
            ('Ice Lake Southeast Mirror Spot', 'Ice Lake Ledge (East)'),
            ('Ice Lake Northeast Mirror Spot', 'Ice Lake Northeast Bank'),
            ('Ice Palace Mirror Spot', 'Ice Palace Area'),
            ('Ice Lake Moat Mirror Spot', 'Ice Lake Moat'),
            ('Ice Palace Teleporter', 'Lake Hylia Water D')
        ]),
    0x37: ([
            ('Ice Cave Mirror Spot', 'Ice Cave Area')
        ], [
            ('Shopping Mall Mirror Spot', 'Shopping Mall Area')
        ]),
    0x3a: ([
            ('Desert Pass Ledge Mirror Spot', 'Desert Pass Ledge'),
            ('Desert Pass Mirror Spot', 'Desert Pass Area')
        ], [
            ('Desert Pass Ladder (North)', 'Desert Pass Area'),
            ('Desert Pass Ladder (South)', 'Desert Pass Ledge'),
            ('Swamp Nook Mirror Spot', 'Swamp Nook Area'),
            ('Swamp Nook Southeast Mirror Spot', 'Swamp Nook Area'),
            ('Swamp Nook Pegs Mirror Spot', 'Swamp Nook Area')
        ]),
    0x3b: ([
            ('Dam Mirror Spot', 'Dam Area')
        ], [
            ('Swamp Mirror Spot', 'Swamp Area')
        ]),
    0x3c: ([
            ('South Pass Mirror Spot', 'South Pass Area')
        ], [
            ('Dark South Pass Mirror Spot', 'Dark South Pass Area')
        ]),
    0x3f: ([
            ('Octoballoon Mirror Spot', 'Octoballoon Area')
        ], [
            ('Bomber Corner Mirror Spot', 'Bomber Corner Area')
        ])
}

parallelsimilar_connections = [('Maze Race ES', 'Kakariko Suburb WS'),
                                ('Dig Game EC', 'Frog WC')
                            ]

# non shuffled overworld
default_connections = [('Lost Woods NW', 'Master Sword Meadow SC'),
                        ('Lost Woods SW', 'Lost Woods Pass NW'),
                        ('Lost Woods SC', 'Lost Woods Pass NE'),
                        ('Lost Woods SE', 'Kakariko Fortune NE'),
                        ('Lost Woods EN', 'Lumberjack WN'),
                        ('Lumberjack SW', 'Mountain Entry NW'),
                        ('Mountain Entry SE', 'Kakariko Pond NE'),
                        ('Zora Waterfall NE', 'Zoras Domain SW'),
                        ('Lost Woods Pass SW', 'Kakariko NW'),
                        ('Lost Woods Pass SE', 'Kakariko NC'),
                        ('Kakariko Fortune SC', 'Kakariko NE'),
                        ('Kakariko Fortune EN', 'Kakariko Pond WN'),
                        ('Kakariko Fortune ES', 'Kakariko Pond WS'),
                        ('Kakariko Pond SW', 'Forgotten Forest NW'),
                        ('Kakariko Pond SE', 'Forgotten Forest NE'),
                        ('Kakariko Pond EN', 'Sanctuary WN'),
                        ('Kakariko Pond ES', 'Sanctuary WS'),
                        ('Forgotten Forest ES', 'Hyrule Castle WN'),
                        ('Sanctuary EC', 'Graveyard WC'),
                        ('Graveyard EC', 'River Bend WC'),
                        ('River Bend SW', 'Wooden Bridge NW'),
                        ('River Bend SC', 'Wooden Bridge NC'),
                        ('River Bend SE', 'Wooden Bridge NE'),
                        ('River Bend EN', 'Potion Shop WN'),
                        ('River Bend EC', 'Potion Shop WC'),
                        ('River Bend ES', 'Potion Shop WS'),
                        ('Potion Shop EN', 'Zora Approach WN'),
                        ('Potion Shop EC', 'Zora Approach WC'),
                        ('Zora Approach NE', 'Zora Waterfall SE'),
                        ('Kakariko SE', 'Kakariko Suburb NE'),
                        ('Kakariko ES', 'Blacksmith WS'),
                        ('Hyrule Castle SW', 'Central Bonk Rocks NW'),
                        ('Hyrule Castle SE', 'Links House NE'),
                        ('Hyrule Castle ES', 'Sand Dunes WN'),
                        ('Wooden Bridge SW', 'Sand Dunes NW'),
                        ('Sand Dunes SC', 'Stone Bridge NC'),
                        ('Eastern Palace SW', 'Tree Line NW'),
                        ('Eastern Palace SE', 'Eastern Nook NE'),
                        ('Maze Race ES', 'Kakariko Suburb WS'),
                        ('Kakariko Suburb ES', 'Flute Boy WS'),
                        ('Flute Boy SW', 'Flute Boy Approach NW'),
                        ('Flute Boy SC', 'Flute Boy Approach NC'),
                        ('Flute Boy Approach EC', 'C Whirlpool WC'),
                        ('C Whirlpool NW', 'Central Bonk Rocks SW'),
                        ('C Whirlpool SC', 'Dam NC'),
                        ('C Whirlpool EN', 'Statues WN'),
                        ('C Whirlpool EC', 'Statues WC'),
                        ('C Whirlpool ES', 'Statues WS'),
                        ('Central Bonk Rocks EN', 'Links House WN'),
                        ('Central Bonk Rocks EC', 'Links House WC'),
                        ('Central Bonk Rocks ES', 'Links House WS'),
                        ('Links House SC', 'Statues NC'),
                        ('Links House ES', 'Stone Bridge WS'),
                        ('Stone Bridge SC', 'Lake Hylia NW'),
                        ('Stone Bridge EN', 'Tree Line WN'),
                        ('Stone Bridge EC', 'Tree Line WC'),
                        ('Stone Bridge WC', 'Hobo EC'),
                        ('Tree Line SC', 'Lake Hylia NC'),
                        ('Tree Line SE', 'Lake Hylia NE'),
                        ('Desert EC', 'Desert Pass WC'),
                        ('Desert ES', 'Desert Pass WS'),
                        ('Desert Pass EC', 'Dam WC'),
                        ('Desert Pass ES', 'Dam WS'),
                        ('Dam EC', 'South Pass WC'),
                        ('Statues SC', 'South Pass NC'),
                        ('South Pass ES', 'Lake Hylia WS'),
                        ('Lake Hylia EC', 'Octoballoon WC'),
                        ('Lake Hylia ES', 'Octoballoon WS'),
                        ('Octoballoon NW', 'Ice Cave SW'),
                        ('Octoballoon NE', 'Ice Cave SE'),
                        ('West Death Mountain EN', 'East Death Mountain WN'),
                        ('West Death Mountain ES', 'East Death Mountain WS'),
                        ('East Death Mountain EN', 'Death Mountain TR Pegs WN'),

                        ('Skull Woods SW', 'Skull Woods Pass NW'),
                        ('Skull Woods SC', 'Skull Woods Pass NE'),
                        ('Skull Woods SE', 'Dark Fortune NE'),
                        ('Skull Woods EN', 'Dark Lumberjack WN'),
                        ('Dark Lumberjack SW', 'Bumper Cave NW'),
                        ('Bumper Cave SE', 'Outcast Pond NE'),
                        ('Skull Woods Pass SW', 'Village of Outcasts NW'),
                        ('Skull Woods Pass SE', 'Village of Outcasts NC'),
                        ('Dark Fortune SC', 'Village of Outcasts NE'),
                        ('Dark Fortune EN', 'Outcast Pond WN'),
                        ('Dark Fortune ES', 'Outcast Pond WS'),
                        ('Outcast Pond SW', 'Shield Shop NW'),
                        ('Outcast Pond SE', 'Shield Shop NE'),
                        ('Outcast Pond EN', 'Dark Chapel WN'),
                        ('Outcast Pond ES', 'Dark Chapel WS'),
                        ('Dark Chapel EC', 'Dark Graveyard WC'),
                        ('Dark Graveyard EC', 'Qirn Jump WC'),
                        ('Qirn Jump SW', 'Broken Bridge NW'),
                        ('Qirn Jump SC', 'Broken Bridge NC'),
                        ('Qirn Jump SE', 'Broken Bridge NE'),
                        ('Qirn Jump EN', 'Dark Witch WN'),
                        ('Qirn Jump EC', 'Dark Witch WC'),
                        ('Qirn Jump ES', 'Dark Witch WS'),
                        ('Dark Witch EN', 'Catfish Approach WN'),
                        ('Dark Witch EC', 'Catfish Approach WC'),
                        ('Catfish Approach NE', 'Catfish SE'),
                        ('Village of Outcasts SE', 'Frog NE'),
                        ('Village of Outcasts ES', 'Hammer Pegs WS'),
                        ('Pyramid SW', 'Dark Bonk Rocks NW'),
                        ('Pyramid SE', 'Big Bomb Shop NE'),
                        ('Pyramid ES', 'Dark Dunes WN'),
                        ('Broken Bridge SW', 'Dark Dunes NW'),
                        ('Dark Dunes SC', 'Hammer Bridge NC'),
                        ('Palace of Darkness SW', 'Dark Tree Line NW'),
                        ('Palace of Darkness SE', 'Palace of Darkness Nook NE'),
                        ('Dig Game EC', 'Frog WC'),
                        ('Dig Game ES', 'Frog WS'),
                        ('Frog ES', 'Stumpy WS'),
                        ('Stumpy SW', 'Stumpy Approach NW'),
                        ('Stumpy SC', 'Stumpy Approach NC'),
                        ('Stumpy Approach EC', 'Dark C Whirlpool WC'),
                        ('Dark C Whirlpool NW', 'Dark Bonk Rocks SW'),
                        ('Dark C Whirlpool SC', 'Swamp NC'),
                        ('Dark C Whirlpool EN', 'Hype Cave WN'),
                        ('Dark C Whirlpool EC', 'Hype Cave WC'),
                        ('Dark C Whirlpool ES', 'Hype Cave WS'),
                        ('Dark Bonk Rocks EN', 'Big Bomb Shop WN'),
                        ('Dark Bonk Rocks EC', 'Big Bomb Shop WC'),
                        ('Dark Bonk Rocks ES', 'Big Bomb Shop WS'),
                        ('Big Bomb Shop SC', 'Hype Cave NC'),
                        ('Big Bomb Shop ES', 'Hammer Bridge WS'),
                        ('Hammer Bridge SC', 'Ice Lake NW'),
                        ('Hammer Bridge EN', 'Dark Tree Line WN'),
                        ('Hammer Bridge EC', 'Dark Tree Line WC'),
                        ('Dark Tree Line SC', 'Ice Lake NC'),
                        ('Dark Tree Line SE', 'Ice Lake NE'),
                        ('Swamp Nook EC', 'Swamp WC'),
                        ('Swamp Nook ES', 'Swamp WS'),
                        ('Swamp EC', 'Dark South Pass WC'),
                        ('Hype Cave SC', 'Dark South Pass NC'),
                        ('Dark South Pass ES', 'Ice Lake WS'),
                        ('Ice Lake EC', 'Bomber Corner WC'),
                        ('Ice Lake ES', 'Bomber Corner WS'),
                        ('Bomber Corner NW', 'Shopping Mall SW'),
                        ('Bomber Corner NE', 'Shopping Mall SE'),
                        ('West Dark Death Mountain EN', 'East Dark Death Mountain WN'),
                        ('West Dark Death Mountain ES', 'East Dark Death Mountain WS'),
                        ('East Dark Death Mountain EN', 'Turtle Rock WN')
                        ]

isolated_regions = [
    'Death Mountain Floating Island',
    'Mimic Cave Ledge',
    'Spiral Mimic Ledge Extend',
    'Mountain Entry Ledge',
    'Maze Race Prize',
    'Maze Race Ledge',
    'Desert Ledge',
    'Desert Palace Entrance (North) Spot',
    'Desert Palace Mouth',
    'Dark Death Mountain Floating Island',
    'Dark Death Mountain Ledge',
    'Dark Death Mountain Isolated Ledge',
    'Bumper Cave Ledge',
    'Pyramid Exit Ledge'
]

flute_data = {
    #Slot    LW Region                         DW Region                            OWID   VRAM    BG Y    BG X   Link Y  Link X   Cam Y   Cam X   Unk1    Unk2   IconY   IconX    AltY    AltX  AltVRAM  AltBGY  AltBGX  AltCamY AltCamX AltUnk1 AltUnk2 AltIconY AltIconX
    0x09: (['Lost Woods East Area',           'Skull Woods Forest'],                0x00, 0x1042, 0x022e, 0x0202, 0x0290, 0x0288, 0x029b, 0x028f, 0xfff2, 0x000e, 0x0290, 0x0288, 0x0290, 0x0290),
    0x02: (['Lumberjack Area',                'Dark Lumberjack Area'],              0x02, 0x059c, 0x00d6, 0x04e6, 0x0138, 0x0558, 0x0143, 0x0563, 0xfffa, 0xfffa, 0x0138, 0x0550),
    0x0b: (['West Death Mountain (Bottom)',   'West Dark Death Mountain (Top)'],    0x03, 0x1600, 0x02ca, 0x060e, 0x0328, 0x0678, 0x0337, 0x0683, 0xfff6, 0xfff2, 0x035b, 0x0680, 0x0118, 0x0860, 0x05c0, 0x00b8, 0x07ec, 0x0127, 0x086b, 0xfff8, 0x0004, 0x0148, 0x0850),
    0x0e: (['East Death Mountain (Bottom)',   'East Dark Death Mountain (Bottom)'], 0x05, 0x1860, 0x031e, 0x0d00, 0x0388, 0x0da8, 0x038d, 0x0d7d, 0x0000, 0x0000, 0x0388, 0x0da8),
    0x07: (['Death Mountain TR Pegs',         'Turtle Rock Area'],                  0x07, 0x0804, 0x0102, 0x0e1a, 0x0160, 0x0e90, 0x016f, 0x0e97, 0xfffe, 0x0006, 0x0160, 0x0f20),
    0x0a: (['Mountain Entry Area',            'Bumper Cave Area'],                  0x0a, 0x0180, 0x0220, 0x0406, 0x0280, 0x0488, 0x028f, 0x0493, 0x0000, 0xfffa, 0x0280, 0x0488),
    0x0f: (['Zora Waterfall Area',            'Catfish Area'],                      0x0f, 0x0316, 0x025c, 0x0eb2, 0x02c0, 0x0f28, 0x02cb, 0x0f2f, 0x0002, 0xfffe, 0x02d0, 0x0f38),
    0x10: (['Lost Woods Pass West Area',      'Skull Woods Pass West Area'],        0x10, 0x0080, 0x0400, 0x0000, 0x0448, 0x0058, 0x046f, 0x0085, 0x0000, 0x0000, 0x0448, 0x0058),
    0x11: (['Kakariko Fortune Area',          'Dark Fortune Area'],                 0x11, 0x0912, 0x051e, 0x0292, 0x0588, 0x0318, 0x058d, 0x031f, 0x0000, 0xfffe, 0x0588, 0x0318),
    0x12: (['Kakariko Pond Area',             'Outcast Pond Area'],                 0x12, 0x0890, 0x051a, 0x0476, 0x0578, 0x04f8, 0x0587, 0x0503, 0xfff6, 0x000a, 0x0578, 0x04f8),
    0x13: (['Sanctuary Area',                 'Dark Chapel Area'],                  0x13, 0x051c, 0x04aa, 0x06de, 0x0508, 0x0758, 0x0517, 0x0763, 0xfff6, 0x0002, 0x0508, 0x0758),
    0x14: (['Graveyard Area',                 'Dark Graveyard Area'],               0x14, 0x089c, 0x051e, 0x08e6, 0x0580, 0x0958, 0x058b, 0x0963, 0x0000, 0xfffa, 0x0580, 0x0928, 0x0580, 0x0948),
    0x15: (['River Bend East Bank',           'Qirn Jump East Bank'],               0x15, 0x041a, 0x0486, 0x0ad2, 0x04e8, 0x0b48, 0x04f3, 0x0b4f, 0x0008, 0xfffe, 0x04f8, 0x0b60),
    0x16: (['Potion Shop Area',               'Dark Witch Area'],                   0x16, 0x0888, 0x0516, 0x0c4e, 0x0578, 0x0cc8, 0x0583, 0x0cd3, 0xfffa, 0xfff2, 0x0598, 0x0ccf),
    0x17: (['Zora Approach Ledge',            'Catfish Approach Ledge'],            0x17, 0x039e, 0x047e, 0x0ef2, 0x04e0, 0x0f68, 0x04eb, 0x0f6f, 0x0000, 0xfffe, 0x04e0, 0x0f68),
    0x18: (['Kakariko Area',                  'Village of Outcasts Area'],          0x18, 0x0b30, 0x0759, 0x017e, 0x07b7, 0x0200, 0x07c6, 0x020b, 0x0007, 0x0002, 0x07c0, 0x0210, 0x07c8, 0x01f8),
    0x1a: (['Forgotten Forest Area',          'Shield Shop Fence'],                 0x1a, 0x081a, 0x070f, 0x04d2, 0x0770, 0x0548, 0x077c, 0x054f, 0xffff, 0xfffe, 0x0770, 0x0548),
    0x1b: (['Hyrule Castle Courtyard',        'Pyramid Area'],                      0x1b, 0x0c30, 0x077a, 0x0786, 0x07d8, 0x07f8, 0x07e7, 0x0803, 0x0006, 0xfffa, 0x07d8, 0x07f8),
    0x1d: (['Wooden Bridge Area',             'Broken Bridge Northeast'],           0x1d, 0x0602, 0x06c2, 0x0a0e, 0x0720, 0x0a80, 0x072f, 0x0a8b, 0xfffe, 0x0002, 0x0720, 0x0a80),
    0x26: (['Eastern Palace Area',            'Palace of Darkness Area'],           0x1e, 0x1802, 0x091e, 0x0c0e, 0x09c0, 0x0c80, 0x098b, 0x0c8b, 0x0000, 0x0002, 0x09c0, 0x0c80),
    0x22: (['Blacksmith Area',                'Hammer Pegs Area'],                  0x22, 0x058c, 0x08aa, 0x0462, 0x0908, 0x04d8, 0x0917, 0x04df, 0x0006, 0xfffe, 0x0908, 0x04d8),
    0x25: (['Sand Dunes Area',                'Dark Dunes Area'],                   0x25, 0x030e, 0x085a, 0x0a76, 0x08b8, 0x0ae8, 0x08c7, 0x0af3, 0x0006, 0xfffa, 0x08b8, 0x0b08),
    0x28: (['Maze Race Area',                 'Dig Game Area'],                     0x28, 0x0908, 0x0b1e, 0x003a, 0x0b88, 0x00b8, 0x0b8d, 0x00bf, 0x0000, 0x0006, 0x0b88, 0x00b8),
    0x29: (['Kakariko Suburb Area',           'Frog Area'],                         0x29, 0x0408, 0x0a7c, 0x0242, 0x0ae0, 0x02c0, 0x0aeb, 0x02c7, 0x0002, 0xfffe, 0x0ae0, 0x02c0),
    0x2a: (['Flute Boy Area',                 'Stumpy Area'],                       0x2a, 0x058e, 0x0aac, 0x046e, 0x0b10, 0x04e8, 0x0b1b, 0x04f3, 0x0002, 0x0002, 0x0b10, 0x04e8),
    0x2b: (['Central Bonk Rocks Area',        'Dark Bonk Rocks Area'],              0x2b, 0x0620, 0x0acc, 0x0700, 0x0b30, 0x0790, 0x0b3b, 0x0785, 0xfff2, 0x0000, 0x0b30, 0x0770),
    0x2c: (['Links House Area',               'Big Bomb Shop Area'],                0x2c, 0x0588, 0x0ab9, 0x0840, 0x0b17, 0x08b8, 0x0b26, 0x08bf, 0xfff7, 0x0000, 0x0b20, 0x08b8),
    0x2d: (['Stone Bridge Area',              'Hammer Bridge South Area'],          0x2d, 0x0886, 0x0b1e, 0x0a2a, 0x0ba0, 0x0aa8, 0x0b8b, 0x0aaf, 0x0000, 0x0006, 0x0bc4, 0x0ad0),
    0x2e: (['Tree Line Area',                 'Dark Tree Line Area'],               0x2e, 0x0100, 0x0a1a, 0x0c00, 0x0a78, 0x0c30, 0x0a87, 0x0c7d, 0x0006, 0x0000, 0x0a78, 0x0c58),
    0x2f: (['Eastern Nook Area',              'Palace of Darkness Nook Area'],      0x2f, 0x0798, 0x0afa, 0x0eb2, 0x0b58, 0x0f30, 0x0b67, 0x0f37, 0xfff6, 0x000e, 0x0b50, 0x0f30),
    0x38: (['Desert Palace Teleporter Ledge', 'Misery Mire Teleporter Ledge'],      0x30, 0x1880, 0x0f1e, 0x0000, 0x0fa8, 0x0078, 0x0f8d, 0x008d, 0x0000, 0x0000, 0x0fb0, 0x0070),
    0x32: (['Flute Boy Approach Area',        'Stumpy Approach Area'],              0x32, 0x03a0, 0x0c6c, 0x0500, 0x0cd0, 0x05a8, 0x0cdb, 0x0585, 0x0002, 0x0000, 0x0cd6, 0x0568),
    0x33: (['C Whirlpool Outer Area',         'Dark C Whirlpool Outer Area'],       0x33, 0x0180, 0x0c20, 0x0600, 0x0c80, 0x0628, 0x0c8f, 0x067d, 0x0000, 0x0000, 0x0c80, 0x0628),
    0x34: (['Statues Area',                   'Hype Cave Area'],                    0x34, 0x088e, 0x0d00, 0x0866, 0x0d60, 0x08d8, 0x0d6f, 0x08e3, 0x0000, 0x000a, 0x0d60, 0x08d8),
    #0x35: (['Lake Hylia Area',                'Ice Lake Area'],                     0x35, 0x0d00, 0x0da6, 0x0a06, 0x0e08, 0x0a80, 0x0e13, 0x0a8b, 0xfffa, 0xfffa, 0x0d88, 0x0a88),
    0x3e: (['Lake Hylia South Shore',         'Ice Lake Ledge (East)'],             0x35, 0x1860, 0x0f1e, 0x0d00, 0x0f98, 0x0da8, 0x0f8b, 0x0d85, 0x0000, 0x0000, 0x0f90, 0x0da4),
    0x37: (['Ice Cave Area',                  'Shopping Mall Area'],                0x37, 0x0786, 0x0cf6, 0x0e2e, 0x0d58, 0x0ea0, 0x0d63, 0x0eab, 0x000a, 0x0002, 0x0d48, 0x0ed0),
    0x3a: (['Desert Pass Area',               'Swamp Nook Area'],                   0x3a, 0x001a, 0x0e08, 0x04c6, 0x0e70, 0x0540, 0x0e7d, 0x054b, 0x0006, 0x000a, 0x0e70, 0x0540),
    0x3b: (['Dam Area',                       'Swamp Area'],                        0x3b, 0x069e, 0x0edf, 0x06f2, 0x0f3d, 0x0778, 0x0f4c, 0x077f, 0xfff1, 0xfffe, 0x0f30, 0x0770),
    0x3c: (['South Pass Area',                'Dark South Pass Area'],              0x3c, 0x0584, 0x0ed0, 0x081e, 0x0f38, 0x0898, 0x0f45, 0x08a3, 0xfffe, 0x0002, 0x0f38, 0x0898),
    0x3f: (['Octoballoon Area',               'Bomber Corner Area'],                0x3f, 0x0810, 0x0f05, 0x0e75, 0x0f67, 0x0ef3, 0x0f72, 0x0efa, 0xfffb, 0x000b, 0x0f80, 0x0ef0)
}

tile_swap_spoiler_table = \
"""                       0 1 2 3 4 5 6 7
                      +---+-+---+---+-+
      01234567   A(00)|   |s|   |   |s|
     +--------+       | s +-+ s | s +-+
A(00)|s ss s s|  B(08)|   |s|   |   |s|
B(08)|  s    s|       +-+-+-+-+-+-+-+-+
C(10)|ssssssss|  C(10)|s|s|s|s|s|s|s|s|
D(18)|s ss ss |       +-+-+-+-+-+-+-+-+
E(20)|  s  s  |  D(18)|   |s|   |s|   |
F(28)|ssssssss|       | s +-+ s +-+ s |
G(30)|s ssss s|  E(20)|   |s|   |s|   |
H(38)|  sss  s|       +-+-+-+-+-+-+-+-+
     +--------+  F(28)|s|s|s|s|s|s|s|s|
            +-+       +-+-+-+-+-+-+-+-+
  Ped/Hobo: |s|  G(30)|   |s|s|s|   |s|
            +-+       | s +-+-+-+ s +-+
      Zora: |s|  H(38)|   |s|s|s|   |s|
            +-+       +---+-+-+-+---+-+"""

flute_spoiler_table = \
"""                       0 1 2 3 4 5 6 7
                      +---+-+---+---+-+
      01234567   A(00)|   |s|   |   |s|
     +--------+       | s +-+ s | s +-+
A(00)|s ss s s|  B(08)|   |s|   |   |s|
B(08)|  s    s|       +-+-+-+-+-+-+-+-+
C(10)|ssssssss|  C(10)|s|s|s|s|s|s|s|s|
D(18)|s ss ss |       +-+-+-+-+-+-+-+-+
E(20)|  s  s  |  D(18)|   |s|   |s|   |
F(28)|ssssssss|       | s +-+ s +-+ s |
G(30)|s ssss s|  E(20)|   |s|   |s|   |
H(38)|  sss  s|       +-+-+-+-+-+-+-+-+
     +--------+  F(28)|s|s|s|s|s|s|s|s|
                      +-+-+-+-+-+-+-+-+
                 G(30)|   |s|s|s|   |s|
                      | s +-+-+-+ s +-+
                 H(38)|   |s|s|s|   |s|
                      +---+-+-+-+---+-+"""

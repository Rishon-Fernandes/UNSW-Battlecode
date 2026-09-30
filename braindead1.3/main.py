import helper as unswbc
from helper import Direction, EdgeType
import random
from collections import deque

ct: unswbc.Controller
game: unswbc.Game

# Seed so we get the same random generator every time.
random.seed(0)

S = 50

# Not used in (current) bfs. May need for smth else.
def closest_pearl():
    for i in range(7):
        for j in range(i + 1):
            L = [(j, i - j), (-j, i - j), (j, j - i), (-j, j - i)]
            for (x, y) in L:
                if ct.get_tile(unswbc.Position(x, y)).has_pearl():
                    return (x, y)
    return None

def has_or_will_have_pearl(tile, steps):
    if tile.has_pearl(): 
        return True
    elif tile.get_pearl_time() < 0: 
        return False
    elif tile.get_pearl_time() <= steps: 
        return True

def bfs():
    width, height = game.get_map_size()
    visited = [[0] * width for _ in range(height)]

    here_pos = ct.get_position()
    here = ct.get_tile(here_pos)
    directions = Direction.get_direction_list()

    q = deque([(here, None, 0)])
    visited[here_pos.y][here_pos.x] = 1

    while len(q) != 0:
        left_element = q.popleft()
        tile, source_dir, steps = left_element

        if steps > 1 or source_dir != ct.get_dir().get_opposite():
            if source_dir != None and has_or_will_have_pearl(tile, steps):
                return source_dir

        for dir in directions:
            edge_in_dir = tile.get_edge(dir).get_edge_type()
            if edge_in_dir == EdgeType.KELP:
                continue
            if edge_in_dir == EdgeType.PORTAL:
                continue
            
            tile_in_dir_pos = tile.get_position().add_dir(dir)

            if not tile_in_dir_pos.is_in_vision():
                continue 

            tile_in_dir_tile = ct.get_tile(tile_in_dir_pos)
            
            if tile_in_dir_tile.get_dragon() is not None:
                continue

            if visited[tile_in_dir_pos.y][tile_in_dir_pos.x] == 1:
                continue

            if source_dir is None:
                q.append((tile_in_dir_tile, dir, steps + 1))
            else:
                q.append((tile_in_dir_tile, source_dir, steps + 1))
            
            visited[tile_in_dir_pos.y][tile_in_dir_pos.x] = 1
    return None


def execute_turn() -> None:
    here = ct.get_position()
    here_tile = ct.get_tile(here)

    directions = Direction.get_direction_list() # north, east, south, west
    
    for direc in directions:
        is_portal = 0
        edge = here_tile.get_edge(direc).get_edge_type()
        if edge == EdgeType.PORTAL and direc != ct.get_dir().get_opposite():
            is_portal = 2 * (direc.get_offset()[0] + 1) + direc.get_offset()[1] + 1
        sonar_message = ct.get_id() + ct.get_length() * (2 ** 16) + is_portal * (2 ** 32) # id, length, is_portal
        ct.send_sonar(direc, sonar_message)

    messages = ct.get_sonar_messages()
    random.shuffle(directions)

    if game.get_round_num() < S and 4 < ct.get_length() < 20 and ct.get_unit_count() < game.get_unit_limit() / 2:
        ct.do_split(2)
        return

    bfs_dir = bfs()
    if bfs_dir is not None:
        ct.make_move(bfs_dir)
        return

    for direction in directions:
        if direction == ct.get_dir().get_opposite():
            continue

        if edge == EdgeType.PORTAL:
            if len(messages) and ct.get_length() < 14:
                for message in messages:
                    message = message // (2 ** 32)
                    if message == 0:
                        continue
                    elif message == 1:
                        if dir.value == Direction.EAST:
                            break
                    elif message == 5:
                        if dir == Direction.WEST:
                            break
                    elif message == 2:
                        if dir == Direction.SOUTH:
                            break
                    elif message == 4:
                        if dir == Direction.NORTH:
                            break
                else:
                    ct.make_move(dir)
                    return None
                continue
    
    for direction in directions:
        if direction == ct.get_dir().get_opposite():
            continue

        edge = here_tile.get_edge(direction).get_edge_type()
        if edge == EdgeType.KELP:
            continue

        if edge == EdgeType.PORTAL:
            continue

        ahead = here.add_dir(direction)
        ahead_tile = ct.get_tile(ahead)
        if ahead_tile.get_dragon() is not None:
            k = ahead_tile.get_dragon()
            if k.get_id() == ct.get_id() and edge == EdgeType.PORTAL:
                ct.output_log("Moving in", direction.value)
                ct.make_move(direction)
                return
            if k.is_head() and k.get_team() != ct.get_team():
                if ct.get_length() == 2:
                    ct.make_move(direction)
                    return
                if ct.can_split(2) and ct.get_unit_count() < game.get_unit_limit():
                    ct.do_split(ct.get_length() - 2)
                    return
            continue

# 1 # TODO: small dragons of our team give preference to big dragons
        # prevents head-on-head collsions
        for direc in directions:
            if direc == ct.get_dir().get_opposite():
                continue

            ahead_edge = ahead_tile.get_edge(direc).get_edge_type()
            if ahead_edge == EdgeType.KELP:
                continue

            # if the tile next to next tile is a dragon, there is chance of collision
            ahead_ahead = ahead.add_dir(direc)
            ahead_ahead_tile = ct.get_tile(ahead_ahead)

            if ahead_ahead_tile.get_dragon() is None:
                continue
            if ahead_ahead_tile.get_dragon().is_head():
                if ahead_ahead_tile.get_dragon().get_team() != ct.get_team():
                    if ct.can_split(2) and ct.get_unit_count() < game.get_unit_limit():
                        ct.do_split(ct.get_length() - 2)
                        return
                else:
                    flag = 0
                    if messages is not None:    
                        for message in messages:
                            if message % (2 ** 16) == ahead_ahead_tile.get_dragon().get_id():
                                message = message // (2 ** 16)
                                if message > ct.get_length():
                                    if ct.can_split(2) and ct.get_unit_count() < game.unit_limit():
                                        ct.do_split(ct.get_length() - 2)
                                        return
                                    flag = 1
                                    break
                    if flag:
                        continue
        
        ct.output_log("Moving in", direction.value)
        ct.make_move(direction)
        return

    # splits before dying to minimise loss
    ct.do_split(ct.get_length() - 2)
    return

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()


"""
If we call for a tile not in vision then the game just stops and dragon dies. Be careful.
"""
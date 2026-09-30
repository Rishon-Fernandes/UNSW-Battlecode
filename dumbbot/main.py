import helper as unswbc
from helper import Direction, EdgeType
import random
from collections import deque

ct: unswbc.Controller
game: unswbc.Game

# Seed so we get the same random generator every time.
random.seed(0)

S = 100
N = 470 # round after which small suicide to feed large
splitter = random.randint(1, 8) <= 7

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
    if tile.has_pearl(): return True
    elif tile.get_pearl_time() < 0: return False
    elif tile.get_pearl_time() <= steps: return True

def suicide_bfs():
    width, height = game.get_map_size()
        
    visited = [[0] * width for _ in range(height)]

    here = ct.get_tile(ct.get_position())

    # tile, direction taken at first step from here tile to second tile, number of steps from here tile to current tile
    q = deque([here])
    visited[here.get_position().y][here.get_position().x] = 1

    while len(q) != 0:
        tile = q.popleft()

        if tile.get_dragon().is_head() and tile != here:
            if tile.get_dragon().get_team() == ct.get_team():
                return True
            return False

        directions = Direction.get_direction_list()

        for dir in directions:
            edge_in_dir = tile.get_edge(dir).get_edge_type()
            if edge_in_dir == EdgeType.KELP:
                continue

            # TODO: FIGURE OUT HOW TO DEAL WITH PORTALS!!
            
            tile_in_dir_pos = tile.get_position().add_dir(dir)

            if not tile_in_dir_pos.is_in_vision():
                continue 

            tile_in_dir_tile = ct.get_tile(tile_in_dir_pos)

            if visited[tile_in_dir_pos.y][tile_in_dir_pos.x] == 1:
                continue
            if tile_in_dir_tile.get_dragon() is not None:
                if tile_in_dir_tile.get_dragon().is_head() and tile_in_dir_tile != here:
                    if tile_in_dir_tile.get_dragon().get_team() == ct.get_team():
                        return True
                    return False
                continue

            q.append(tile_in_dir_tile)
            
            visited[tile_in_dir_pos.y][tile_in_dir_pos.x] = 1
    return False

def bfs():
    width, height = game.get_map_size()
    
    visited = [[0] * width for _ in range(height)]

    here = ct.get_tile(ct.get_position())

    # tile, direction taken at first step from here tile to second tile, number of steps from here tile to current tile
    q = deque([(here, None, 0)])
    visited[here.get_position().y][here.get_position().x] = 1

    while len(q) != 0:
        left_element = q.popleft()
        tile, source_dir, steps = left_element

        if source_dir != None and has_or_will_have_pearl(tile, steps):
            return source_dir

        directions = Direction.get_direction_list()

        for dir in directions:
            edge_in_dir = tile.get_edge(dir).get_edge_type()
            if edge_in_dir == EdgeType.KELP:
                continue

            # TODO: FIGURE OUT HOW TO DEAL WITH PORTALS!!
            
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

def vision_has_ally_head():
    for tile in ct.get_vision().get_tiles():
        if tile.get_dragon().is_head() and tile.get_dragon().get_team() == ct.get_team():
            return True

    return False

def execute_turn() -> None:
    ct.output_log("Execution started")
    here = ct.get_position()
    here_tile = ct.get_tile(here)

    # if game.get_round_num() > N and has_greater_ally():
    if game.get_round_num() > N and ct.get_length() <= 5 and suicide_bfs():
        ct.make_move(ct.get_dir().get_opposite())
        return
    ct.output_log("if 1 done")

    if splitter and game.get_round_num() < S and ct.can_split(2) and ct.get_unit_count() < game.get_unit_limit():
        ct.output_log("Splitting as round num < S")
        ct.do_split(2)
        return
    ct.output_log("if 2 done")

    bfs_dir = bfs()
    if bfs_dir is not None:
        ct.make_move(bfs_dir)
        return

    directions = Direction.get_direction_list()
    directions.remove(ct.get_dir().get_opposite())
    random.shuffle(directions)
    
    for direction in directions:
        
        edge = here_tile.get_edge(direction).get_edge_type()
        if edge == EdgeType.KELP:
            continue

        ahead = ct.get_tile(here.add_dir(direction))
        if ahead.get_dragon() is not None:
            continue

        ct.make_move(direction)
        return

    if ct.can_split(ct.get_length() - 2) and ct.get_unit_count() < game.get_unit_limit():
        ct.do_split(ct.get_length() - 2)
    else:
        ct.make_move(directions[0])

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
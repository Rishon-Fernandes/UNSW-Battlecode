import helper as unswbc
from helper import Direction, EdgeType
import random
from collections import deque

ct: unswbc.Controller
game: unswbc.Game

# Seed so we get the same random generator every time.
random.seed(0)

S = 500 / 2

# Not used in (current) bfs. May need for smth else.
def closest_pearl():
    for i in range(7):
        for j in range(i + 1):
            L = [(j, i - j), (-j, i - j), (j, j - i), (-j, j - i)]
            for (x, y) in L:
                if ct.get_tile(unswbc.Position(x, y)).has_pearl():
                    return (x, y)
    return None

def bfs():
    # keeps track of whether a tile has been in the q or not, that is, traversed or not
    width, height = game.get_map_size()
    visited = [[0] * width] * height

    # queue
    here = ct.get_tile(ct.get_position())
    q = deque([(here, None, None)])
    visited[here.get_position().y][tile.get_position().x] = 1

    ct.output_log(here.get_position().x)

    while q:
        # source_dir is the direction parent -> child (the child is the current tile)
        # parent is parent of the tile
        # CAN OPTIMISE by storing only the parent and not the source_dir as that can be derived
        left_element = q.popleft()
        tile, parent, source_dir = left_element
        if tile.has_pearl():
            while parent[1] is not None:
                prev = parent
                parent = parent[1]
            return prev[2]
        
        directions = Direction.get_direction_list()
        for dir in directions:
            edge_in_dir = tile.get_edge(dir).get_edge_type()
            if edge_in_dir == EdgeType.KELP:
                continue

            # TODO: FIGURE OUT HOW TO DEAL WITH PORTALS!!
            if edge_in_dir == EdgeType.PORTAL:
                continue
            
            tile_in_dir_pos = tile.get_position().add_dir(dir)
            tile_in_dir_tile = ct.get_tile(tile_in_dir_pos)
            
            if tile_in_dir_tile.get_dragon() is not None or not tile_in_dir_pos.is_in_vision():
                continue

            if visited[tile_in_dir_pos.y][tile_in_dir_pos.x]:
                continue
            
            q.append((tile_in_dir_tile, left_element, dir))
            visited[tile_in_dir_pos.y][tile_in_dir_pos.x] = 1

    return None


def execute_turn() -> None:
    """Step onto the first open neighbouring tile."""
    here = ct.get_position()
    here_tile = ct.get_tile(here)

    directions = Direction.get_direction_list()
    directions.remove(ct.get_dir().get_opposite())
    random.shuffle(directions)

    if game.get_round_num() < S and ct.can_split(2):
        ct.do_split(2)
        return

    bfs_dir = bfs()
    if bfs_dir is not None:
        ct.make_move(bfs_dir)
        return
    
    for direction in directions:
        
        edge = here_tile.get_edge(direction).get_edge_type()
        if edge == EdgeType.KELP:
            continue

        ahead = ct.get_tile(here.add_dir(direction))
        if ahead.get_dragon() is not None:
            continue

        ct.output_log("Moving in", direction.value)
        ct.make_move(direction)
        return

    if ct.can_split(ct.get_length() - 2):
        ct.do_split(ct.get_length() - 2)
        ct.output_log("splitting")
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


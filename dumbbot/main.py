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

    here = ct.get_tile(ct.get_position())

    # tile, initial direction
    q = deque([(here, None)])
    visited[here.get_position().y][here.get_position().x] = 1

    while len(q) != 0:
        left_element = q.popleft()
        tile, source_dir = left_element
        ct.output_log((tile.get_position().x, tile.get_position().y))

        if tile.has_pearl():
            return source_dir
        
        directions = Direction.get_direction_list()
        for dir in directions:
            edge_in_dir = tile.get_edge(dir).get_edge_type()
            if edge_in_dir == EdgeType.KELP:
                continue

            # TODO: FIGURE OUT HOW TO DEAL WITH PORTALS!!
            # if edge_in_dir == EdgeType.PORTAL:
            #     continue
            
            tile_in_dir_pos = tile.get_position().add_dir(dir)

            if not tile_in_dir_pos.is_in_vision():
                continue

            tile_in_dir_tile = ct.get_tile(tile_in_dir_pos)
            
            if tile_in_dir_tile.get_dragon() is not None:
                continue

            if visited[tile_in_dir_pos.y][tile_in_dir_pos.x] == 1:
                continue

            if source_dir is None:
                q.append((tile_in_dir_tile, dir))
            else:
                q.append((tile_in_dir_tile, source_dir))
            
            visited[tile_in_dir_pos.y][tile_in_dir_pos.x] = 1

    ct.output_log("BFS FAIL")
    return None


def execute_turn() -> None:
    """Step onto the first open neighbouring tile."""
    here = ct.get_position()
    here_tile = ct.get_tile(here)

    # if game.get_round_num() < S and ct.can_split(2):
    #     ct.output_log("Splitting as round num < S")
    #     ct.do_split(2)
    #     return

    bfs_dir = bfs()
    if bfs_dir is not None:
        ct.make_move(bfs_dir)
        ct.output_log("bfs success:", bfs_dir.value())
        return

    ct.output_log("bfs fail")

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

    if ct.can_split(ct.get_length() - 2):
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
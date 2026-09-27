import helper as unswbc
from helper import Direction, EdgeType
import random

ct: unswbc.Controller
game: unswbc.Game

# Seed so we get the same random generator every time.
random.seed(0)

S = 500 / 2

def execute_turn() -> None:
    """Step onto the first open neighbouring tile."""
    here = ct.get_position()
    here_tile = ct.get_tile(here)

    directions = Direction.get_direction_list()
    directions.remove(ct.get_dir().get_opposite())
    # random.shuffle(directions)
    # sort in decreasing order of distance because dir = direction is set 
    # to be the most recent feasible direction. so we need the least distance direction at last.

    if game.get_round_num() < S and ct.can_split(2):
        ct.do_split(2)
        return

    dir = None
    min_d_to_avg_pearl = 7
    avg_pearl_coord = avg_coordinates()

    for direction in directions:
        edge = here_tile.get_edge(direction).get_edge_type()

        if edge == EdgeType.KELP:
            continue

        ahead = ct.get_tile(here.add_dir(direction))
        if ahead.get_dragon() is not None:
            continue
        elif ahead.has_pearl():
            ct.make_move(direction)
            return

        #prospective position
        pros_pos = (here.x + direction.get_offset()[0], here.y + direction.get_offset()[1])
        d_tmp = abs(avg_pearl_coord[0] - pros_pos[0]) + abs(avg_pearl_coord[1] - pros_pos[1])
        if dir is None or d_tmp < min_d_to_avg_pearl:
            dir = direction
            min_d_to_avg_pearl = d_tmp

    if dir is not None:
        ct.make_move(dir)
    else:
        if ct.can_split(ct.get_length() - 2):
            ct.do_split(ct.get_length() - 2)
            ct.output_log("splitting")
        else:
            ct.make_move(directions[0])

def avg_coordinates():
    sum = (0, 0)
    for tile in ct.get_tiles():
        sum = (tile.get_position().x + sum[0], tile.get_position().y + sum[1])
    return (sum[0]/49, sum[1]/49)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()

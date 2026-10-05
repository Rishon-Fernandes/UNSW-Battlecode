#include "helper.hpp"

#include <algorithm>
#include <random>
#include <optional>
#include <queue>
#include <unordered_set>
#include <deque>
#include <functional>


// Only traverse destinations we can inspect in the current vision window.
unswbc::Tile const* next_tile(unswbc::Controller const& ct,
                             unswbc::Tile const& from,
                             unswbc::Direction direction)
{
    auto const& edge = from.get_edge(direction);
    if (!edge.is_passable())
        return nullptr;

    auto const adjacent = from.get_position().add_dir(direction);
    if (!edge.is_portal())
        return ct.get_tile(adjacent);

    // The exit tile has the partner portal on its incoming side. Exclude
    // the reverse view of the entrance edge itself.
    for (auto const& tile : ct.get_tiles())
    {
        if (tile.get_position() != adjacent &&
            tile.get_edge(direction.get_opposite()).get_portal_id() == edge.get_portal_id())
            return &tile;
    }
    return nullptr; // Partner exit outside vision: destination is unknown.
}

std::deque<unswbc::Position> visible_body(unswbc::Controller const& ct)
{
    // Recover the visible prefix of our body in head-to-tail order. Unknown
    // rear length is tracked separately; unmatched visible parts stay blocked.
    std::deque<unswbc::Position> body{ct.get_position()};
    std::unordered_set<unswbc::Position, unswbc::PositionHash> recovered{ct.get_position()};
    while (static_cast<int>(body.size()) < ct.get_length())
    {
        unswbc::Tile const* rear = nullptr;
        for (auto const& tile : ct.get_tiles())
        {
            auto const* part = tile.get_dragon();
            if (!part || part->get_id() != ct.get_id() || recovered.contains(tile.get_position()))
                continue;
            auto const* toward_head = next_tile(ct, tile, part->get_dir());
            if (toward_head && toward_head->get_position() == body.back())
            {
                rear = &tile;
                break;
            }
        }
        if (!rear)
            break;
        body.push_back(rear->get_position());
        recovered.insert(rear->get_position());
    }

    return body;
}

// Trace forced corridors using static edges, not temporary body occupancy.
// Unknown continuations and branches are allowed; known traps are deferred.
bool direction_is_trap(unswbc::Controller const& ct, unswbc::Direction first)
{
    auto const* start = ct.get_tile(ct.get_position());
    auto const* tile = start ? next_tile(ct, *start, first) : nullptr;
    if (!tile)
        return false; // First-step safety is checked separately.
    struct Visit
    {
        unswbc::Position position;
        unswbc::Direction incoming;
        int step;
    };
    std::vector<Visit> visits;
    std::unordered_set<unswbc::Position, unswbc::PositionHash> pearls;
    auto incoming = first;
    int step = 1;
    for (;;)
    {
        for (auto const& visit : visits)
            if (visit.position == tile->get_position() && visit.incoming == incoming)
            {
                int const loop_size = step - visit.step;
                // The tail must vacate before a later head step, so a loop
                // needs strictly more cells than the grown dragon's length.
                return ct.get_length() + static_cast<int>(pearls.size()) >= loop_size;
            }
        visits.push_back({tile->get_position(), incoming, step});
        if (tile->has_pearl())
            pearls.insert(tile->get_position());

        std::optional<unswbc::Direction> forward;
        for (auto const direction : unswbc::Direction::get_direction_list())
        {
            // Portals preserve heading, so the reverse edge is still opposite
            // to the incoming direction, even if the previous tile is remote.
            if (direction == incoming.get_opposite() || !tile->get_edge(direction).is_passable())
                continue;
            if (!next_tile(ct, *tile, direction))
                return false; // Corridor continues outside vision.
            if (forward)
                return false; // A branch ends this forced-corridor check.
            forward = direction;
        }
        if (!forward)
            return true; // Every forward edge ends in kelp.
        tile = next_tile(ct, *tile, *forward);
        incoming = *forward;
        ++step;
    }
}

std::optional<unswbc::Direction> pearl_bfs(unswbc::Controller const& ct,
                                        std::array<unswbc::Direction, 4> const& directions,
                                        std::array<bool, 4> const& allowed_first)
{
    struct Node
    {
        unswbc::Tile const* tile;
        int distance;
        unswbc::Direction first_direction;
    };

    auto const* start = ct.get_tile(ct.get_position());
    if (!start)
        return std::nullopt;

    std::queue<Node> queue;
    std::unordered_set<unswbc::Position, unswbc::PositionHash> visited;
    visited.insert(start->get_position());
    queue.push({start, 0, directions.front()});

    while (!queue.empty())
    {
        auto const node = queue.front();
        queue.pop();
        auto const countdown = node.tile->get_pearl_time();
        // First step is this round, after its pearl tick has already occurred.
        // At distance d, only d - 1 additional pearl ticks have elapsed.
        if (node.distance > 0 &&
            (node.tile->has_pearl() || (countdown >= 0 && countdown <= node.distance - 1)))
            return node.first_direction;

        for (std::size_t i = 0; i < directions.size(); ++i)
        {
            auto const direction = directions[i];
            if (node.distance == 0 && !allowed_first[i])
                continue;
            auto const* next = next_tile(ct, *node.tile, direction);
            if (!next || next->get_dragon())
                continue;
            if (!visited.insert(next->get_position()).second)
                continue;
            queue.push({next, node.distance + 1,
                        node.distance == 0 ? direction : node.first_direction});
        }
    }
    return std::nullopt;
}

// Search simple sprint paths, simulating growth, tail movement and payment.
std::optional<std::vector<unswbc::Direction>> queen_attack(
    unswbc::Controller const& ct,
    std::array<unswbc::Direction, 4> const& directions)
{
    if (ct.get_id() <= 1)
        return std::nullopt; // Original queens never sacrifice themselves.

    unswbc::Tile const* target = nullptr;
    for (auto const& tile : ct.get_tiles())
    {
        auto const* part = tile.get_dragon();
        if (part && part->is_head() && part->get_id() <= 1 && part->get_team() != ct.get_team())
            target = &tile;
    }
    if (!target)
        return std::nullopt;

    auto const body = visible_body(ct);
    std::unordered_set<unswbc::Position, unswbc::PositionHash> recovered(body.begin(), body.end());

    auto const free_steps = (ct.get_length() + 3) / 4;
    std::vector<unswbc::Direction> path;
    std::unordered_set<unswbc::Position, unswbc::PositionHash> on_path{ct.get_position()};
    int examined = 0;
    // Bound work independently of dragon length and maze branching.
    constexpr int search_limit = 8192;
    std::function<bool(unswbc::Tile const*, std::deque<unswbc::Position> const&, int, int)> search;
    search = [&](unswbc::Tile const* from, std::deque<unswbc::Position> const& current_body, int length, int remaining) {
        if (++examined > search_limit || remaining == 0)
            return false;
        bool const paid = static_cast<int>(path.size()) >= free_steps;
        if (paid && length <= 2)
            return false;
        for (auto const direction : directions)
        {
            if (examined >= search_limit)
                return false;
            auto const* next = next_tile(ct, *from, direction);
            if (!next || on_path.contains(next->get_position()))
                continue;
            auto const pos = next->get_position();
            if (std::find(current_body.begin(), current_body.end(), pos) != current_body.end())
                continue; // Includes the tail before it advances.
            auto const* part = next->get_dragon();
            if (part && part->get_id() == ct.get_id() && !recovered.contains(pos))
                continue;
            if (part && part->get_id() != ct.get_id() && next != target)
                continue;

            path.push_back(direction);
            if (next == target)
                return true; // Head-to-head kills both, before tail removal.

            auto next_body = current_body;
            next_body.push_front(pos);
            int next_length = length + 1;
            auto const remove_tail = [&] {
                --next_length;
                if (static_cast<int>(next_body.size()) > next_length)
                    next_body.pop_back();
            };
            if (!next->has_pearl())
                remove_tail();
            if (paid)
                remove_tail();
            on_path.insert(pos);
            if (search(next, next_body, next_length, remaining - 1))
                return true;
            on_path.erase(pos);
            path.pop_back();
        }
        return false;
    };

    auto const* start = ct.get_tile(ct.get_position());
    if (!start)
        return std::nullopt;
    // Iterative deepening finds shorter attacks first. No pearl ticks occur
    // between sprint steps, so only pearls already present can fund growth.
    for (int depth = 1; depth < static_cast<int>(ct.get_tiles().size()) && examined < search_limit; ++depth)
        if (search(start, body, ct.get_length(), depth))
            return path;
    return std::nullopt;
}

struct EscapeSplit
{
    int child_size;
    unswbc::Direction direction;
    unswbc::Position blocker;
};

std::optional<EscapeSplit> escape_split(unswbc::Controller const& ct)
{
    auto const body = visible_body(ct);
    // A remote, unseen child head cannot be assessed reliably.
    if (static_cast<int>(body.size()) != ct.get_length())
        return std::nullopt;
    auto const* here = ct.get_tile(ct.get_position());
    auto const* tail = ct.get_tile(body.back());
    std::optional<EscapeSplit> best;
    int best_score = -1;
    for (auto const direction : unswbc::Direction::get_direction_list())
    {
        auto const* blocker = next_tile(ct, *here, direction);
        if (!blocker)
            continue;
        auto const found = std::find(body.begin(), body.end(), blocker->get_position());
        int const retained = static_cast<int>(std::distance(body.begin(), found));
        int const child_size = ct.get_length() - retained;
        if (found == body.end() || !ct.can_split(child_size))
            continue;

        // The child head is the old tail, and the blocker is its new tail.
        bool child_can_leave = false;
        for (auto const child_direction : unswbc::Direction::get_direction_list())
        {
            auto const* destination = next_tile(ct, *tail, child_direction);
            if (destination && !destination->get_dragon() && !destination->has_pearl())
                child_can_leave = true;
        }
        // If no safe non-pearl move exists, moving toward the old tail's
        // predecessor hits the child's own neck and releases its entire body.
        auto const* neck = next_tile(ct, *tail, tail->get_dragon()->get_dir());
        bool const can_sacrifice = neck && neck->get_position() == body[body.size() - 2];
        if (!child_can_leave && !can_sacrifice)
            continue;
        // For queens preserve maximum length; for other parents first try
        // to keep both dragons alive, then prefer retaining more parent length.
        int const score = retained + (ct.get_id() > 1 && child_can_leave ? 4096 : 0);
        if (score > best_score)
        {
            best_score = score;
            best = EscapeSplit{child_size, direction, blocker->get_position()};
        }
    }
    return best;
}

// Sonar request: magic(16), reserved(7), queen(1), team(1), parent ID(16),
// parent x/y and released x/y (6 bits each). No sender authentication exists.
std::uint64_t release_message(unswbc::Controller const& ct, unswbc::Position blocker)
{
    auto const head = ct.get_position();
    return (std::uint64_t{0xBC71} << 48) |
           (std::uint64_t{ct.get_id() <= 1} << 41) |
           (std::uint64_t{ct.get_team() == unswbc::Team::B} << 40) |
           (static_cast<std::uint64_t>(ct.get_id()) << 24) |
           (static_cast<std::uint64_t>(head.x) << 18) |
           (static_cast<std::uint64_t>(head.y) << 12) |
           (static_cast<std::uint64_t>(blocker.x) << 6) |
           static_cast<std::uint64_t>(blocker.y);
}

std::optional<unswbc::Direction> release_square(
    unswbc::Controller const& ct, unswbc::Position blocker,
    std::array<unswbc::Direction, 4> const& directions)
{
    auto const* tile = ct.get_tile(blocker);
    if (!tile || !tile->get_dragon() || tile->get_dragon()->get_id() != ct.get_id())
        return std::nullopt;
    auto const body = visible_body(ct);
    auto const* head = ct.get_tile(ct.get_position());
    if (static_cast<int>(body.size()) == ct.get_length() && body.back() == blocker)
        for (auto const direction : directions)
        {
            auto const* destination = next_tile(ct, *head, direction);
            if (destination && !destination->get_dragon() && !destination->has_pearl())
                return direction;
        }
    // Verify reverse movement really hits our neck, including at portals.
    auto const reverse = ct.get_dir().get_opposite();
    auto const* neck = next_tile(ct, *head, reverse);
    if (neck && neck->get_dragon() && neck->get_dragon()->get_id() == ct.get_id())
        return reverse;
    for (auto const direction : directions)
    {
        if (!head->get_edge(direction).is_passable())
            return direction;
        auto const* destination = next_tile(ct, *head, direction);
        auto const* part = destination ? destination->get_dragon() : nullptr;
        if (part && (!part->is_head() || part->get_id() == ct.get_id()))
            return direction;
    }
    return std::nullopt;
}

std::optional<unswbc::Direction> rescue_parent(
    unswbc::Controller const& ct,
    std::array<unswbc::Direction, 4> const& directions)
{
    if (ct.get_id() <= 1)
        return std::nullopt;
    auto const messages = ct.get_sonar_messages();
    // Queen requests take precedence over requests from other parents.
    for (bool const queen_request : {true, false})
        for (auto const message : messages)
        {
            if ((message >> 48) != 0xBC71 || ((message >> 42) & 63) != 0)
                continue;
            int const parent_id = static_cast<int>((message >> 24) & 65535);
            bool const queen = ((message >> 41) & 1) != 0;
            bool const team_b = ((message >> 40) & 1) != 0;
            if (queen != queen_request || queen != (parent_id <= 1) ||
                parent_id >= ct.get_id() || team_b != (ct.get_team() == unswbc::Team::B))
                continue;
            unswbc::Position const parent{static_cast<int>((message >> 18) & 63),
                                          static_cast<int>((message >> 12) & 63)};
            unswbc::Position const blocker{static_cast<int>((message >> 6) & 63),
                                           static_cast<int>(message & 63)};
            if (!parent.is_in_map() || !blocker.is_in_map())
                continue;
            if (auto const* visible_parent = ct.get_tile(parent))
            {
                auto const* part = visible_parent->get_dragon();
                if (!part || !part->is_head() || part->get_id() != parent_id || part->get_team() != ct.get_team())
                    continue;
                bool adjacent = false;
                for (auto const direction : directions)
                    if (auto const* next = next_tile(ct, *visible_parent, direction))
                        adjacent |= next->get_position() == blocker;
                if (!adjacent)
                    continue;
            }
            if (auto const action = release_square(ct, blocker, directions))
                return action;
        }

    // Every turn, independently help a visible allied queen that has no
    // empty visible move and is blocked by one of our segments.
    for (auto const& tile : ct.get_tiles())
    {
        auto const* part = tile.get_dragon();
        if (!part || !part->is_head() || part->get_id() > 1 || part->get_team() != ct.get_team())
            continue;
        bool has_move = false;
        std::optional<unswbc::Position> blocker;
        for (auto const direction : directions)
        {
            auto const* next = next_tile(ct, tile, direction);
            if (!next)
                continue;
            auto const* occupant = next->get_dragon();
            if (!occupant)
                has_move = true;
            else if (occupant->get_id() == ct.get_id())
                blocker = next->get_position();
        }
        if (!has_move && blocker)
            if (auto const action = release_square(ct, *blocker, directions))
                return action;
    }
    return std::nullopt;
}

int main()
{
    auto [ct, game] = unswbc::init();

    // Seed so we get the same random generator every time.
    std::mt19937 shuffler(0);

    while (unswbc::update(ct, game))
    {
        // Replan each turn, moving one step toward the closest pearl target.
        auto const here = ct.get_position();
        auto const* hereTile = ct.get_tile(here);
        bool moved = false;

        auto directions = unswbc::Direction::get_direction_list();
        std::shuffle(directions.begin(), directions.end(), shuffler);

        if (auto const rescue = rescue_parent(ct, directions))
        {
            ct.output_log("Releasing parent escape cell");
            ct.make_move(*rescue);
            unswbc::end_turn();
            continue;
        }

        if (auto const attack = queen_attack(ct, directions))
        {
            ct.output_log("Attacking enemy queen");
            ct.make_moves(*attack);
            unswbc::end_turn();
            continue;
        }

        // Classify first directions once, before either BFS pass.
        std::array<bool, 4> preferred{};
        for (std::size_t i = 0; i < directions.size(); ++i)
        {
            auto const* ahead = hereTile ? next_tile(ct, *hereTile, directions[i]) : nullptr;
            preferred[i] = ahead && !ahead->get_dragon() && !direction_is_trap(ct, directions[i]);
        }
        // Pearl BFS, then any safe move, within each priority tier.
        for (bool const avoid_traps : {true, false})
        {
            auto const allowed = avoid_traps ? preferred : std::array<bool, 4>{true, true, true, true};
            if (auto const direction = pearl_bfs(ct, directions, allowed))
            {
                ct.make_move(*direction);
                moved = true;
                break;
            }
            for (std::size_t i = 0; i < directions.size(); ++i)
            {
                auto const direction = directions[i];
                auto const* ahead = hereTile ? next_tile(ct, *hereTile, direction) : nullptr;
                if (!allowed[i] || !ahead || ahead->get_dragon())
                    continue;
                ct.output_log("Moving in", direction);
                ct.make_move(direction);
                moved = true;
                break;
            }
            if (moved)
                break;
        }

        if (!moved)
        {
            auto const child_size = ct.get_length() - 2;
            if (ct.can_split(child_size))
            {
                if (auto const plan = escape_split(ct))
                {
                    ct.do_split(plan->child_size);
                    ct.send_sonar(plan->direction, release_message(ct, plan->blocker));
                }
                else
                {
                    // No verified escape cut: keep the original fallback.
                    ct.do_split(child_size);
                }
            }
            else
            {
                // Trapped short dragons take an enemy head down with them.
                // Otherwise prefer a fatal collision that kills only us;
                // unknown portal exits rank below these, allied queens last.
                auto sacrifice = directions.front();
                int best_rank = 5;
                for (auto const direction : directions)
                {
                    auto const* ahead = hereTile ? next_tile(ct, *hereTile, direction) : nullptr;
                    auto const* part = ahead ? ahead->get_dragon() : nullptr;
                    int rank = 1; // Unknown destination.
                    if (hereTile && !hereTile->get_edge(direction).is_passable())
                        rank = 0; // Kelp kills only the moving dragon.
                    else if (part)
                    {
                        if (!part->is_head() || part->get_id() == ct.get_id())
                            rank = 0;
                        else if (part->get_team() != ct.get_team())
                            rank = ct.get_length() <= 3 ? -1 : 1;
                        else
                            rank = part->get_id() <= 1 ? 4 : 3;
                    }
                    if (rank < best_rank)
                    {
                        best_rank = rank;
                        sacrifice = direction;
                    }
                }
                ct.make_move(sacrifice);
            }
        }
        unswbc::end_turn();
    }
}

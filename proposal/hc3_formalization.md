# HC3 Formalization

HC3 asks one exact question:

Does there exist at least one valid playthrough from `start` to `door` under
the full game rules?

## State

The solver tracks this full state:

`(node_id, stamina, strength, has_key, collected_items, defeated_monsters)`

Each component matters for future reachability:

- `node_id`: current graph node
- `stamina`: remaining movement budget
- `strength`: remaining combat budget
- `has_key`: whether the key has already been collected
- `collected_items`: which one-shot items are already consumed
- `defeated_monsters`: which one-shot monsters are already cleared

## Success Condition

HC3 is satisfied if the solver reaches the door and:

- the door is unlocked, or the key has already been collected
- final stamina is at least `minimum_final_stamina`
- final strength is at least `minimum_final_strength`

## Transition Semantics

One transition means moving from one compressed graph node to another along one
graph edge.

The transition is processed in this order:

1. Pay the edge stamina cost.
2. Defeat every undefeated corridor monster on that edge.
3. Enter the destination node.
4. If the destination node has an undefeated monster, defeat it.
5. If the destination node has an uncollected item, collect it.
6. If the destination node is the door, check the door rule and success.
7. If the destination node is not the door and stamina is now zero or below,
   the state is dead and is discarded.

This ordering intentionally allows a move that lands on a stamina potion with
exactly zero stamina after movement, because the potion is consumed immediately
after entering the cell.

## Graph Model

The solver does not search on the raw grid.

It first compresses the walkable area into a graph whose nodes are:

- `start`
- `door`
- every item cell
- monster cells that are also structural decision points
- every dead end
- every junction
- every turn cell

Edges represent straight corridor segments between those nodes.

Each edge stores:

- movement length in steps
- corridor monster ids encountered on that segment

Because items are always nodes, an item can never be skipped accidentally inside
an edge.

## Dominance Rule

Two labels are comparable only if they share the same:

- current node
- key possession
- collected item set
- defeated monster set

Among such labels, one dominates another if it has:

- at least as much stamina
- at least as much strength
- and is strictly better in at least one of them

Dominated labels are discarded because they can never enable a future action
that the stronger label cannot also perform.

## Exactness

This solver is exact, not heuristic.

It never declares a map solvable unless a legal playthrough exists, and it never
declares a map unsolvable if such a playthrough exists. The price is that the
state space can still grow combinatorially when the map contains many one-shot
resources and monsters.

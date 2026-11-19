from itm_arena.domain.types import RankedEntry


def rank_entries(entries: list[tuple[str, int]]) -> list[RankedEntry]:
    # Highest score first; nickname breaks ties so the order is always the same
    ordered = sorted(entries, key=lambda entry: (-entry[1], entry[0]))

    ranked: list[RankedEntry] = []
    for position, (nickname, score) in enumerate(ordered, start=1):
        if ranked and ranked[-1].score == score:
            # Tied with the previous entry, so share its rank
            rank = ranked[-1].rank
        else:
            # Ranks skip after a tie: 10, 10, 8 -> 1, 1, 3
            rank = position
        ranked.append(RankedEntry(rank=rank, nickname=nickname, score=score))
    return ranked

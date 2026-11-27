from itm_arena.domain.ranking import rank_entries
from itm_arena.domain.types import RankedEntry


def ranks(entries):
    return [entry.rank for entry in rank_entries(entries)]


def nicknames(entries):
    return [entry.nickname for entry in rank_entries(entries)]


def test_tied_scores_share_rank_and_next_rank_is_skipped():
    assert ranks([("amy", 10), ("ben", 10), ("cal", 8)]) == [1, 1, 3]


def test_no_ties_gives_consecutive_ranks():
    assert ranks([("amy", 10), ("ben", 9), ("cal", 8)]) == [1, 2, 3]


def test_tie_at_the_bottom():
    assert ranks([("amy", 10), ("ben", 8), ("cal", 8)]) == [1, 2, 2]


def test_skip_matches_the_size_of_the_tie():
    entries = [("amy", 10), ("ben", 10), ("cal", 10), ("dan", 7)]
    assert ranks(entries) == [1, 1, 1, 4]


def test_same_rank_is_ordered_by_nickname():
    entries = [("cal", 10), ("amy", 10), ("ben", 8)]
    assert nicknames(entries) == ["amy", "cal", "ben"]


def test_input_order_does_not_matter():
    entries = [("amy", 10), ("ben", 10), ("cal", 8)]
    assert rank_entries(list(reversed(entries))) == rank_entries(entries)


def test_empty_list():
    assert rank_entries([]) == []


def test_single_entry():
    expected = [RankedEntry(rank=1, nickname="solo", score=7)]
    assert rank_entries([("solo", 7)]) == expected


def test_all_tied():
    entries = [("cal", 5), ("amy", 5), ("ben", 5)]
    assert rank_entries(entries) == [
        RankedEntry(rank=1, nickname="amy", score=5),
        RankedEntry(rank=1, nickname="ben", score=5),
        RankedEntry(rank=1, nickname="cal", score=5),
    ]

import pytest

from itm_arena.domain.errors import InvalidSubmissionError
from itm_arena.domain.grading import grade_submission
from itm_arena.domain.types import AnswerKey, SubmittedAnswer

# Question ids start at 101 so they can never be confused with positions 1-10
KEYS = [AnswerKey(question_id=101 + i, answer_index=i % 4) for i in range(10)]


def answers_with(correct_count):
    # The first correct_count answers are right; the rest pick a wrong choice
    answers = []
    for i, key in enumerate(KEYS):
        if i < correct_count:
            selected = key.answer_index
        else:
            selected = (key.answer_index + 1) % 4
        answers.append(
            SubmittedAnswer(question_id=key.question_id, selected_index=selected)
        )
    return answers


def test_all_correct_returns_10():
    assert grade_submission(KEYS, answers_with(10)).score == 10


def test_all_wrong_returns_0():
    assert grade_submission(KEYS, answers_with(0)).score == 0


def test_partial_returns_number_of_correct_answers():
    assert grade_submission(KEYS, answers_with(7)).score == 7


def test_returns_per_question_correctness():
    result = grade_submission(KEYS, answers_with(7))
    expected = {key.question_id: i < 7 for i, key in enumerate(KEYS)}
    assert result.correct_by_question == expected


def test_answer_order_does_not_matter():
    shuffled = list(reversed(answers_with(7)))
    assert grade_submission(KEYS, shuffled).score == 7


def test_rejects_too_few_answers():
    with pytest.raises(InvalidSubmissionError):
        grade_submission(KEYS, answers_with(10)[:9])


def test_rejects_too_many_answers():
    extra = SubmittedAnswer(question_id=101, selected_index=0)
    with pytest.raises(InvalidSubmissionError):
        grade_submission(KEYS, answers_with(10) + [extra])


@pytest.mark.parametrize("bad_index", [-1, 4])
def test_rejects_selected_index_out_of_range(bad_index):
    answers = answers_with(10)
    answers[0] = SubmittedAnswer(question_id=101, selected_index=bad_index)
    with pytest.raises(InvalidSubmissionError):
        grade_submission(KEYS, answers)


def test_rejects_unknown_question_id():
    answers = answers_with(10)
    answers[0] = SubmittedAnswer(question_id=999, selected_index=0)
    with pytest.raises(InvalidSubmissionError):
        grade_submission(KEYS, answers)


def test_rejects_duplicate_question_id():
    # The count still matches (10), but question 102 has no answer
    answers = answers_with(10)
    answers[1] = SubmittedAnswer(question_id=101, selected_index=0)
    with pytest.raises(InvalidSubmissionError):
        grade_submission(KEYS, answers)

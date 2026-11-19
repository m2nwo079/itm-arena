from itm_arena.domain.errors import InvalidSubmissionError
from itm_arena.domain.types import AnswerKey, GradeResult, SubmittedAnswer

CHOICE_COUNT = 4


def grade_submission(
    answer_keys: list[AnswerKey], answers: list[SubmittedAnswer]
) -> GradeResult:
    if len(answers) != len(answer_keys):
        raise InvalidSubmissionError(
            f"Expected {len(answer_keys)} answers, got {len(answers)}"
        )

    correct_index = {key.question_id: key.answer_index for key in answer_keys}
    correct_by_question: dict[int, bool] = {}

    for answer in answers:
        if not 0 <= answer.selected_index < CHOICE_COUNT:
            raise InvalidSubmissionError(
                f"Selected index {answer.selected_index} is out of range"
            )
        if answer.question_id not in correct_index:
            raise InvalidSubmissionError(f"Unknown question_id {answer.question_id}")
        if answer.question_id in correct_by_question:
            raise InvalidSubmissionError(f"Duplicate question_id {answer.question_id}")
        correct_by_question[answer.question_id] = (
            answer.selected_index == correct_index[answer.question_id]
        )

    # Same count, no unknown ids, and no duplicates means every question was answered
    score = sum(correct_by_question.values())
    return GradeResult(score=score, correct_by_question=correct_by_question)

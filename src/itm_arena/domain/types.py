from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDraft:
    text: str
    # Exactly four choices are expected
    choices: list[str]
    # Zero-based index of the correct choice (0 to 3)
    answer_index: int


@dataclass(frozen=True)
class QuizDraft:
    questions: list[QuestionDraft]


@dataclass(frozen=True)
class QuestionView:
    # Sent to the solver, so it never includes the answer
    question_id: int
    position: int
    text: str
    choices: list[str]


@dataclass(frozen=True)
class SubmittedAnswer:
    question_id: int
    # Zero-based index chosen by the solver
    selected_index: int


@dataclass(frozen=True)
class ValidationError:
    code: str
    # Question number from 1 to 10, or None for quiz-level errors
    position: int | None
    message: str



@dataclass(frozen=True)
class AnswerKey:
    # Correct answer for one saved question, passed from the DB layer to grading
    question_id: int
    # Zero-based index of the correct choice (0 to 3)
    answer_index: int
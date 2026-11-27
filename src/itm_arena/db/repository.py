"""Repositories: the only place that talks to the database.

These read and write rows and nothing else. 
Who may solve a quiz, when an account is locked, and when three reports hide a quiz are service-level rules
(issues #5, #7 and #15), not repository rules.

Repositories flush but never commit, so a caller can wrap several calls in one transaction with session_scope.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from itm_arena.db.models import Question, Quiz, User
from itm_arena.domain.types import AnswerKey, QuestionView, QuizDraft


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_nickname_key(self, nickname_key: str) -> User | None:
        """Look a user up by the normalised nickname used for uniqueness."""
        return self._session.scalar(
            select(User).where(User.nickname_key == nickname_key)
        )

    # register
    def add(
        self,
        *,
        nickname: str,
        nickname_key: str,
        pin_hash: str,
        pin_salt: str,
    ) -> User:
        user = User(
            nickname=nickname,
            nickname_key=nickname_key,
            pin_hash=pin_hash,
            pin_salt=pin_salt,
        )
        self._session.add(user)
        self._session.flush()
        return user


class QuizRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_owner(self, owner_id: int) -> Quiz | None:
        """The owner's only quiz, hidden or not, or None if they have none."""
        return self._session.scalar(select(Quiz).where(Quiz.owner_id == owner_id))

    def create_with_questions(
        self, *, owner_id: int, title: str, draft: QuizDraft
    ) -> Quiz:
        """Save a quiz and all of its questions as one unit of work.

        Positions are assigned from the order of the draft, starting at 1. The
        draft is expected to be valid already; validation is issue #3.
        """
        quiz = Quiz(owner_id=owner_id, title=title)
        self._session.add(quiz)
        self._session.flush()

        for position, question in enumerate(draft.questions, start=1):
            first, second, third, fourth = question.choices
            self._session.add(
                Question(
                    quiz_id=quiz.id,
                    position=position,
                    text=question.text,
                    choice_1=first,
                    choice_2=second,
                    choice_3=third,
                    choice_4=fourth,
                    answer_index=question.answer_index,
                )
            )
        self._session.flush()
        return quiz

    def list_question_views(self, quiz_id: int) -> list[QuestionView]:
        """Questions as the solver sees them, without the correct answers."""
        statement = (
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
        )
        return [
            QuestionView(
                question_id=question.id,
                position=question.position,
                text=question.text,
                choices=question.choices,
            )
            for question in self._session.scalars(statement)
        ]

    def list_answer_keys(self, quiz_id: int) -> list[AnswerKey]:
        """Correct answers for grading (#4). Never sent to the browser."""
        statement = (
            select(Question.id, Question.answer_index)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.position)
        )
        return [
            AnswerKey(question_id=question_id, answer_index=answer_index)
            for question_id, answer_index in self._session.execute(statement).all()
        ]
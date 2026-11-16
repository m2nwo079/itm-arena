# ITM Arena

A social quiz app where ITM students write quizzes about themselves
and find out who knows their classmates best.

## Purpose

Students in the same program often see each other in class but have few
light, low-pressure ways to get to know each other. ITM Arena gives them
one shared place to do that: each student writes a short quiz about
themselves, classmates solve it, and a ranking board shows who knows the
group best.

Link-based quiz sites such as QuizForFriend focus on a single quiz shared
through a link. ITM Arena is built for one group instead:

- All quizzes in the group appear in one list.
- One ranking board covers every quiz, not just a single one.
- Answers are graded on the server, so they are not exposed to players.
- Each quiz can be solved only once, and users cannot solve their own quiz.
- Quizzes that break the rules can be reported and hidden.

## Intended users

ITM students.

## Features (planned)

- Sign up and log in with a nickname and a 4-digit PIN
- Create one 10-question quiz per user, with four choices per question
- Solve each quiz once (users cannot solve their own quiz)
- Automatic grading and a ranking board with tied ranks
- Manage your own quiz, and hide quizzes through reports
- Demo mode with SQLite and fictional sample quizzes

Each feature will be described in more detail as it is implemented.

## Tech stack

Python, Streamlit, SQLAlchemy, PostgreSQL (Neon), SQLite (demo mode)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

We chose MIT for three reasons:

- It is short and easy for a small student team to read and apply.
- It lets anyone reuse, modify, and learn from our code, which fits a
  course project meant to be shared, as long as the copyright notice is kept.
- It is a permissive license, so it does not conflict with the open source
  libraries we depend on.

Copyright (c) 2026 Lee Min Woo, Lee Suk Hyun, Yu Byeong Hwa, Shin Min Gyu
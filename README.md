# ITM Arena

A social quiz app where ITM students write quizzes about themselves
and find out who knows their classmates best.

## Purpose

Students in the same program often see each other in class but have few
light, low-pressure ways to get to know each other. ITM Arena gives them
one shared place to do that: each student writes a short quiz about
themselves, classmates solve it, and each quiz's ranking shows who knows
its author best.

Link-based quiz sites such as QuizForFriend focus on a single quiz shared
through a link. ITM Arena is built for one group instead:

- All quizzes in the group appear in one list.
- Players use one account (nickname and PIN) for every quiz, and each quiz
  has its own ranking.
- Answers are graded on the server, so they are not exposed to players.
- Each quiz can be solved only once, and users cannot solve their own quiz.
- Quizzes that break the rules can be reported and hidden.

## Intended users

ITM students.

## Features (planned)

- Sign up and log in with a nickname and a 4-digit PIN
- Create one 10-question quiz per user, with four choices per question
- Solve each quiz once (users cannot solve their own quiz)
- Automatic grading and a ranking for each quiz, where tied scores share
  a rank (for example, 10, 10, 8 are ranked 1, 1, 3)
- Manage your own quiz, and hide quizzes through reports
- Demo mode with SQLite and fictional sample quizzes

Each feature will be described in more detail as it is implemented.

## Getting started

You need Git and Python 3.12, the version this project targets.

Clone the repository:

    git clone https://github.com/m2nwo079/itm-arena.git
    cd itm-arena

Create a virtual environment and install the dependencies.

On macOS or Linux:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

On Windows (PowerShell):

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Run the tests:

    pytest

Run the app:

    streamlit run app.py

The app opens in your browser. Activate the virtual environment again
each time you open a new terminal.

## Current limitations

ITM Arena is in early development.

- The app currently shows only a placeholder page. The screens are not
  built yet.
- Core logic such as input validation, grading, and ranking is being
  added step by step, so most planned features are not usable yet.
- Demo mode with sample quizzes is not available yet (#2).
- Tests run locally with pytest. Automated checks with GitHub Actions are
  not set up yet (#8).
- The online version is not deployed yet (#14).

## Tech stack

Python, Streamlit, SQLAlchemy, PostgreSQL (Neon), SQLite (demo mode)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

We chose MIT for three reasons:

- It is short and easy for a small student team to read and apply.
- It lets anyone reuse, modify, and learn from our code, which fits a
  course project meant to be shared, as long as the copyright notice is kept.
- It is a permissive license that works with the libraries we depend on:
  Streamlit (Apache-2.0), SQLAlchemy and pytest (MIT), and psycopg
  (LGPL-3.0). We only import these libraries and do not copy or modify
  their code, so our own code can stay MIT.

Copyright (c) 2026 Lee Min Woo, Lee Suk Hyun, Yu Byeong Hwa, Shin Min Gyu
# Contributing to ITM Arena

This guide is written for the four of us working on ITM Arena during the
course, and for anyone who reads the repository later and wants to
understand how we work. If you are outside the team, please open an issue
before sending a pull request.

Everything we put in this repository is written in English: code,
comments, tests, commit messages, issues, and pull requests.

By taking part you agree to follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Development setup

You need Git and Python 3.12, the version this project targets. If you
have a different version installed, mention it in your pull request
instead of changing the pinned dependencies on your own, so we can decide
together which version CI should use (issue #8).

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/m2nwo079/itm-arena.git
cd itm-arena
```

On Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the tests, then the app:

```bash
pytest
streamlit run app.py
```

The app runs in demo mode by default: a local SQLite database with sample
quizzes, so you never need a password or a database server to develop
(demo mode itself arrives with issue #2). The deployed app reads its
`DATABASE_URL` from Streamlit Secrets.

Never commit secrets or local data. `.streamlit/secrets.toml`, `*.db`,
and `.env` are listed in `.gitignore`; if you need a new secret, add its
**name** to the documentation and share the value outside the repository.

## Project layout

```
app.py                     Streamlit entry point
src/itm_arena/ui/          screens
src/itm_arena/services/    auth, quiz and ranking services
src/itm_arena/domain/      pure logic: types.py, errors.py, rules
src/itm_arena/db/          SQLAlchemy models and repositories
tests/                     unit, service and screen tests
requirements.txt           pinned dependencies
```

Dependencies point one way: UI calls services, services call the domain
and the database layer. Domain code stays pure — no Streamlit, no
database session — so it can be unit-tested directly.

Shared types live in `src/itm_arena/domain/types.py` and shared
exceptions in `src/itm_arena/domain/errors.py`. Use them instead of
defining your own copy. They are a contract between all of us, so if you
need to change or extend one, say so in your pull request description and
tag the people whose work depends on it.

Three conventions are easy to get wrong:

- `answer_index` and `selected_index` are zero-based (`0`–`3`).
- `position` is one-based (`1`–`10`).
- Every timestamp is UTC. The database layer hands back timezone-aware
  datetimes on both SQLite and PostgreSQL, so compare them with
  `datetime.now(timezone.utc)` and never store local time.

## Working on an issue

1. Take an issue that is assigned to you on the
   [board](https://github.com/users/m2nwo079/projects/1) and move its card
   from Ready to In progress.
2. Branch off the latest `main`:

   ```bash
   git switch main
   git pull
   git switch -c feat/6-tie-ranking
   ```

   Branch names are `type/issue-number-short-slug`, where `type` is one of
   `feat`, `fix`, `docs`, `test`, `refactor`, or `chore`. When the work has
   no issue — the initial repository documents, for example — drop the
   number and use `type/short-slug`, as in `docs/readme`.
3. Commit as you go, following
   [Conventional Commits](https://www.conventionalcommits.org/): a type, an
   optional scope, and an imperative summary.

   ```
   feat(domain): calculate tied ranks for equal scores
   test(domain): cover all-tied and empty ranking cases
   docs: add contributing guide
   ```
4. Run `pytest` before you push.
5. Open a pull request, fill in the template, and request the reviewer
   assigned to your issue. Move the card to In review.
6. After it is merged, move the card to Done. Once deployment is set up in
   #14, also check the deployed app if your change is visible there.

## Pull requests

- Keep a pull request small enough that your reviewer can read it in one
  sitting. One issue per pull request.
- The template asks for four things, and all of them are required:
  **Related issue**, **Summary**, **Verification** (what you actually ran
  and what you saw), and **AI use**.
- Write `Closes #12` in the description only when merging the pull request
  really finishes that issue. Otherwise write `Refs #12`.
- `main` is protected. Nothing is pushed to it directly, and one approval is
  required before a squash merge. Once CI is added in #8, a green run is
  required as well, and a red one blocks the merge.
- Resolve every review comment before merging. If you push changes after
  an approval, ask your reviewer to approve again.
- `main` is also what gets deployed, so a merge is a release. If a merge
  turns out to be wrong, revert the pull request rather than patching over
  it in a hurry. Reverting code does not undo data already written to the
  deployed database.

## Reviewing

- Reply to a review request within 24 hours, even if only to say when you
  can look at it.
- Read the code and the tests, not just the description. Check that the
  acceptance criteria in the linked issue are met, that the behaviour is
  covered by a test, and that shared types and error classes are used as
  agreed.
- Use GitHub's suggested changes for small fixes so the author can apply
  them in one click.
- Approve only what you understood. "I could not follow this part, please
  explain" is a useful review comment.

## Tests

- `tests/unit/` — pure domain functions: input validation, grading, tied
  ranking, PIN hashing, visibility rules.
- `tests/service/` — services against an in-memory SQLite database:
  duplicate attempts, solving your own quiz, a second quiz per user,
  reports and hiding.
- `tests/app/` — screens driven by `streamlit.testing.v1.AppTest` in demo
  mode.

Three test files still sit directly in `tests/`, from before this layout:
`test_smoke.py`, and `test_grading.py` and `test_ranking.py` once #23 and #24
are merged. #26 and #27 already use `tests/unit/` and `tests/service/`, so the
proposal is to move those two into `tests/unit/` in a small follow-up and
leave `test_smoke.py` where it is. If the team would rather drop the
subfolders altogether, say so on this pull request and this section changes
instead.

Every change in behaviour arrives with a test. When you fix a bug, add the
test that would have caught it.

## Using AI assistants

We are allowed to use AI tools, and we are required to be transparent
about it.

- Use them per issue. Generating the project, or a whole feature you have
  not read, is not allowed.
- Every pull request records the tool, the task it helped with, what you
  verified yourself, and which suggestions you accepted, changed, or
  rejected, and why.
- You own what you merge. If you cannot explain a line of it during
  review, it does not get merged.
- This section is about how we develop. The product itself contains no AI
  features.

## Decisions reviewers will hold you to

These follow from the design we agreed on, and a pull request that breaks
one needs a discussion first, not a workaround:

- A published quiz is never edited or deleted. Owners can hide and unhide
  their quiz; a quiz hidden by reports cannot be unhidden by its owner.
  Editing questions after people have played would make the ranking
  unfair.
- Correct answers stay on the server until a player submits. They are
  never sent to the browser with the questions.
- One quiz per user, one attempt per quiz, and one report per user are
  enforced by database constraints, not only by checks in Python, so that
  two simultaneous requests cannot both succeed.
- We have no migration tool. The table structure is agreed in issue #1
  and frozen once the app is in real use; later changes go in as a
  reviewed SQL script under `db/changes/` at the repository root — next to
  `src/` and `tests/`, not inside `src/itm_arena/db/`.

## Questions and problems

Open an issue if something is broken or unclear. For anything covered by
the Code of Conduct, contact m2nwo079@seoultech.ac.kr.

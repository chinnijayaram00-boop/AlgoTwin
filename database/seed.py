from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.schemas.auth import normalize_email
from database.models import User
from database.problem_catalog import sync_catalog, validate_catalog

# The account `seed_demo_data` creates so a fresh development database has
# something to sign in with. The password is a published development constant,
# not a secret: it exists only because `SEED_DEMO_DATA` is a development flag,
# and `SEED_DEMO_DATA=false` leaves the account out entirely. Deployments must
# set that flag to false -- see the README.
DEMO_USER_EMAIL = normalize_email("learner@algotwin.dev")
DEMO_USER_NAME = "Demo Learner"
DEMO_USER_PASSWORD = "algotwin-demo-2026"


def seed_demo_user(session: Session) -> None:
    """Create the demo learner unless the address is already taken.

    Without this the seeded database held no account at all, so the sign-in form
    had nothing to authenticate against and every attempt came back as
    `401 Invalid email or password.` regardless of what was typed.

    Existing rows are left completely alone, matched case-insensitively and only
    on the normalized address so this cannot create a second account for an
    address that is already registered under different casing. An existing
    account's password is never re-hashed or reset: a developer who changed the
    demo password keeps their own, and a real learner who claimed the address
    keeps their credentials.
    """
    existing = session.scalar(
        select(User).where(func.lower(User.email) == DEMO_USER_EMAIL)
    )
    if existing is not None:
        return

    session.add(
        User(
            name=DEMO_USER_NAME,
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD),
        )
    )
    session.commit()


def seed_demo_data(session: Session) -> None:
    """Reconcile the catalog and create the demo learner.

    The catalog sync runs first and validates every definition before writing, so
    a broken catalog stops the seed before the demo account exists rather than
    after. It is idempotent: an existing problem is updated in place, keeping its
    primary key, so a learner's progress and submissions stay attached to it.

    Earlier versions of this function inserted four hand-written problems here and
    left the twelve full definitions in `database/problem_defs` unreferenced. That
    left the `test_cases`, `hints`, `reference_solutions` and judge-limit columns
    the migration adds permanently empty, which a judge would have read as a
    problem with nothing to run.

    `init_db` calls the two halves separately so the catalog and the demo account
    can be switched off independently; this combined form stays because the test
    fixtures want both in one call.
    """
    validate_catalog()
    sync_catalog(session)
    seed_demo_user(session)

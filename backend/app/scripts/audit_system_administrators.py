"""Read-only report on System Administrator role holders and the platform
company - run before applying the add_platform_company migration or the
platform bootstrap, both of which refuse to proceed while conflicts exist.

Run with:
    python -m app.scripts.audit_system_administrators

Never writes anything and never prints secrets (no password hashes, no
tokens) - only ids, usernames, company codes, flags, and timestamps.

There is no platform-action audit table, so "did this account do anything
with its platform access?" can only be answered indirectly: the only
platform *writes* are company creation and activate/deactivate, which show
up as companies.created_at/updated_at at or after the account's promotion.
Read-only platform views (overview, company list/detail) leave no trace.
"""

from sqlalchemy import inspect, text

from app.core.roles import PLATFORM_COMPANY_CODE, SYSTEM_ADMINISTRATOR_ROLE
from app.db.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        has_flags = "is_platform" in {
            c["name"] for c in inspect(db.get_bind()).get_columns("companies")
        }
        role_id = db.execute(
            text("SELECT id FROM roles WHERE name = :name"), {"name": SYSTEM_ADMINISTRATOR_ROLE}
        ).scalar()
        print(f"'{SYSTEM_ADMINISTRATOR_ROLE}' role id: {role_id}")
        print(f"Platform columns present (migration applied): {has_flags}")

        flag_column = (
            ", u.is_system_administrator, c.is_platform" if has_flags else ""
        )
        holders = db.execute(
            text(
                f"""
                SELECT u.id, u.username, u.company_id, c.company_code, u.is_active,
                       u.created_at, u.updated_at{flag_column}
                FROM users u LEFT JOIN companies c ON c.id = u.company_id
                WHERE u.role_id = :role_id ORDER BY u.id
                """
            ),
            {"role_id": role_id},
        ).all()
        print(f"\nUsers holding the role: {len(holders)}")
        for h in holders:
            if has_flags and h.is_system_administrator and h.is_platform:
                kind = "platform account (flagged, platform company)"
            elif h.company_id is None:
                kind = "platform-level (no company) - adopted by the migration"
            else:
                kind = "TENANT USER - conflict"
            print(
                f"  id={h.id} username={h.username} company={h.company_code or '-'} "
                f"active={h.is_active} created={h.created_at} updated={h.updated_at} -> {kind}"
            )
            if kind.startswith("TENANT"):
                changes = db.execute(
                    text(
                        "SELECT id, company_code, created_at, updated_at FROM companies "
                        "WHERE created_at >= :since OR updated_at >= :since"
                    ),
                    {"since": h.updated_at},
                ).all()
                print(
                    f"    companies created/updated since {h.updated_at}: "
                    f"{[(c.id, c.company_code) for c in changes] or 'none'}"
                )

        reserved = db.execute(
            text("SELECT id, name FROM companies WHERE LOWER(company_code) = LOWER(:code)"),
            {"code": PLATFORM_COMPANY_CODE},
        ).all()
        print(f"\nCompanies using reserved code {PLATFORM_COMPANY_CODE}: {reserved or 'none'}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

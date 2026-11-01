"""Role names and the platform organization's identity - the one place these
strings are defined, so role checks, the bootstrap script, and the
migration that introduced the platform company can never drift apart.

Role *ids* are deliberately absent: they depend on install history (on the
development database, System Administrator is id 1 because the roles table
was re-seeded after the role-consolidation migration), so every caller must
resolve a role by name - see RoleRepository.get_by_name and GET /roles.
"""

EMPLOYEE_ROLE = "Employee"
TECHNICIAN_ROLE = "Technician"
COMPANY_ADMINISTRATOR_ROLE = "Company Administrator"
SYSTEM_ADMINISTRATOR_ROLE = "System Administrator"

# The only roles a Company Administrator may assign through user
# management (POST /users, PATCH /users/{id}). System Administrator is
# never assignable there - its single account is provisioned exclusively by
# app.scripts.seed_initial_data.
COMPANY_ROLE_NAMES: tuple[str, ...] = (
    EMPLOYEE_ROLE,
    TECHNICIAN_ROLE,
    COMPANY_ADMINISTRATOR_ROLE,
)

# The dedicated internal organization the System Administrator belongs to.
# Valid under validate_company_code_format, and can never collide with an
# auto-generated code (those always start with "IT-").
PLATFORM_COMPANY_NAME = "ITOnIT Platform Administration"
PLATFORM_COMPANY_CODE = "ITONIT-SYSTEM"

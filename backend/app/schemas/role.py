from pydantic import BaseModel, ConfigDict


class RoleResponse(BaseModel):
    """GET /roles item - a role's real database id and name. The frontend
    must use these ids for role_id, never a hardcoded mapping: ids depend on
    install history (see app.core.roles)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str

from fastapi import Header, HTTPException, Query, Depends
from typing import Optional, List

VALID_ROLES = ["requester", "agent", "lead", "admin"]

def get_current_role(
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    role_param: Optional[str] = Query(None, alias="role")
) -> str:
    """
    Extracts role from X-User-Role header or query parameter.
    Defaults to 'admin' for developer convenience if omitted.
    """
    role = (x_user_role or role_param or "admin").lower().strip()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{role}'. Allowed roles are: {VALID_ROLES}"
        )
    return role

def require_role(allowed_roles: List[str]):
    def role_checker(current_role: str = Depends(get_current_role)):
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access Denied: Role '{current_role}' lacks permissions for this action. Required: {allowed_roles}"
            )
        return current_role
    return role_checker

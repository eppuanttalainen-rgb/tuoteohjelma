import uuid
from typing import Annotated

from fastapi import Header

OrganizationId = Annotated[uuid.UUID, Header(alias="X-Organization-Id")]
ReviewerId = Annotated[str, Header(alias="X-Reviewer-Id", min_length=1, max_length=200)]

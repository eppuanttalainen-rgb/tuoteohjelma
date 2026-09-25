import uuid
from typing import Annotated

from fastapi import Header


OrganizationId = Annotated[uuid.UUID, Header(alias="X-Organization-Id")]

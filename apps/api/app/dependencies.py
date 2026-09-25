from typing import Annotated
import uuid

from fastapi import Header


OrganizationId = Annotated[uuid.UUID, Header(alias="X-Organization-Id")]

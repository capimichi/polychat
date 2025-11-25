from pydantic import BaseModel
from typing import Optional, List


class WebResultMetadata(BaseModel):
    client: Optional[str] = None
    date: Optional[str] = None
    citation_domain_name: Optional[str] = None
    suffix: Optional[str] = None
    domain_name: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None
    published_date: Optional[str] = None
    authors: Optional[List[str]] = None

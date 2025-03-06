from pydantic import BaseModel

class DataMountModel(BaseModel):
    path: str
    options: dict

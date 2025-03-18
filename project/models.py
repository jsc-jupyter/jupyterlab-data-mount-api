from pydantic import BaseModel


class DataMountOption(BaseModel):
    displayName: str
    template: str
    external: bool = False
    readonly: bool = False
    config: dict


class DataMountModel(BaseModel):
    path: str
    options: DataMountOption

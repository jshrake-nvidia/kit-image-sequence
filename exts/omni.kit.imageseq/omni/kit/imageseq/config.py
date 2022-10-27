import codecs
import pickle
from typing import List

from pxr import Sdf, Usd


class Config:
    path_glob: str
    expanded_glob: List[str]
    ppi: int
    gap_pct: float
    curve_pct: float
    images_per_row: int


def set_config_metadata(prim: Usd.Prim, config: Config) -> None:
    if not prim.IsValid():
        return
    config_str = codecs.encode(pickle.dumps(config), 'base64')
    attribute: Usd.Attribute= prim.GetAttribute("imageseq:config")
    if not attribute.IsValid():
        attribute = prim.CreateAttribute("imageseq:config", Sdf.ValueTypeNames.String)
    attribute.Set(config_str)

def get_config_metadata(prim: Usd.Prim) -> Config:
    if not prim.IsValid():
        raise Exception("programming error")
    attribute: Usd.Attribute = prim.GetAttribute("imageseq:config")
    if not attribute.IsValid():
        return None
    config_str = attribute.Get()
    config_bytes = codecs.decode(config_str.encode(), 'base64')
    config = pickle.loads(config_bytes)
    return config

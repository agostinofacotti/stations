import json
import os
from functools import partial
from collections import OrderedDict
from itertools import product, chain
from typing import List, Tuple


class json_property(property):
    _count = 0
    
    def __init__(self, fget=None, fset=None, fdel=None, doc=None, ord=0):
        super(json_property, self).__init__(fget=fget, fset=fset, fdel=fdel, doc=doc)
        self._idx = type(self)._count
        type(self)._count += 1
    
    def __int__(self) -> int:
        return self._idx


class Copan24Specs:
    def __init__(self,
                 nrows: int = 4,
                 ncols: int = 6,
                 brand: str = "COPAN",
                 brandId: List[str] = ["330C"],
                 diameter: float = 16.8,
                 distance_vert: float = 18,
                 distance_horz: float = 19,
                 tube_diameter: float = 14,
                 tube_volume: float = 14000,
                 tube_depth: float = 93,
                 tube_height: float = 15,
                 global_dimensions: Tuple[float, float, float] = (121.35, 79.1, 108),
                 a1_offset: Tuple[float, float] = (11.63, 14),
                 ):
        self.nrows = nrows
        self.ncols = ncols
        self._brand = brand
        self._brandId = brandId
        self._dims = global_dimensions
        self._a1_off = a1_offset
        self._d = diameter
        self._dv = distance_vert
        self._dh = distance_horz
        self._tw = tube_diameter
        self._td = tube_depth
        self._tv = tube_volume
        self._th = tube_height
    
    @property
    def n(self) -> int:
        return self.ncols * self.nrows

    @json_property
    def ordering(self) -> List[List[str]]:
        return [[chr(r + ord("A")) + str(c + 1) for r in range(self.nrows)] for c in range(self.ncols)]

    @json_property
    def brand(self) -> dict:
        return {"brand": self._brand, "brandId": self._brandId}

    @json_property
    def metadata(self) -> dict:
        return {
            "displayName": "COPAN {} Tube Rack 14000 µL".format(self.n),
            "displayCategory": "tubeRack",
            "displayVolumeUnits": "µL",
            "tags": []
        }

    @json_property
    def dimensions(self) -> dict:
        return {
            "xDimension": self._dims[0],
            "yDimension": self._dims[1],
            "zDimension": self._dims[2]
        }
    
    def well(self, r: int, c: int) -> Tuple[str, dict]:
        return chr(ord("A") + r) + str(1 + c), {
            "depth": self._td,
            "totalLiquidVolume": self._tv,
            "shape": "circular",
            "diameter": self._tw,
            "x": self._a1_off[0] + c * self._dh,
            "y": self._dims[1] - self._a1_off[1] - r * self._dv,
            "z": self._th
        }
        
    @json_property
    def wells(self) -> dict:
        return dict(self.well(r, c) for c, r in product(range(self.ncols), range(self.nrows)))
    
    @json_property
    def groups(self) -> List[dict]:
        return [{
            "metadata": {
                "displayName": "COPAN {} Tube Rack 14000 µL".format(self.n),
                "displayCategory": "tubeRack",
                "wellBottomShape": "v"
            },
            "brand": self.brand,
            "wells": list(chain.from_iterable(self.ordering)),
        }]

    @json_property
    def parameters(self) -> dict:
        return {
            "format": "irregular",
            "quirks": [],
            "isTiprack": False,
            "isMagneticModuleCompatible": False,
            "loadName": "copan_{}_tuberack_14000ul".format(self.n)
        }

    @json_property
    def namespace(self) -> str:
        return "custom_beta"

    @json_property
    def version(self) -> int:
        return 1

    @json_property
    def schemaVersion(self) -> int:
        return 2

    @json_property
    def cornerOffsetFromSlot(self) -> dict:
        return {
            "x": 0,
            "y": 0,
            "z": 0
        }
    
    def toJSON(self) -> dict:
        return OrderedDict((k, getattr(self, k)) for k in sorted(
            filter(lambda a: isinstance(getattr(type(self), a, None), json_property), dir(self)),
            key=lambda a: int(getattr(type(self), a, 0))
        ))
    
    def __str__(self) -> str:
        return json.dumps(self.toJSON(), indent=4).replace(r"\u00b5", "\u00b5")
        

if __name__ == "__main__":
    s = str(Copan24Specs())
    if len(os.sys.argv) > 1:
        with open(os.sys.argv[1], "w") as f:
            f.write(s)
    else:
        print(s)

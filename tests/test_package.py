import importlib.metadata
import importlib.resources as ir
import json

import numpy as np

import cloudlib
from cloudlib.thermo.thermfn import find_esat


def test_version():
    assert importlib.metadata.version("cloudlib")


def test_esat_at_freezing():
    # saturation vapour pressure at 273.15 K is about 611 Pa
    assert np.isclose(find_esat(273.15), 611.0, rtol=0.01)


def test_data_files_installed():
    data = ir.files("cloudlib") / "data"
    for name in ["dropgrow.json", "aero_nacl.json", "ammonium_sulphate.json"]:
        json.loads((data / name).read_text())
    for site in ["quillayute", "littlerock", "delrio"]:
        assert (data / site / "metadata.json").is_file()

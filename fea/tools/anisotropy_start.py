"""What Abaqus/CAE runs when a click on Anisotropy's site starts it (ADR-0094 amendment 1). `anisotropy_link.py` copies this file
into the coupon's folder as `anisotropy-start.py`, writes `anisotropy-start.json` beside it (the build script it fetched, the run it
came from, and the folder the connector's files are in), and starts `abaqus cae script=anisotropy-start.py` there.

This file reads those facts and hands them to the menu's module, which builds the coupon as File > Run Script would, puts it on the
screen, and from then on sends the results of that model's job back to its run when the job completes (`anisotropy_menu.py`). The
script it runs is one our writer wrote: the menu checks its first lines, as for Open from Anisotropy.
"""

import io
import json
import os
import sys

FACTS = "anisotropy-start.json"


def started() -> None:
    with io.open(os.path.join(os.getcwd(), FACTS), encoding="utf-8") as handle:
        facts = json.load(handle)
    folder = str(facts["connector"])
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import anisotropy_menu
    anisotropy_menu.opened_from_the_site(facts)


started()

"""Write a blank coupon input form: the Excel template an engineer fills in with the inputs of a coupon test (ADR-0046).

    uv run python tools/coupon_form.py                                  # .local/fea/forms/coupon-input-form.xlsx
    uv run python tools/coupon_form.py --out some/folder/form.xlsx

The form lists the library materials and the engine version at the time it is written, so write a fresh one for each delivery.
A filled-in form is read with tools/coupon_from_form.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.intake import FORM_VERSION, write_blank_form


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=paths.LOCAL / "forms" / "coupon-input-form.xlsx", help="where to write the form")
    args = parser.parse_args()
    path = write_blank_form(args.out)
    print(f"coupon input form {FORM_VERSION} written to {path}")


if __name__ == "__main__":
    main()

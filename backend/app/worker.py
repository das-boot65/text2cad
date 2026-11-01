"""Trusted subprocess entry point; all template input is schema validated."""

import json
import sys
from pathlib import Path


def main() -> None:
    if sys.argv[1] == "--probe":
        import cadquery as cq

        print(
            json.dumps(
                {
                    "cadquery": cq.__version__,
                    "valid": cq.Solid.makeBox(1, 1, 1).isValid(),
                }
            )
        )
        return
    from .cad import generate

    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    generate(json.loads(source.read_text(encoding="utf-8")), destination)


if __name__ == "__main__":
    main()

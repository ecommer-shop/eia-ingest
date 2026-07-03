"""Punto de entrada: python -m eia_ingest"""
import argparse
import json
import logging
import sys

from eia_ingest.sync import sync_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza el catalogo de productos (PostgreSQL) hacia Qdrant."
    )
    parser.add_argument(
        "--product-id",
        type=int,
        default=None,
        help="Sincronizar un solo producto por ID.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar logs detallados.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    result = sync_catalog(product_id=args.product_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("status") == "no_products":
        return 1
    if result.get("stats", {}).get("failed", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

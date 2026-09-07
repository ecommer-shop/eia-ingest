"""Entry point CLI para eia-sync.

Uso:
    eia-sync catalog                    # Sincronización completa del catálogo
    eia-sync catalog --product-id 42    # Sincronizar un producto específico
    eia-sync documents                  # Sincronizar PDFs (default: platform/policies)
    eia-sync documents --tenant-id X --folder company
    eia-sync ui-guides                  # Sincronizar guías markdown (default: platform/guides)
    eia-sync ui-guides --tenant-id X --folder guides
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser(
        description="eia-ingest: sincronización de datos hacia Qdrant"
    )
    sub = parser.add_subparsers(dest="command")

    # --- catalog ---
    cat = sub.add_parser("catalog", help="Sincronizar catálogo de PostgreSQL")
    cat.add_argument(
        "--product-id",
        type=int,
        default=None,
        help="ID de producto específico (default: sincronización completa)",
    )

    # --- documents ---
    doc = sub.add_parser("documents", help="Sincronizar PDFs")
    doc.add_argument("--tenant-id", default="platform", help="Tenant (default: platform)")
    doc.add_argument("--folder", default="policies", help="Subcarpeta (default: policies)")

    # --- ui-guides ---
    guide = sub.add_parser("ui-guides", help="Sincronizar guías markdown")
    guide.add_argument("--tenant-id", default="platform", help="Tenant (default: platform)")
    guide.add_argument("--folder", default="guides", help="Subcarpeta (default: guides)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    from eia_ingest.sync import sync_catalog, sync_documents, sync_ui_guides

    if args.command == "catalog":
        result = sync_catalog(product_id=args.product_id)
    elif args.command == "documents":
        result = sync_documents(tenant_id=args.tenant_id, folder=args.folder)
    elif args.command == "ui-guides":
        result = sync_ui_guides(tenant_id=args.tenant_id, folder=args.folder)

    print(result)


if __name__ == "__main__":
    main()

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="TrashSmart bottle component research tools")
    parser.add_argument("command", choices=["inventory", "audit-intake", "propose-bottles", "research-cycle", "export", "annotate", "train-detector", "train-material", "evaluate", "fetch-public", "import-spin", "package-training"])
    parser.add_argument("--data", type=Path, required=True, help="Dataset root (or prepared export for training)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=512)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--split", choices=["val", "test"], default="test")
    parser.add_argument("--limit", type=int, default=0, help="Public image limit; 0 downloads metadata only")
    parser.add_argument("--hash-images", action="store_true", help="Audit exact duplicate images by SHA256")
    parser.add_argument("--include-partial-materials", action="store_true", help="Export verified materials from reviewed partial annotations; incomplete bottles never train detector")
    args = parser.parse_args()
    from .data import inventory, export
    if args.command == "inventory":
        result = inventory(args.data)
    elif args.command == "research-cycle":
        if not args.output:
            parser.error("--output is required")
        from .research_cycle import run_cycle
        return run_cycle(args)
    elif args.command == "audit-intake":
        from .intake import audit_intake
        result = audit_intake(args.data, args.hash_images)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    elif args.command == "propose-bottles":
        if not args.output:
            parser.error("--output is required")
        from .proposals import propose_bottles
        result = propose_bottles(args.data, args.weights, args.output, args.batch, args.imgsz, args.threads, args.limit)
    elif args.command == "export":
        if not args.output:
            parser.error("--output is required")
        result = export(args.data, args.output, include_partial_materials=args.include_partial_materials)
    elif args.command == "package-training":
        if not args.output:
            parser.error("--output is required")
        from .packaging import package_training
        result = package_training(args.data, args.output)
    elif args.command == "annotate":
        from .annotate import serve
        return serve(args.data, args.port)
    elif args.command in ("fetch-public", "import-spin"):
        from .public_data import fetch_public, import_spin
        result = fetch_public(args.data, args.limit) if args.command == "fetch-public" else import_spin(args.data)
    else:
        if not args.output:
            parser.error("--output is required")
        from .training import train_detector, train_material, evaluate
        action = {"train-detector": train_detector, "train-material": train_material, "evaluate": evaluate}[args.command]
        result = action(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

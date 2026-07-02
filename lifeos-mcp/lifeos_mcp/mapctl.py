import argparse
import sys
from .config import load_settings, build_store, load_map, save_map


def run(argv, env=None) -> int:
    parser = argparse.ArgumentParser(prog="mapctl")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("push", "pull"):
        p = sub.add_parser(name)
        p.add_argument("--identity", required=True)
        p.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    settings = load_settings(env)
    store = build_store(settings)
    if args.cmd == "push":
        store.save(args.identity, load_map(args.file))
    else:  # pull
        save_map(store.load(args.identity), args.file)
    return 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

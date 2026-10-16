"""Estate housekeeping from the command line.

    python3 scripts/estate_admin.py list
    python3 scripts/estate_admin.py adopt <dataset> [--slug <slug>]
    python3 scripts/estate_admin.py wipe <slug>

`list` and `adopt` use the standard library only and run on the HOST, with
the stack stopped: adopt is how an install from the one-container-per-dataset
layout moves into the shared one, so it has to work before the new container
can start. `wipe` needs the app and runs inside the container (`make wipe`).
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from src import estates  # noqa: E402  (stdlib-only module)

# Where datasets/ and a pre-dataset .env live: the checkout, unless a test says otherwise.
CONFIG_DIR = os.environ.get("OE_CONFIG_DIR", REPO)
SITE_ENV = os.path.join(CONFIG_DIR, "datasets", "site.env")
# Settings that belong to the whole site. Everything else in an old dataset
# file (DATASET, DATASET_LABEL, DATASET_PROTECTED, DATABASE_URL) is per
# estate now, and lives in estates.json or nowhere.
SITE_KEYS = ("COMPOSE_PROJECT_NAME", "CONTAINER_NAME", "PORT", "BIND_ADDR", "PUID", "PGID",
             "SECRET_KEY", "ADMIN_PASSWORD", "FLASK_ENV")


def _root():
    return os.environ.get("ESTATES_ROOT") or os.path.join(REPO, "instance")


def _read_env(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_list(args):
    rows = estates.load(_root())
    if not rows:
        print("  (no estates yet - the container registers an empty 'demo' on first start)")
    for i, e in enumerate(rows):
        flags = ("protected" if e["protected"] else "") + (", default" if i == 0 else "")
        print(f"  {e['slug']:<20} {e['label']}  {('[' + flags.strip(', ') + ']') if flags else ''}")
    return 0


def cmd_adopt(args):
    """instance/<dataset>/estate.db (or a pre-dataset instance/estate.db)
    -> instance/estates/<slug>/, registered with the old file's label and
    protected flag. Moves, never copies: one estate, one file."""
    root = _root()
    slug = estates.check_slug(args.slug or args.dataset)
    if estates.get(root, slug):
        print(f"'{slug}' is already registered - nothing to do.", file=sys.stderr)
        return 1
    legacy = args.dataset == "legacy"
    src_dir = root if legacy else os.path.join(root, args.dataset)
    if not os.path.exists(os.path.join(src_dir, "estate.db")):
        print(f"Nothing to adopt: {os.path.join(src_dir, 'estate.db')} not found.", file=sys.stderr)
        return 1
    dest = estates.estate_dir(root, slug)
    if os.path.exists(dest):
        print(f"{dest} already exists - refusing to merge into it.", file=sys.stderr)
        return 1

    env_path = os.path.join(CONFIG_DIR, ".env" if legacy else os.path.join("datasets", f"{args.dataset}.env"))
    env = _read_env(env_path) if os.path.exists(env_path) else {}

    os.makedirs(dest)
    for name in os.listdir(src_dir):
        if name.startswith("estate.db") or (name == "backups" and not legacy):
            shutil.move(os.path.join(src_dir, name), os.path.join(dest, name))
    if not legacy and not os.listdir(src_dir):
        os.rmdir(src_dir)

    label = env.get("DATASET_LABEL") or slug
    protected = env.get("DATASET_PROTECTED") == "1"
    estates.add(root, slug, label, protected=protected)
    print(f"Adopted into instance/estates/{slug}/ as '{label}'"
          f"{' (protected)' if protected else ''}.")

    if not os.path.exists(SITE_ENV) and env:
        lines = ["# Written by estate_admin.py adopt from " + os.path.relpath(env_path, CONFIG_DIR),
                 "# Site-wide settings: one login, one port, every estate. See datasets/README.md."]
        lines += [f"{k}={env[k]}" for k in SITE_KEYS if k in env]
        fd = os.open(SITE_ENV, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Wrote datasets/site.env from {os.path.relpath(env_path, CONFIG_DIR)} "
              "(its password and key now open every estate).")
    elif env:
        print(f"datasets/site.env already exists; {os.path.relpath(env_path, CONFIG_DIR)} was not merged "
              "into it. Its password no longer applies - the site has one login.")
    if env:
        print(f"{os.path.relpath(env_path, CONFIG_DIR)} is no longer read; delete it once the stack is up.")
    return 0


def cmd_wipe(args):
    """Empty one estate: its database moves to backups/ (the way back), and
    the migrations build a fresh one. Refused on a protected estate."""
    root = _root()
    entry = estates.get(root, estates.check_slug(args.slug))
    if entry is None:
        print(f"No estate named '{args.slug}'.", file=sys.stderr)
        return 1
    try:
        estates.require_unprotected(entry, "wiped")
    except estates.EstateProtected as e:
        print(e, file=sys.stderr)
        return 1
    if not args.yes:
        reply = input(f"This empties estate '{args.slug}' ({entry['label']}). "
                      "Type its name to confirm: ")
        if reply.strip() != args.slug:
            print("Cancelled.")
            return 1
    folder = estates.estate_dir(root, args.slug)
    backups = os.path.join(folder, "backups")
    os.makedirs(backups, exist_ok=True)
    stamp = _stamp()
    for suffix in ("", "-wal", "-shm"):
        path = os.path.join(folder, "estate.db" + suffix)
        if os.path.exists(path):
            shutil.move(path, os.path.join(backups, f"estate-{stamp}-wiped.db{suffix}"))
    proc = subprocess.run([sys.executable, os.path.join(HERE, "upgrade_db.py"),
                           "--estate", args.slug], env={**os.environ, "ESTATES_ROOT": root})
    if proc.returncode == 0:
        print(f"Estate '{args.slug}' is empty. The old database is in "
              f"instance/estates/{args.slug}/backups/estate-{stamp}-wiped.db.")
    return proc.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a = sub.add_parser("adopt", help="move an old dataset folder into the estates layout")
    a.add_argument("dataset", help="the old dataset name (instance/<name>/), or 'legacy' "
                                   "for a pre-dataset instance/estate.db")
    a.add_argument("--slug", help="estate name to adopt it as (default: the dataset name)")
    w = sub.add_parser("wipe", help="empty one estate (refused when protected)")
    w.add_argument("slug")
    w.add_argument("--yes", action="store_true", help="skip the typed confirmation")
    args = ap.parse_args(argv)
    try:
        return {"list": cmd_list, "adopt": cmd_adopt, "wipe": cmd_wipe}[args.cmd](args)
    except estates.EstateError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

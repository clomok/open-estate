# Estates

One running app holds several estates: a demo set to build against, and one
per real trust. The **dropdown at the top of the sidebar** switches between
them, and the estate it shows is the estate every page, link and form on
screen belongs to.

Each estate is a separate SQLite file. Nothing in the schema knows about
estates (there are no tenant columns), so a query can only ever see the one
database it was handed:

```
instance/                      (gitignored)
  estates.json                 the registry: slug, label, protected
  estates/<slug>/estate.db     that estate's whole database
  estates/<slug>/backups/      copies taken before each migration and wipe
datasets/
  site.env                     the site: port, bind address, login (gitignored)
  site.env.example             its template (the only file here that is committed)
```

## How an estate is chosen

Every estate page lives under `/e/<slug>/`: `/e/demo/`, `/e/wheeler/timeline`,
`/e/family/settings/`. The estate is in the URL, not in a "current estate"
cookie, so two tabs on two estates stay two estates: a form left open on one
posts back to that one, even after another tab has switched. The bare address
`/` opens the estate used last, or the first in `estates.json`.

Under the hood `db.engines` (`src/extensions.py`) returns only the engine of
the estate the URL named, held in Flask's `g` for that one request. With no
estate named there is no engine at all, so code that forgets to say which
estate it means fails instead of guessing. `g` is per request context, which
makes the binding safe under gunicorn's processes *and* under threads.

`tests/test_estates.py` is the proof: writes land only in the estate their URL
names, a stale tab writes where it was rendered, two threads on two estates
never cross, and an unknown or malformed slug is a 404.

## The registry

`instance/estates.json`, written by the app, readable by hand:

```json
{
  "estates": [
    {"slug": "demo", "label": "Demo data", "protected": false},
    {"slug": "wheeler", "label": "The Wheeler Trust", "protected": true}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `slug` | Folder name and URL segment. Lowercase letters, digits, dashes; fixed once created |
| `label` | What the dropdown shows |
| `protected` | `true` on real data: seed, wipe and restore all refuse it |

The first entry is the default. **Protect** is a button on that estate's
Settings page and is one-way on purpose: lifting it is a hand edit of this file.
The refusal lives in the app (`src/estates.py: require_unprotected`), so the
dropdown, the Settings page, `make` and `ops.ps1` all hit the same guard.

## Creating one

From the sidebar: **+ New estate…**, give it a name and a short name. The app
builds its database by running the same migrator the container runs at start
(`scripts/upgrade_db.py --estate <slug>`), so a new estate has exactly the
schema and default rows (the transition playbook, the root trust on first use)
of an upgraded one. It starts empty.

## Running

The stack has one settings file and no per-estate commands, except the two
that act on one estate's data, which must name it:

```bash
cp datasets/site.env.example datasets/site.env   # once: fresh SECRET_KEY + ADMIN_PASSWORD
make up                       # start            (or: .\ops.ps1 -Run update)
make logs / make shell / make down
make estates                  # list the estates here
make seed ESTATE=demo         # load scripts/seed_example.py into one estate
make wipe ESTATE=demo         # empty one estate (old file kept in its backups/)
make test                     # no container, no estate
```

`make seed` passes `--estate` to the script, so a custom seed script given with
`FILE=` must accept `--estate <slug>` too. Generate secrets rather than
inventing them: `python -c "import secrets; print(secrets.token_hex(32))"`. The
app refuses to start while either is still at its template value.

**One login opens every estate on the site.** Several estates used to mean
several containers, each with its own password; one app has one. If someone
must see only one estate, that estate still belongs on its own site (its own
checkout and `site.env`).

## Moving real data in

Never through a seed script: real names, account numbers and coordinates do not
belong in a file under version control. Use the app's own durability layer.

1. **+ New estate…** in the sidebar, e.g. `family`.
2. On the install that holds the data today, **Settings → Download Backup**.
3. In the new estate, **Settings → Restore** with that zip.
4. **Settings → Protect this estate**.

The backup carries every table (see `src/services/backup_schema.py`, the
single list both the export and the restore read), and its file name carries
the estate it came from (`estate_<slug>_backup.zip`).

## Upgrading from one container per dataset

Before this layout each estate ran as its own container with
`datasets/<name>.env` and `instance/<name>/estate.db`. On start the new
container refuses that layout, naming the command that fixes it, rather than
starting empty beside the real data. On the host, with the old stack stopped:

```bash
make adopt DATASET=demo       # instance/demo/ -> instance/estates/demo/
make adopt DATASET=family     # keeps DATASET_LABEL and DATASET_PROTECTED
make up
```

`adopt` moves the database and its backups (never copies), registers the
estate with the old file's label and protected flag, and, the first time,
writes `datasets/site.env` from that dataset's port, bind address, user and
secrets. The old `datasets/<name>.env` is then no longer read; delete it once
the stack is up. `DATASET=legacy` adopts a pre-dataset `instance/estate.db`
and `.env`. It is standard-library Python and runs before the container exists
(`python3 scripts/estate_admin.py adopt <name>` on a host without `make`).

# Datasets

One estate per instance. The app is single-tenant by design — a singleton
`TrustProfile`, one admin password, one database — so separate estates are kept
apart by running separate containers rather than by adding tenant columns to
every table. Nothing in the application code knows about datasets; the whole
mechanism is a file per instance and a mount per instance.

Each dataset is one file here, `datasets/<name>.env`, which decides:

| Setting | What it separates |
| --- | --- |
| `DATASET` | Container name, Compose project, and the host directory the database lives in (`instance/<DATASET>/`) |
| `PORT` | Which port this estate answers on, so several run side by side |
| `SECRET_KEY`, `ADMIN_PASSWORD` | Its own login — one estate's password opens no other |
| `DATASET_LABEL` | The badge in the sidebar, so the tab identifies itself before you edit it |
| `DATASET_PROTECTED` | `1` on real data: `wipe` and `seed` refuse outright |

`DATABASE_URL` is deliberately identical in every dataset. The path inside the
container never changes; the Compose mount is the only thing that decides which
estate loads. One place to get right instead of two.

Only `demo.env.example` is committed. Every real `*.env` is gitignored, along
with `instance/`, so no password, key or estate can ride along in a push.

## Creating one

```bash
make new DATASET=demo        # copies the template, makes instance/demo/
$EDITOR datasets/demo.env    # set DATASET, a unique PORT, fresh secrets
make up DATASET=demo
```

Generate the secrets rather than inventing them, once per dataset:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

The app refuses to start while `SECRET_KEY` or `ADMIN_PASSWORD` is still at its
template value, so a half-filled file fails loudly at boot instead of quietly
serving an estate with a known password.

## Running

Every command names its dataset — there is no default:

```bash
make up DATASET=demo         # start        (or: .\ops.ps1 -Dataset demo -Run update)
make logs DATASET=demo       # tail logs
make shell DATASET=demo      # container shell
make down DATASET=demo       # stop
make seed DATASET=demo       # load scripts/seed_example.py
make wipe DATASET=demo       # delete every record, rebuild the schema
make list                    # what datasets exist here
```

Under the hood each of these is `docker compose --env-file datasets/<name>.env`.
Omitting `DATASET` is an error, not a default — picking the wrong estate by
omission is the mistake this layout exists to prevent.

## Moving real data in

Never through a seed script: real names, account numbers and coordinates do not
belong in a file under version control. Use the app's own durability layer.

1. Stand the dataset up empty: `make new DATASET=family && make up DATASET=family`
2. Log in and go to **Settings → Download Backup** on the instance that holds
   the data today.
3. On the new instance, **Settings → Restore** with that same zip.
4. Set `DATASET_PROTECTED=1` in `datasets/family.env` and restart.

The backup carries every table, including beneficiary shares, recurring bills,
location points and the trust profile — see `src/services/backup_schema.py`,
which is the single list both the export and the restore read.

## Suggested layout

| Dataset | Label | Protected | Port |
| --- | --- | --- | --- |
| `demo` | `DEMO DATA` | no | 5000 |
| `family` | `FAMILY — LIVE` | yes | 5001 |
| `client` | `CLIENT — LIVE` | yes | 5002 |

## Upgrading an install that predates datasets

An older checkout keeps its database at `instance/estate.db` and its settings in
`.env`. Compose now requires a named dataset, so move the old install into one:

```bash
make adopt DATASET=family    # moves instance/estate.db* and copies .env
$EDITOR datasets/family.env  # add DATASET, COMPOSE_PROJECT_NAME, PORT, DATASET_PROTECTED
make up DATASET=family
```

Do this before the next pull-and-redeploy on any live host — the stack will
refuse to start with `DATASET is not set` until the dataset file exists.

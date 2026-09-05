"""Pure calculation helpers, free of the ORM and the request cycle.

`fcm` / `fcm_auth` are the modules here that talk to the network; they still
touch no model, which is what `docs/code-standards.md` -> Layering actually
forbids.

NOTHING IS RE-EXPORTED FLAT. Every call site imports by module path
(`from giapha.services.fcm import send_multicast`), which keeps the origin of
a name visible and -- for `fcm` -- keeps `requests` out of the import graph of
every module that merely touches `giapha.services`.
"""

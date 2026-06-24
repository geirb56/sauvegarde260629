"""Garmin connector package (invisible, OAuth-like experience).

All Garmin-specific logic is encapsulated inside this package behind a
Provider abstraction. No Garmin logic must exist outside this layer.

- providers/      : Provider abstraction + Mock and Gccli implementations
- runner.py       : Isolated GccliRunner (encapsulates the gccli binary)
- vault.py        : Ephemeral, in-memory credential vault (never persisted)
- factory.py      : Selects the active provider via env GARMIN_PROVIDER
- service.py       : Orchestration (connect / sync / status / disconnect)
"""

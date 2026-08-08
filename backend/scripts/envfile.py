"""Write a single key into backend/.env, in place.

Setup scripts use this so a credential can go straight into the env file
instead of being printed to a terminal, copied through a clipboard, and
left in scrollback. The refresh token in particular is a full read-write
grant to the owner's calendar and should be seen by as little as possible.
"""

from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def set_key(name: str, value: str, path: Path = ENV_PATH) -> Path:
    """Replace `name`'s line, or append it if the key is not there yet."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated, replaced = [], False
    for line in lines:
        if line.startswith(f"{name}="):
            updated.append(f"{name}={value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"{name}={value}")
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return path

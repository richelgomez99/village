"""Release gate (FS-5): build in Daytona, tap with Anchor, score with Arize, then go live (blue/green)."""
from core.release.pipeline import release_id, run_release

__all__ = ["run_release", "release_id"]

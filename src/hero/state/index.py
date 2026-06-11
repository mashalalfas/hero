"""IndexState — master sandbox registry management."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hero.state.toon import toon_read, toon_write
from hero.core.locks import FileLock


HOME = Path.home()
SANDBOX_DIR = HOME / ".hero" / "sandboxes"
INDEX_FILE = SANDBOX_DIR / "INDEX.toon"


@dataclass
class SandboxEntry:
    """Single sandbox entry in the index."""
    name: str
    path: str
    budget_max: int
    skills_count: int
    status: str
    last_seen: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class IndexData:
    """Index file data structure."""
    sandboxes: list[SandboxEntry] = field(default_factory=list)
    version: str = "1.0.0"


class IndexState:
    """Manages the master sandbox registry (INDEX.toon)."""
    
    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or SANDBOX_DIR
        self.index_file = self.base_path / "INDEX.toon"
    
    def load(self) -> dict[str, Any]:
        """Load the index file and return its data as a dict."""
        if not self.index_file.exists():
            return {"sandboxes": [], "version": "1.0.0"}
        
        data = toon_read(self.index_file)
        
        # Normalize structure
        if "sandboxes" not in data:
            data["sandboxes"] = []
        if "version" not in data:
            data["version"] = "1.0.0"
        
        return data
    
    def save(self, data: dict[str, Any]) -> None:
        """Save data to the index file under a file lock."""
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Ensure required keys
        if "sandboxes" not in data:
            data["sandboxes"] = []
        if "version" not in data:
            data["version"] = "1.0.0"

        with FileLock("sandbox_index"):
            toon_write(self.index_file, data)
    
    def add_sandbox(self, name: str, path: str, budget_max: int = 5000) -> None:
        """Add or update a sandbox entry in the index."""
        data = self.load()
        
        # Check if sandbox already exists
        existing = None
        for sb in data["sandboxes"]:
            if sb.get("name") == name:
                existing = sb
                break
        
        entry = {
            "name": name,
            "path": path,
            "budget_max": budget_max,
            "skills_count": 0,
            "status": existing.get("status", "idle") if existing else "idle",
            "last_seen": datetime.utcnow().isoformat(),
        }
        
        if existing:
            # Update existing
            for k, v in entry.items():
                existing[k] = v
        else:
            data["sandboxes"].append(entry)
        
        self.save(data)
    
    def remove_sandbox(self, name: str) -> bool:
        """Remove a sandbox from the index. Returns True if found and removed."""
        data = self.load()
        
        original_len = len(data["sandboxes"])
        data["sandboxes"] = [sb for sb in data["sandboxes"] if sb.get("name") != name]
        
        if len(data["sandboxes"]) < original_len:
            self.save(data)
            return True
        return False
    
    def get_sandbox(self, name: str) -> dict[str, Any] | None:
        """Get a specific sandbox entry by name."""
        data = self.load()
        for sb in data["sandboxes"]:
            if sb.get("name") == name:
                return sb
        return None
    
    def list_sandboxes(self) -> list[dict[str, Any]]:
        """Return all sandbox entries."""
        data = self.load()
        return data.get("sandboxes", [])
    
    def update_last_seen(self, name: str) -> None:
        """Update the last_seen timestamp for a sandbox."""
        data = self.load()
        for sb in data["sandboxes"]:
            if sb.get("name") == name:
                sb["last_seen"] = datetime.utcnow().isoformat()
                break
        self.save(data)
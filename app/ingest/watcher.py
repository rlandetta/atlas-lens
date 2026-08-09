from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Iterable

from app.config import FLOW_WATCH_DIRECTORIES, FLOW_WATCH_INTERVAL_SECONDS, INGEST_SESSION_TIMEOUT_MINUTES, INGEST_STORE_PATH
from app.ingest.service import IngestService
from app.ingest.store import IngestStore

LOGGER = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".jpg", ".jpeg"}


class IngestWatcher:
    def __init__(self, service: IngestService, directories: Iterable[str | Path], *, logger: logging.Logger | None = None):
        self.service = service
        self.directories = [Path(directory) for directory in directories]
        self.logger = logger or LOGGER
        self.pending_sizes: dict[str, int] = {}
        self.warned_missing: set[str] = set()
        self.logged_observed: set[str] = set()

    def scan_once(self) -> list[dict]:
        registered = []
        known_paths = self.registered_paths()
        for directory in self.directories:
            if not directory.is_dir():
                self.warn_missing_directory(directory)
                continue
            self.log_observing(directory)
            for candidate in sorted(directory.iterdir()):
                if not self.is_supported_image(candidate):
                    continue
                path_key = str(candidate.resolve())
                if path_key in known_paths:
                    self.pending_sizes.pop(path_key, None)
                    continue
                if not self.is_stable(candidate, path_key):
                    continue
                try:
                    photo = self.service.register_received_photo({
                        "filename": candidate.name,
                        "path": path_key,
                        "source": directory.name,
                        "received_at": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as error:
                    self.logger.warning("FLOW: error controlado %s", error)
                    continue
                self.pending_sizes.pop(path_key, None)
                known_paths.add(path_key)
                registered.append(photo)
                self.logger.info(
                    "FLOW: fotografía recibida %s source=%s session=%s",
                    candidate.name,
                    directory.name,
                    photo.get("session_id", ""),
                )
        return registered

    def run_forever(self, *, interval_seconds: int = FLOW_WATCH_INTERVAL_SECONDS) -> None:
        self.log_startup_summary(interval_seconds=interval_seconds)
        while True:
            self.scan_once()
            time.sleep(interval_seconds)

    def log_startup_summary(self, *, interval_seconds: int) -> None:
        summary, available_count, missing_directories = self.startup_summary(interval_seconds=interval_seconds)
        for directory in self.directories:
            if directory.is_dir():
                self.logged_observed.add(str(directory))
        for directory in missing_directories:
            self.warned_missing.add(str(directory))
        if missing_directories:
            self.logger.warning(summary)
        else:
            self.logger.info(summary)

    def startup_summary(self, *, interval_seconds: int) -> tuple[str, int, list[Path]]:
        lines = ["ATLAS FLOW WATCHER", "------------------"]
        available_count = 0
        missing_directories = []
        for directory in self.directories:
            camera = directory.name
            if directory.is_dir():
                available_count += 1
                lines.extend([f"✓ {camera}", f"  {directory}", ""])
            else:
                missing_directories.append(directory)
                lines.extend([f"⚠ {camera}", "  carpeta no disponible", f"  {directory}", ""])
        lines.extend([f"Watching: {available_count} camera(s)", f"Polling: {interval_seconds} s"])
        return "\n".join(lines), available_count, missing_directories

    def registered_paths(self) -> set[str]:
        return {str(photo.get("path", "")) for photo in self.service.store.list_photos() if str(photo.get("path", ""))}

    def is_stable(self, path: Path, path_key: str) -> bool:
        try:
            size = path.stat().st_size
        except OSError as error:
            self.logger.warning("FLOW: error controlado %s", error)
            return False
        previous_size = self.pending_sizes.get(path_key)
        self.pending_sizes[path_key] = size
        return previous_size == size

    def warn_missing_directory(self, directory: Path) -> None:
        key = str(directory)
        if key not in self.warned_missing:
            self.logger.warning("FLOW: carpeta no disponible %s", directory)
            self.warned_missing.add(key)

    def log_observing(self, directory: Path) -> None:
        key = str(directory)
        if key not in self.logged_observed:
            self.logger.info("FLOW: observando %s", directory)
            self.logged_observed.add(key)

    @staticmethod
    def is_supported_image(path: Path) -> bool:
        return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def build_ingest_watcher(
    *,
    store_path: str | Path = INGEST_STORE_PATH,
    directories: Iterable[str | Path] = FLOW_WATCH_DIRECTORIES,
    session_timeout_minutes: int = INGEST_SESSION_TIMEOUT_MINUTES,
) -> IngestWatcher:
    store = IngestStore(store_path)
    service = IngestService(store, session_timeout_minutes=session_timeout_minutes)
    return IngestWatcher(service, directories)


def run_ingest_watcher() -> None:
    build_ingest_watcher().run_forever(interval_seconds=FLOW_WATCH_INTERVAL_SECONDS)

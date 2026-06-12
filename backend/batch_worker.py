import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


SUPPORTED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")


class BatchWorker:
    def __init__(
        self,
        convert_file: Callable[[Path, str], Dict[str, Any]],
        get_pipeline_name: Optional[Callable[[], str]] = None,
    ) -> None:
        self._convert_file = convert_file
        self._get_pipeline_name = get_pipeline_name or (lambda: "OCR_None_LLM_Unspecified")
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._config: Dict[str, Any] = self._default_config()
        self._items: List[Dict[str, Any]] = []
        self._totals = {"processed": 0, "failed": 0}
        self._current_file = ""
        self._last_error = ""
        self._run_dir = ""
        self._result_dir = ""
        self._pipeline_name = ""
        self._seen_inputs = set()
        self._planned_count = 0

    def _default_config(self) -> Dict[str, Any]:
        return {
            "inputDir": "",
            "outputDir": "",
            "mode": "customdb",
            "keepInputFiles": False,
            "usePipelineName": False,
        }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "config": dict(self._config),
                "runDir": self._run_dir,
                "resultDir": self._result_dir,
                "pipelineName": self._pipeline_name,
                "currentFile": self._current_file,
                "lastError": self._last_error,
                "totals": dict(self._totals),
                "plannedCount": self._planned_count,
                "items": list(self._items[-100:]),
            }

    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        clean = self._clean_config(config)
        with self._lock:
            self._config.update(clean)
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        return self.status()

    def run_once(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if config:
            self.configure(config)
        self._validate_config()
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._stop_event.clear()
        self._prepare_run_folder()
        with self._lock:
            self._thread = threading.Thread(target=self._run_once_loop, name="batch-run-once", daemon=True)
            self._thread.start()
        return self.status()

    def _clean_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        clean: Dict[str, Any] = {}
        for key in ("inputDir", "outputDir", "mode"):
            value = config.get(key)
            if value is not None:
                clean[key] = str(value).strip()
        for key in ("keepInputFiles", "usePipelineName"):
            if key not in config:
                continue
            value = config.get(key)
            if isinstance(value, str):
                clean[key] = value.strip().lower() in ("1", "true", "yes", "on")
            else:
                clean[key] = bool(value)
        return clean

    def _resolved_config(self) -> Dict[str, Any]:
        with self._lock:
            config = dict(self._config)
            run_dir = self._run_dir
            result_dir = self._result_dir
        input_dir = Path(config.get("inputDir", "")).expanduser()
        output_dir = Path(config.get("outputDir", "")).expanduser()
        run_path = Path(run_dir).expanduser() if run_dir else None
        result_path = Path(result_dir).expanduser() if result_dir else None
        return {
            **config,
            "inputPath": input_dir,
            "outputPath": output_dir,
            "runPath": run_path,
            "resultPath": result_path,
            "processedPath": run_path / "processed" if run_path else None,
            "logPath": run_path / "batch.log" if run_path else None,
            "errorLogPath": run_path / "errors.log" if run_path else None,
        }

    def _validate_config(self) -> None:
        config = self._resolved_config()
        if not str(config["inputDir"]).strip():
            raise ValueError("Batch input folder is required")
        if not str(config["outputDir"]).strip():
            raise ValueError("Batch output folder is required")
        if not config["inputPath"].exists() or not config["inputPath"].is_dir():
            raise ValueError(f"Batch input folder does not exist: {config['inputPath']}")
        config["outputPath"].mkdir(parents=True, exist_ok=True)

    def _prepare_run_folder(self) -> None:
        config = self._resolved_config()
        now = datetime.now()
        folder_stamp = now.strftime("%Y-%m-%d")
        log_stamp = now.strftime("%Y-%m-%d %H:%M:%S")
        run_path = config["outputPath"] / f"batch_{folder_stamp}"
        pipeline_name = self._get_pipeline_name()
        result_folder_name = pipeline_name if config.get("usePipelineName") else "output"
        result_path = run_path / result_folder_name
        processed_path = run_path / "processed"
        result_path.mkdir(parents=True, exist_ok=True)
        processed_path.mkdir(parents=True, exist_ok=True)
        with (run_path / "batch.log").open("a", encoding="utf-8") as handle:
            handle.write(
                f"\nBatch started: {log_stamp}\nPipeline: {pipeline_name}\nResult folder: {result_folder_name}\n"
            )
        (run_path / "errors.log").touch(exist_ok=True)
        with self._lock:
            self._run_dir = str(run_path)
            self._result_dir = str(result_path)
            self._pipeline_name = pipeline_name
            self._seen_inputs = set()
            self._planned_count = 0
            self._totals = {"processed": 0, "failed": 0}
            self._items = []
            self._current_file = ""
            self._last_error = ""

    def _run_once_loop(self) -> None:
        try:
            self._scan_once()
        except Exception as exc:  # noqa: BLE001
            self._set_last_error(str(exc))
        finally:
            with self._lock:
                self._current_file = ""

    def _scan_once(self) -> None:
        config = self._resolved_config()
        if not config["runPath"]:
            self._prepare_run_folder()
            config = self._resolved_config()
        files = sorted(
            p for p in config["inputPath"].iterdir()
            if (
                p.is_file()
                and p.suffix.lower() in SUPPORTED_EXTENSIONS
                and self._file_ready(p)
                and not self._already_processed_in_run(p, config)
            )
        )
        self._set_planned_count(len(files))
        for file_path in files:
            if self._stop_event.is_set():
                break
            self._process_file(file_path, config)

    def _file_ready(self, path: Path) -> bool:
        try:
            return (time.time() - path.stat().st_mtime) >= 1
        except OSError:
            return False

    def _process_file(self, file_path: Path, config: Dict[str, Any]) -> None:
        self._set_current_file(file_path.name)
        started = time.time()
        try:
            result = self._convert_file(file_path, str(config.get("mode") or "customdb"))
            output_path = self._unique_path(config["resultPath"] / f"{file_path.stem}.json")
            output_path.write_text(json.dumps(result["result"], ensure_ascii=False, indent=2), encoding="utf-8")
            archive_path = self._archive_file(file_path, config)
            self._mark_processed_in_run(file_path, config)
            self._append_log(config["logPath"], f"OK {file_path.name} -> {output_path}")
            self._record_item(
                {
                    "file": file_path.name,
                    "status": "completed",
                    "output": str(output_path),
                    "archive": str(archive_path),
                    "durationSeconds": round(time.time() - started, 2),
                }
            )
            with self._lock:
                self._totals["processed"] += 1
                self._last_error = ""
        except Exception as exc:  # noqa: BLE001
            self._set_last_error(str(exc))
            error_path = self._archive_file(file_path, config)
            self._mark_processed_in_run(file_path, config)
            self._append_log(config["errorLogPath"], f"FAILED {file_path.name}: {exc}")
            self._append_log(config["logPath"], f"FAILED {file_path.name}: {exc}")
            self._record_item(
                {
                    "file": file_path.name,
                    "status": "failed",
                    "error": str(exc),
                    "archive": str(error_path) if error_path else "",
                    "durationSeconds": round(time.time() - started, 2),
                }
            )
            with self._lock:
                self._totals["failed"] += 1
        finally:
            self._set_current_file("")

    def _archive_file(self, file_path: Path, config: Dict[str, Any]) -> Optional[Path]:
        if not file_path.exists():
            return None
        target = self._unique_path(config["processedPath"] / file_path.name)
        if config.get("keepInputFiles"):
            shutil.copy2(str(file_path), str(target))
        else:
            shutil.move(str(file_path), str(target))
        return target

    def _already_processed_in_run(self, path: Path, config: Dict[str, Any]) -> bool:
        if not config.get("keepInputFiles"):
            return False
        signature = self._input_signature(path)
        with self._lock:
            return signature in self._seen_inputs

    def _mark_processed_in_run(self, path: Path, config: Dict[str, Any]) -> None:
        if not config.get("keepInputFiles"):
            return
        signature = self._input_signature(path)
        with self._lock:
            self._seen_inputs.add(signature)

    def _input_signature(self, path: Path) -> str:
        try:
            stat = path.stat()
            resolved = path.resolve()
            return f"{resolved}|{stat.st_size}|{stat.st_mtime_ns}"
        except OSError:
            return str(path)

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        for idx in range(1, 10000):
            candidate = parent / f"{stem}_{idx}{suffix}"
            if not candidate.exists():
                return candidate
        raise ValueError(f"Could not create unique output path for {path}")

    def _record_item(self, item: Dict[str, Any]) -> None:
        with self._lock:
            item["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._items.append(item)
            self._items = self._items[-200:]

    def _append_log(self, path: Optional[Path], message: str) -> None:
        if not path:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {message}\n")

    def _set_current_file(self, file_name: str) -> None:
        with self._lock:
            self._current_file = file_name

    def _set_last_error(self, error: str) -> None:
        with self._lock:
            self._last_error = error

    def _set_planned_count(self, discovered_count: int) -> None:
        with self._lock:
            done_count = self._totals.get("processed", 0) + self._totals.get("failed", 0)
            self._planned_count = max(self._planned_count, done_count + discovered_count)

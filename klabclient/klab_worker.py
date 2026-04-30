import asyncio
import os
import shutil
import subprocess
import sys
import tempfile

from qgis.PyQt.QtCore import QThread, pyqtSignal


class KlabInstallWorker(QThread):
    """Installs klab-client-py into the plugin's own deps/ directory.

    Using --target avoids both the need for root and the PEP 668
    externally-managed-environment restriction present on Debian/Ubuntu.
    """

    installResult = pyqtSignal(bool, str)

    def run(self):
        python = _find_python()
        deps_dir = _deps_dir()
        os.makedirs(deps_dir, exist_ok=True)
        try:
            result = subprocess.run(
                [python, "-m", "pip", "install", "klab-client-py", "--target", deps_dir],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if result.returncode == 0:
                _refresh_sys_path(deps_dir)
                self.installResult.emit(True, "klab-client-py installed successfully")
            else:
                msg = (result.stderr or result.stdout or "pip exited with errors").strip()
                self.installResult.emit(False, msg)
        except subprocess.TimeoutExpired:
            self.installResult.emit(False, "Installation timed out (>3 min)")
        except Exception as exc:
            self.installResult.emit(False, str(exc))


class KlabConnectionWorker(QThread):
    """Tests k.lab engine connectivity in a background thread."""

    connectionResult = pyqtSignal(bool, str)

    def __init__(self, credentials):
        super().__init__()
        self._credentials = credentials

    def run(self):
        tmp = None
        try:
            from klab.klab import Klab  # noqa: PLC0415
            tmp = _write_credentials_file(self._credentials)
            klab = Klab.create(credentialsFile=tmp)
            if klab and klab.isOnline():
                url = _engine_url(klab)
                klab.close()
                self.connectionResult.emit(True, f"Connected to {url}")
            else:
                self.connectionResult.emit(False, "Engine is not online")
        except ImportError:
            self.connectionResult.emit(
                False, "klab-client-py not installed — run: pip install klab-client-py"
            )
        except Exception as exc:
            self.connectionResult.emit(False, str(exc))
        finally:
            _remove(tmp)


class KlabObservationWorker(QThread):
    """Runs a k.lab observation and exports the result in a background thread.

    Emits:
        log(str)                        — progress messages
        observationFinished(path, type) — path to temp file, type is 'raster' or 'vector'
        observationError(str)           — error description
    """

    log = pyqtSignal(str)
    observationFinished = pyqtSignal(str, str)
    observationError = pyqtSignal(str)

    def __init__(self, credentials, observable, polygon_wkt, resolution, year,
                 export_format="auto"):
        super().__init__()
        self._credentials = credentials
        self._observable = observable
        self._polygon_wkt = polygon_wkt
        self._resolution = resolution
        self._year = year
        self._export_format = export_format  # "auto" | "raster" | "vector"
        self._cancelled = False
        self._loop = None

    def stop(self):
        """Request cancellation of the running observation."""
        self._cancelled = True
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def run(self):
        self._cancelled = False
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._observe())
        except Exception as exc:
            if not self._cancelled:
                self.observationError.emit(f"Worker error: {exc}")
        finally:
            loop.close()
            self._loop = None

    async def _observe(self):
        klab = None
        tmp_cred = None
        try:
            from klab.klab import Klab  # noqa: PLC0415
            from klab.geometry import GeometryBuilder
            from klab.observable import Observable
            from klab.utils import Export, ExportFormat
        except ImportError:
            self.observationError.emit(
                "klab-client-py not installed — run: pip install klab-client-py"
            )
            return

        try:
            tmp_cred = _write_credentials_file(self._credentials)

            self.log.emit("Connecting to k.lab engine…")
            klab = Klab.create(credentialsFile=tmp_cred)
            if not klab or not klab.isOnline():
                self.observationError.emit("Could not connect to k.lab engine")
                return
            self.log.emit(f"Connected to {_engine_url(klab)}")

            self.log.emit(
                f"Context: {self._polygon_wkt} | {self._resolution} | year {self._year}"
            )
            region = Observable.create("earth:Region")
            grid = (
                GeometryBuilder()
                .grid(urn=self._polygon_wkt, resolution=self._resolution)
                .years(self._year)
                .build()
            )

            self.log.emit("Submitting context…")
            context = await (klab.submit(region, grid)).get()
            if context is None:
                self.observationError.emit("Failed to create context")
                return

            self.log.emit(f"Context ready. Observing: {self._observable}")
            data_obs = Observable.create(self._observable)
            observation = await (context.submit(data_obs)).get()

            if observation is None:
                self.observationError.emit("Observation returned None")
                return
            if observation.isEmpty():
                self.observationError.emit(
                    "Observation is empty — the engine could not resolve the observable"
                )
                return

            if self._export_format in ("auto", "raster"):
                self.log.emit("Exporting as GeoTIFF (raster)…")
                tif = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
                tif.close()
                try:
                    ok = observation.exportToFile(Export.DATA, ExportFormat.BYTESTREAM, tif.name)
                except Exception as exc:
                    self.log.emit(f"Raster export raised: {exc}")
                    ok = False
                if ok:
                    self.log.emit(f"Raster saved: {tif.name}")
                    self.observationFinished.emit(tif.name, "raster")
                    return
                _remove(tif.name)
                if self._export_format == "raster":
                    self.observationError.emit("GeoTIFF export failed for this observation")
                    return
                self.log.emit("Raster export failed — trying GeoJSON…")

            if self._export_format in ("auto", "vector"):
                self.log.emit("Exporting as GeoJSON (vector)…")
                try:
                    geojson = observation.exportToString(Export.DATA, ExportFormat.GEOJSON_FEATURES)
                except Exception as exc:
                    self.log.emit(f"Vector export raised: {exc}")
                    geojson = None
                if geojson:
                    geojson = _ensure_feature_collection(geojson)
                    gjf = tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False)
                    gjf.write(geojson)
                    gjf.close()
                    self.log.emit(f"Vector saved: {gjf.name}")
                    self.observationFinished.emit(gjf.name, "vector")
                    return
                if self._export_format == "vector":
                    self.observationError.emit("GeoJSON export failed for this observation")
                    return

            self.observationError.emit(
                "Could not export observation — both GeoTIFF and GeoJSON exports failed"
            )

        except Exception as exc:
            self.observationError.emit(f"Observation error: {exc}")
        finally:
            if klab:
                try:
                    klab.close()
                except Exception:
                    pass
            _remove(tmp_cred)


# ── helpers ──────────────────────────────────────────────────────────────────

def _write_credentials_file(creds):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".properties", delete=False)
    f.write(f"username={creds.get('username', '')}\n")
    f.write(f"password={creds.get('password', '')}\n")
    if creds.get("engine"):
        f.write(f"engine={creds['engine']}\n")
    f.close()
    return f.name


def _engine_url(klab):
    return getattr(getattr(klab, "engine", None), "url", "unknown")


def _remove(path):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except Exception:
            pass


def _deps_dir():
    """Absolute path to the plugin's local dependency directory."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "deps")


def _find_python():
    """Return the Python executable that pip can use from within QGIS."""
    exe = sys.executable
    # On Linux/Mac sys.executable is already the Python interpreter
    if "python" in os.path.basename(exe).lower():
        return exe
    # On Windows sys.executable may be qgis-bin.exe — look beside it
    exe_dir = os.path.dirname(exe)
    for name in ("python3.exe", "python.exe", "python3", "python"):
        candidate = os.path.join(exe_dir, name)
        if os.path.exists(candidate):
            return candidate
    # Last resort: whatever is on PATH
    return shutil.which("python3") or shutil.which("python") or "python3"


def _ensure_feature_collection(geojson_str):
    """Wrap a bare Feature array into a proper GeoJSON FeatureCollection."""
    import json
    try:
        data = json.loads(geojson_str)
        if isinstance(data, list):
            return json.dumps({"type": "FeatureCollection", "features": data})
        if isinstance(data, dict) and data.get("type") == "Feature":
            return json.dumps({"type": "FeatureCollection", "features": [data]})
    except Exception:
        pass
    return geojson_str  # already valid or unparseable — return as-is


def _refresh_sys_path(deps_dir):
    """Make the newly populated deps/ directory importable without a restart."""
    import importlib

    if deps_dir not in sys.path:
        sys.path.insert(0, deps_dir)
    importlib.invalidate_caches()

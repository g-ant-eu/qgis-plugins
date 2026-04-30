from qgis.PyQt.QtWidgets import QDialog, QAction
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.core import (
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsUnitTypes,
)
from qgis.utils import iface

from .klabclient_dialog import Ui_Dialog
from .klab_worker import KlabConnectionWorker, KlabInstallWorker, KlabObservationWorker
from .ui import IconKlabClient


class KlabClientPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(IconKlabClient, "k.lab Client", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&G-ANT", self.action)
        self.iface.addToolBarIcon(self.action)
        self.dialog = None

    def unload(self):
        if self.dialog:
            del self.dialog
            self.dialog = None
        self.iface.removePluginMenu("&G-ANT", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if not self.dialog:
            self.dialog = KlabClientDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()


class KlabClientDialog(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self._obs_worker = None
        self._conn_worker = None
        self._install_worker = None

        self.setupUi(self)
        self.setWindowTitle("k.lab Client")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._load_settings()
        self._connect_signals()
        self._update_extent_ui()
        self._check_klab()

    # ------------------------------------------------------------------ #
    # Dependency check + auto-install                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _klab_available():
        try:
            import klab  # noqa: F401
            return True
        except ImportError:
            return False

    def _check_klab(self):
        available = self._klab_available()
        self.installBanner.setVisible(not available)
        self.submitButton.setEnabled(available)

    def _on_install(self):
        self.installButton.setEnabled(False)
        self.installStatusLabel.setText("Installing klab-client-py…")
        self._install_worker = KlabInstallWorker()
        self._install_worker.installResult.connect(self._on_install_result)
        self._install_worker.finished.connect(self._install_worker.deleteLater)
        self._install_worker.start()

    def _on_install_result(self, success, message):
        if success:
            self.installBanner.setVisible(False)
            self.submitButton.setEnabled(True)
            iface.messageBar().pushSuccess("k.lab Client", message)
        else:
            self.installButton.setEnabled(True)
            self.installStatusLabel.setText(f"Install failed: {message}")
            iface.messageBar().pushCritical("k.lab Client", f"Install failed: {message}")

    # ------------------------------------------------------------------ #
    # Settings                                                             #
    # ------------------------------------------------------------------ #

    def _load_settings(self):
        s = QSettings()
        self.usernameEdit.setText(s.value("KlabClient/username", ""))
        self.passwordEdit.setText(s.value("KlabClient/password", ""))
        self.engineUrlEdit.setText(s.value("KlabClient/engine", ""))
        self.observableEdit.setText(s.value("KlabClient/observable", "geography:Elevation"))
        self.yearSpinBox.setValue(int(s.value("KlabClient/year", 2010)))
        self.resolutionEdit.setText(s.value("KlabClient/resolution", "1 km"))
        self.exportFormatCombo.setCurrentIndex(0)  # always reset to placeholder

    def _save_observe_settings(self):
        s = QSettings()
        s.setValue("KlabClient/observable", self.observableEdit.text())
        s.setValue("KlabClient/year", self.yearSpinBox.value())
        s.setValue("KlabClient/resolution", self.resolutionEdit.text())

    def _save_connection_settings(self):
        s = QSettings()
        s.setValue("KlabClient/username", self.usernameEdit.text())
        s.setValue("KlabClient/password", self.passwordEdit.text())
        s.setValue("KlabClient/engine", self.engineUrlEdit.text())

    # ------------------------------------------------------------------ #
    # Signal wiring                                                        #
    # ------------------------------------------------------------------ #

    def _connect_signals(self):
        self.installButton.clicked.connect(self._on_install)
        self.useMapViewCheckbox.toggled.connect(self._update_extent_ui)
        self.refreshExtentButton.clicked.connect(self._refresh_extent_from_map)
        self.submitButton.clicked.connect(self._on_submit)
        self.testConnectionButton.clicked.connect(self._on_test_connection)
        self.saveSettingsButton.clicked.connect(self._on_save_connection_settings)

    # ------------------------------------------------------------------ #
    # Extent helpers                                                       #
    # ------------------------------------------------------------------ #

    def _update_extent_ui(self):
        use_map = self.useMapViewCheckbox.isChecked()
        self.manualExtentWidget.setEnabled(not use_map)
        self.crsEdit.setReadOnly(use_map)
        if use_map:
            self._refresh_extent_from_map()

    def _refresh_extent_from_map(self):
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        crs_id = canvas.mapSettings().destinationCrs().authid()
        self.minXSpinBox.setValue(extent.xMinimum())
        self.maxXSpinBox.setValue(extent.xMaximum())
        self.minYSpinBox.setValue(extent.yMinimum())
        self.maxYSpinBox.setValue(extent.yMaximum())
        self.crsEdit.setText(crs_id)

    def _build_polygon_wkt(self):
        crs_id = self.crsEdit.text().strip() or "EPSG:4326"
        xmin = self.minXSpinBox.value()
        xmax = self.maxXSpinBox.value()
        ymin = self.minYSpinBox.value()
        ymax = self.maxYSpinBox.value()
        return (
            f"{crs_id} POLYGON(({xmin} {ymin}, {xmax} {ymin}, "
            f"{xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))"
        )

    # ------------------------------------------------------------------ #
    # Square-cell snapping                                                 #
    # ------------------------------------------------------------------ #

    def _snap_extent_to_grid(self, xmin, ymin, xmax, ymax, crs_id, resolution_str):
        """Expand the extent so all four edges fall on resolution-grid lines."""
        import math
        res = self._resolution_in_crs_units(resolution_str, crs_id)
        if res is None or res <= 0:
            iface.messageBar().pushWarning(
                "k.lab Client",
                f"Could not parse resolution '{resolution_str}' — extent unchanged",
            )
            return xmin, ymin, xmax, ymax
        return (
            math.floor(xmin / res) * res,
            math.floor(ymin / res) * res,
            math.ceil(xmax / res) * res,
            math.ceil(ymax / res) * res,
        )

    def _resolution_in_crs_units(self, resolution_str, crs_id):
        """Return the resolution value expressed in the native units of crs_id."""
        import re
        m = re.fullmatch(r"\s*([\d.]+)\s*(\w+)\s*", resolution_str)
        if not m:
            return None
        value, unit = float(m.group(1)), m.group(2).lower()

        if unit in ("deg", "degree", "degrees"):
            return value

        if unit in ("km", "kilometer", "kilometre", "kilometers", "kilometres"):
            metres = value * 1000.0
        elif unit in ("m", "meter", "metre", "meters", "metres"):
            metres = value
        else:
            return None

        crs = QgsCoordinateReferenceSystem(crs_id)
        if crs.isGeographic():
            return metres / 111_320.0  # approximate m → degrees at equator
        map_units = crs.mapUnits()
        if map_units == QgsUnitTypes.DistanceMeters:
            return metres
        if map_units == QgsUnitTypes.DistanceFeet:
            return metres * 3.28084
        if map_units == QgsUnitTypes.DistanceKilometers:
            return metres / 1000.0
        return metres  # best-effort fallback

    # ------------------------------------------------------------------ #
    # Connection tab                                                       #
    # ------------------------------------------------------------------ #

    def _get_credentials(self):
        return {
            "username": self.usernameEdit.text().strip(),
            "password": self.passwordEdit.text(),
            "engine": self.engineUrlEdit.text().strip(),
        }

    def _on_test_connection(self):
        self.connectionStatusLabel.setText("Testing…")
        self.testConnectionButton.setEnabled(False)
        self._conn_worker = KlabConnectionWorker(self._get_credentials())
        self._conn_worker.connectionResult.connect(self._on_connection_result)
        self._conn_worker.finished.connect(self._conn_worker.deleteLater)
        self._conn_worker.start()

    def _on_connection_result(self, success, message):
        self.testConnectionButton.setEnabled(True)
        color = "green" if success else "red"
        self.connectionStatusLabel.setText(
            f'<span style="color:{color};">{message}</span>'
        )

    def _on_save_connection_settings(self):
        self._save_connection_settings()
        iface.messageBar().pushSuccess("k.lab Client", "Connection settings saved.")

    # ------------------------------------------------------------------ #
    # Observe tab                                                          #
    # ------------------------------------------------------------------ #

    def _on_submit(self):
        if self._obs_worker and self._obs_worker.isRunning():
            iface.messageBar().pushWarning("k.lab Client", "An observation is already running.")
            return

        observable = self.observableEdit.text().strip()
        if not observable:
            iface.messageBar().pushWarning("k.lab Client", "Please enter an observable.")
            return

        resolution = self.resolutionEdit.text().strip()
        if not resolution:
            iface.messageBar().pushWarning("k.lab Client", "Please enter a resolution.")
            return

        fmt_index = self.exportFormatCombo.currentIndex()
        if fmt_index == 0:
            iface.messageBar().pushWarning("k.lab Client", "Please select an export format.")
            return
        export_format = ("raster", "vector")[fmt_index - 1]

        if self.useMapViewCheckbox.isChecked():
            self._refresh_extent_from_map()

        if self.forceSquareCellsCheckbox.isChecked():
            crs_id = self.crsEdit.text().strip() or "EPSG:4326"
            xmin, ymin, xmax, ymax = self._snap_extent_to_grid(
                self.minXSpinBox.value(), self.minYSpinBox.value(),
                self.maxXSpinBox.value(), self.maxYSpinBox.value(),
                crs_id, resolution,
            )
            self.minXSpinBox.setValue(xmin)
            self.minYSpinBox.setValue(ymin)
            self.maxXSpinBox.setValue(xmax)
            self.maxYSpinBox.setValue(ymax)

        self._save_observe_settings()
        self.logTextEdit.clear()
        self._set_running(True)

        self._obs_worker = KlabObservationWorker(
            credentials=self._get_credentials(),
            observable=observable,
            polygon_wkt=self._build_polygon_wkt(),
            resolution=resolution,
            year=self.yearSpinBox.value(),
            export_format=export_format,
        )
        self._obs_worker.log.connect(self._on_log)
        self._obs_worker.observationFinished.connect(self._on_observation_finished)
        self._obs_worker.observationError.connect(self._on_observation_error)
        self._obs_worker.finished.connect(self._obs_worker.deleteLater)
        self._obs_worker.finished.connect(self._on_obs_worker_done)
        self._obs_worker.start()

    def _on_obs_worker_done(self):
        self._obs_worker = None

    def _set_running(self, running):
        self.submitButton.setEnabled(not running)
        self.progressBar.setVisible(running)
        self.statusLabel.setText("Observing…" if running else "Ready")

    def _on_log(self, message):
        self.logTextEdit.appendPlainText(message)

    def _on_observation_finished(self, file_path, layer_type):
        self._set_running(False)
        observable = self.observableEdit.text().strip()
        year = self.yearSpinBox.value()
        layer_name = f"{observable} ({year})"

        if layer_type == "raster":
            layer = QgsRasterLayer(file_path, layer_name)
        else:
            layer = QgsVectorLayer(file_path, layer_name, "ogr")

        if not layer.isValid():
            self.statusLabel.setText("Layer invalid — see log")
            self.logTextEdit.appendPlainText(f"ERROR: could not load layer from {file_path}")
            iface.messageBar().pushWarning(
                "k.lab Client", f"Result file could not be loaded as a layer: {file_path}"
            )
            return

        QgsProject.instance().addMapLayer(layer)
        self.statusLabel.setText(f"Loaded: {layer_name}")
        self.logTextEdit.appendPlainText(f"Layer added to project: {layer_name}")
        iface.messageBar().pushSuccess("k.lab Client", f"Loaded: {layer_name}")

    def _on_observation_error(self, message):
        self._set_running(False)
        self.statusLabel.setText("Error — see log")
        self.logTextEdit.appendPlainText(f"ERROR: {message}")
        iface.messageBar().pushCritical("k.lab Client", message)

    # ------------------------------------------------------------------ #
    # Cleanup                                                              #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        if self._obs_worker and self._obs_worker.isRunning():
            self._obs_worker.quit()
            self._obs_worker.wait(2000)
        super().closeEvent(event)

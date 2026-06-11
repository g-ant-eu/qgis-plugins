from qgis.PyQt.QtWidgets import QDialog, QAction
from qgis.core import QgsProject, QgsRasterLayer, QgsCoordinateTransform, \
    QgsMapLayerType, QgsRectangle, QgsPointXY
from qgis.PyQt.QtCore import QSettings, Qt, QTimer
from PyQt5.QtGui import QColor
from qgis.utils import iface
from .geomorpheye_dialog import Ui_Dialog
from .ui import IconGeomorphEye
from .rasteroverlay import RasterOverlay
from qgis.PyQt import sip


class GeomorphEyePlugin():
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        self.action = QAction(IconGeomorphEye, "GeomorphEye", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&G-ANT", self.action)
        self.iface.addToolBarIcon(self.action)
        self.dialog = None

    def unload(self):
        if self.dialog:
            self.dialog.unload()
            del self.dialog
            self.dialog = None
        self.iface.removePluginMenu("&G-ANT", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if not self.dialog:
            self.dialog = GeomorpheyePluginDialog(self.iface)
        self.dialog.show()


class GeomorpheyePluginDialog(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.rasterOverlayItem = None
        self._currentRasterLayer = None

        self._refreshTimer = QTimer()
        self._refreshTimer.setSingleShot(True)
        self._refreshTimer.timeout.connect(self._refresh_overlay)

        self.setupUi(self)
        self.setWindowTitle("GeomorphEye")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        settings = QSettings()
        viewFlow    = self.isTrue(settings.value("GeomorphEye/viewFlow", True))
        viewPit     = self.isTrue(settings.value("GeomorphEye/viewPit", True))
        viewValues  = self.isTrue(settings.value("GeomorphEye/viewValues", False))
        viewColRow  = self.isTrue(settings.value("GeomorphEye/viewColRow", False))
        viewBorders = self.isTrue(settings.value("GeomorphEye/viewBorders", True))
        viewColors  = self.isTrue(settings.value("GeomorphEye/viewColors", False))
        fontSize        = int(settings.value("GeomorphEye/fontSize", 14))
        cellBorderColor = settings.value("GeomorphEye/cellBorderColor", "#000000")
        maxCells        = int(settings.value("GeomorphEye/maxCells", 10000))

        self.viewFlowCheckbox.setChecked(viewFlow)
        self.viewPitsCheckbox.setChecked(viewPit)
        self.viewValuesCheckbox.setChecked(viewValues)
        self.viewColRowCheckbox.setChecked(viewColRow)
        self.viewBordersCheckbox.setChecked(viewBorders)
        self.viewColorsCheckbox.setChecked(viewColors)
        self.fontSizeSpinBox.setValue(fontSize)
        self.cellBorderColorButton.setColor(QColor(cellBorderColor))
        self.maxCellsSpinBox.setValue(maxCells)

        self.viewFlowCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewPitsCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewValuesCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewColRowCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewBordersCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewColorsCheckbox.toggled.connect(self.on_checkbox_changed)
        self.fontSizeSpinBox.valueChanged.connect(self.on_fontsize_changed)
        self.cellBorderColorButton.colorChanged.connect(self.on_color_changed)
        self.maxCellsSpinBox.valueChanged.connect(self.on_maxcells_changed)

        self.rasterLayerCombobox.setFilters(QgsMapLayerType.Raster)
        self.rasterLayerCombobox.layerChanged.connect(self._on_layer_changed)
        self.pushButtonLoad.clicked.connect(self.load_raster_info)
        self.pushButtonZoomTo.clicked.connect(self.zoom_to_cell)
        self.buttonBox.accepted.connect(self.on_accept)
        self.buttonBox.rejected.connect(self.on_reject)

        self.reset_ui()

    def isTrue(self, value):
        return str(value).lower() == "true"

    def reset_ui(self):
        self.pushButtonLoad.setEnabled(True)
        self.progressBar.setVisible(False)
        self.progressBar.setValue(0)

    # ------------------------------------------------------------------ #
    #  Dialog lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def on_accept(self):
        self.cleanup_overlay()
        self.accept()

    def on_reject(self):
        self.cleanup_overlay()
        self.reject()

    def closeEvent(self, event):
        self.cleanup_overlay()
        super().closeEvent(event)

    def unload(self):
        self.cleanup_overlay()

    def cleanup_overlay(self):
        if self.rasterOverlayItem:
            self._refreshTimer.stop()
            canvas = self.iface.mapCanvas()
            try:
                canvas.extentsChanged.disconnect(self._on_canvas_extent_changed)
            except TypeError:
                pass  # not connected
            canvas.scene().removeItem(self.rasterOverlayItem)
            sip.delete(self.rasterOverlayItem)
            self.rasterOverlayItem = None
            self._currentRasterLayer = None

    # ------------------------------------------------------------------ #
    #  Settings callbacks                                                  #
    # ------------------------------------------------------------------ #

    def on_checkbox_changed(self):
        settings = QSettings()
        settings.setValue("GeomorphEye/viewFlow",    self.viewFlowCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewPit",     self.viewPitsCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewValues",  self.viewValuesCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewBorders", self.viewBordersCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewColors",  self.viewColorsCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewColRow",  self.viewColRowCheckbox.isChecked())
        if self.rasterOverlayItem:
            self.rasterOverlayItem.setDrawAttributes(
                self.viewFlowCheckbox.isChecked(),
                self.viewPitsCheckbox.isChecked(),
                self.viewValuesCheckbox.isChecked(),
                self.viewBordersCheckbox.isChecked(),
                self.viewColorsCheckbox.isChecked(),
                self.viewColRowCheckbox.isChecked()
            )

    def on_fontsize_changed(self):
        settings = QSettings()
        settings.setValue("GeomorphEye/fontSize", self.fontSizeSpinBox.value())
        if self.rasterOverlayItem:
            self.rasterOverlayItem.setFontSize(self.fontSizeSpinBox.value())

    def on_color_changed(self):
        settings = QSettings()
        settings.setValue("GeomorphEye/cellBorderColor", self.cellBorderColorButton.color().name())
        if self.rasterOverlayItem:
            self.rasterOverlayItem.setBorderColor(self.cellBorderColorButton.color().name())

    def on_maxcells_changed(self):
        settings = QSettings()
        settings.setValue("GeomorphEye/maxCells", self.maxCellsSpinBox.value())

    def zoom_to_cell(self):
        rasterLayer = self.rasterLayerCombobox.currentLayer()
        if not rasterLayer or not isinstance(rasterLayer, QgsRasterLayer):
            iface.messageBar().pushWarning("No Raster Layer", "Please select a raster layer first.")
            return
        col = self.colSpinBox.value()
        row = self.rowSpinBox.value()
        rasterExtent = rasterLayer.extent()
        xRes = rasterLayer.rasterUnitsPerPixelX()
        yRes = rasterLayer.rasterUnitsPerPixelY()
        worldX = rasterExtent.xMinimum() + (col + 0.5) * xRes
        worldY = rasterExtent.yMaximum() - (row + 0.5) * yRes
        canvas = self.iface.mapCanvas()
        canvas.setCenter(QgsPointXY(worldX, worldY))
        canvas.refresh()

    # ------------------------------------------------------------------ #
    #  Auto-refresh on pan / zoom                                         #
    # ------------------------------------------------------------------ #

    def _on_canvas_extent_changed(self):
        # Debounce: restart timer so we only refresh after panning stops.
        self._refreshTimer.start(1000)

    def _refresh_overlay(self):
        if not self.rasterOverlayItem or not self._currentRasterLayer:
            return
        data = self._read_raster_data(self._currentRasterLayer)
        if data is None:
            # Zoomed out too far or panned outside raster — hide until back in range.
            self.rasterOverlayItem.setVisible(False)
            return
        x_y_c_r_v_sink_dir_List, readExtent, rasterXres, rasterYres, elevMin, elevMax = data
        self.rasterOverlayItem.setVisible(True)
        self.rasterOverlayItem.updateData(
            x_y_c_r_v_sink_dir_List, readExtent, rasterXres, rasterYres, elevMin, elevMax
        )

    # ------------------------------------------------------------------ #
    #  Data reading                                                        #
    # ------------------------------------------------------------------ #

    def _read_raster_data(self, rasterLayer):
        """Read cell data for the current canvas extent.

        Returns (x_y_c_r_v_sink_dir_List, readExtent, xRes, yRes, elevMin, elevMax)
        or None when the view is outside the raster or has too many cells (> 10 000).
        """
        canvas = self.iface.mapCanvas()
        canvasExtent = canvas.extent()

        raster_provider = rasterLayer.dataProvider()
        rasterExtent    = rasterLayer.extent()
        rasterNorth     = rasterExtent.yMaximum()
        rasterSouth     = rasterExtent.yMinimum()
        rasterWest      = rasterExtent.xMinimum()
        rasterEast      = rasterExtent.xMaximum()
        rasterXres      = rasterLayer.rasterUnitsPerPixelX()
        rasterYres      = rasterLayer.rasterUnitsPerPixelY()

        canvasNorth = canvasExtent.yMaximum()
        canvasSouth = canvasExtent.yMinimum()
        canvasWest  = canvasExtent.xMinimum()
        canvasEast  = canvasExtent.xMaximum()

        if not canvasExtent.intersects(rasterExtent):
            return None

        # Snap reading extent to the raster grid.
        readNorth = rasterNorth
        if readNorth > canvasNorth:
            while readNorth > canvasNorth:
                readNorth -= rasterYres
            readNorth += rasterYres

        readSouth = rasterSouth
        if readSouth < canvasSouth:
            while readSouth < canvasSouth:
                readSouth += rasterYres
            readSouth -= rasterYres

        readWest = rasterWest
        if readWest < canvasWest:
            while readWest < canvasWest:
                readWest += rasterXres
            readWest -= rasterXres

        readEast = rasterEast
        if readEast > canvasEast:
            while readEast > canvasEast:
                readEast -= rasterXres
            readEast += rasterXres

        readExtent = QgsRectangle(readWest, readSouth, readEast, readNorth)
        readCols   = int(readExtent.width()  / rasterXres)
        readRows   = int(readExtent.height() / rasterYres)

        if readCols * readRows > self.maxCellsSpinBox.value():
            return None

        x_y_c_r_v_sink_dir_List = []
        startWorldX = readWest  + rasterXres / 2
        startWorldY = readNorth - rasterYres / 2
        elevMin =  99999999999
        elevMax = -99999999999

        for row in range(readRows):
            for col in range(readCols):
                worldX  = startWorldX + col * rasterXres
                worldY  = startWorldY - row * rasterYres
                origRow = int((rasterNorth - worldY) / rasterYres)
                origCol = int((worldX - rasterWest)  / rasterXres)

                result = raster_provider.sample(QgsPointXY(worldX, worldY), 1)
                value  = result[0] if result[1] else None

                if value is not None:
                    elevMin = min(elevMin, value)
                    elevMax = max(elevMax, value)

                    tl = raster_provider.sample(QgsPointXY(worldX - rasterXres, worldY + rasterYres), 1)
                    tc = raster_provider.sample(QgsPointXY(worldX,              worldY + rasterYres), 1)
                    tr = raster_provider.sample(QgsPointXY(worldX + rasterXres, worldY + rasterYres), 1)
                    cl = raster_provider.sample(QgsPointXY(worldX - rasterXres, worldY             ), 1)
                    cr = raster_provider.sample(QgsPointXY(worldX + rasterXres, worldY             ), 1)
                    bl = raster_provider.sample(QgsPointXY(worldX - rasterXres, worldY - rasterYres), 1)
                    bc = raster_provider.sample(QgsPointXY(worldX,              worldY - rasterYres), 1)
                    br = raster_provider.sample(QgsPointXY(worldX + rasterXres, worldY - rasterYres), 1)

                    tlDir = (tl[0] if tl[1] else None, 4)
                    tcDir = (tc[0] if tc[1] else None, 3)
                    trDir = (tr[0] if tr[1] else None, 2)
                    clDir = (cl[0] if cl[1] else None, 5)
                    crDir = (cr[0] if cr[1] else None, 1)
                    blDir = (bl[0] if bl[1] else None, 6)
                    bcDir = (bc[0] if bc[1] else None, 7)
                    brDir = (br[0] if br[1] else None, 8)

                    neighbours = [tlDir, tcDir, trDir, clDir, crDir, blDir, bcDir, brDir]
                    allValues  = [d[0] for d in neighbours]

                    isSink = not any(v is not None and v < value for v in allValues)
                    if isSink and allValues.count(value) > 1:
                        isSink = False

                    steepestDir   = None
                    steepestValue = None
                    for val, direction in neighbours:
                        if val is not None and (steepestValue is None or val < steepestValue):
                            steepestValue = val
                            steepestDir   = direction

                    x_y_c_r_v_sink_dir_List.append(
                        (worldX, worldY, origCol, origRow, value, isSink, steepestDir)
                    )

        return (x_y_c_r_v_sink_dir_List, readExtent, rasterXres, rasterYres, elevMin, elevMax)

    # ------------------------------------------------------------------ #
    #  Layer selection change                                             #
    # ------------------------------------------------------------------ #

    def _on_layer_changed(self, layer):
        if not self.rasterOverlayItem:
            return
        self.cleanup_overlay()
        self.pushButtonLoad.setText("Load On-Screen Raster Info")
        self.reset_ui()
        if layer and isinstance(layer, QgsRasterLayer):
            self.load_raster_info()

    # ------------------------------------------------------------------ #
    #  Load / unload button                                               #
    # ------------------------------------------------------------------ #

    def load_raster_info(self):
        canvas = self.iface.mapCanvas()
        if self.rasterOverlayItem:
            self.cleanup_overlay()
            self.pushButtonLoad.setText("Load On-Screen Raster Info")
            self.reset_ui()
            return

        rasterLayer = self.rasterLayerCombobox.currentLayer()
        if not rasterLayer:
            iface.messageBar().pushWarning("No Raster Layer", "Please select a raster layer.")
            return
        if not isinstance(rasterLayer, QgsRasterLayer):
            iface.messageBar().pushWarning("Invalid Layer", "Selected layer is not a raster layer.")
            return

        raster_crs = rasterLayer.crs()
        canvas_crs = canvas.mapSettings().destinationCrs()
        if raster_crs != canvas_crs:
            iface.messageBar().pushWarning(
                "CRS Mismatch", "This only works if the raster has the same CRS as the map canvas.")
            return

        if not canvas.extent().intersects(rasterLayer.extent()):
            iface.messageBar().pushWarning("No Data", "No data found in the selected extent.")
            self.reset_ui()
            return

        self.pushButtonLoad.setEnabled(False)
        self.progressBar.setVisible(True)
        self.progressBar.setValue(0)

        data = self._read_raster_data(rasterLayer)

        if data is None:
            iface.messageBar().pushWarning(
                "Too many cells", "Zoom in first — max 10,000 cells can be displayed.")
            self.reset_ui()
            return

        x_y_c_r_v_sink_dir_List, readExtent, rasterXres, rasterYres, elevMin, elevMax = data

        self.progressBar.setValue(100)

        overlay = RasterOverlay(
            canvas,
            x_y_c_r_v_sink_dir_List,
            readExtent, rasterXres, rasterYres, elevMin, elevMax,
            fontSize    = self.fontSizeSpinBox.value(),
            borderColor = self.cellBorderColorButton.color().name(),
            draw_pits   = self.viewPitsCheckbox.isChecked(),
            draw_flow   = self.viewFlowCheckbox.isChecked(),
            draw_values = self.viewValuesCheckbox.isChecked(),
            draw_cells  = self.viewBordersCheckbox.isChecked(),
            draw_colors = self.viewColorsCheckbox.isChecked(),
            draw_colrow = self.viewColRowCheckbox.isChecked(),
        )

        self._currentRasterLayer = rasterLayer
        self.rasterOverlayItem   = overlay
        canvas.extentsChanged.connect(self._on_canvas_extent_changed)

        self.pushButtonLoad.setText("Remove On-Screen Raster Info")
        self.reset_ui()

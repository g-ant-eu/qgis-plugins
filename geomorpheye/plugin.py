from qgis.PyQt.QtWidgets import QDialog, QAction
from qgis.core import QgsProject, QgsRasterLayer, QgsCoordinateTransform, \
    QgsMapLayerType, QgsRectangle
from qgis.PyQt.QtCore import QSettings
from PyQt5.QtGui import QColor
from qgis.utils import iface
from .geomorpheye_dialog import Ui_Dialog
from qgis.PyQt.QtCore import Qt
from .ui import IconGeomorphEye
from .rasteroverlay import RasterOverlay



class GeomorphEyePlugin():
    def __init__(self, iface):
        """Initialize the plugin with the QGIS interface."""
        self.iface = iface

    def initGui(self):
        
        """Initialize the plugin GUI (adds the action to QGIS)."""
        self.action = QAction(IconGeomorphEye, "GeomorphEye", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("&G-ANT", self.action)
        self.iface.addToolBarIcon(self.action)
        self.dialog = None

    def unload(self):
        if self.dialog:
            self.dialog.unload()
            self.dialog = None
        """Remove the plugin from QGIS when it's disabled."""
        self.iface.removePluginMenu("&G-ANT", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Show the plugin dialog when triggered."""
        if not self.dialog:
            self.dialog = GeomorpheyePluginDialog(self.iface)
        self.dialog.show()

class GeomorpheyePluginDialog(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface

        self.rasterOverlayItem = None
        
        self.setupUi(self)
        self.setWindowTitle("GeomorphEye")
        # Make the dialog stay on top without blocking interaction with QGIS
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # Restore previous settings
        settings = QSettings()
        viewFlow = settings.value("GeomorphEye/viewFlow", True)
        viewFlow = self.isTrue(viewFlow)
        viewPit = settings.value("GeomorphEye/viewPit", True)
        viewPit = self.isTrue(viewPit)
        viewValues = settings.value("GeomorphEye/viewValues", False)
        viewValues = self.isTrue(viewValues)
        viewBorders = settings.value("GeomorphEye/viewBorders", True)
        viewBorders = self.isTrue(viewBorders)
        viewColors = settings.value("GeomorphEye/viewColors", False)
        viewColors = self.isTrue(viewColors)
        fontSize = settings.value("GeomorphEye/fontSize", 14)
        fontSize = int(fontSize)
        cellBorderColor = settings.value("GeomorphEye/cellBorderColor", "#000000")


        self.viewFlowCheckbox.setChecked(viewFlow)
        self.viewPitsCheckbox.setChecked(viewPit)
        self.viewValuesCheckbox.setChecked(viewValues)
        self.viewBordersCheckbox.setChecked(viewBorders)
        self.viewColorsCheckbox.setChecked(viewColors)
        self.fontSizeSpinBox.setValue(fontSize)
        self.cellBorderColorButton.setColor(QColor(cellBorderColor))
        self.viewFlowCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewPitsCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewValuesCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewBordersCheckbox.toggled.connect(self.on_checkbox_changed)
        self.viewColorsCheckbox.toggled.connect(self.on_checkbox_changed)
        self.fontSizeSpinBox.valueChanged.connect(self.on_fontsize_changed)
        self.cellBorderColorButton.colorChanged.connect(self.on_color_changed)

        self.rasterLayerCombobox.setFilters(QgsMapLayerType.Raster)

        self.pushButtonLoad.clicked.connect(self.load_raster_info)

        self.buttonBox.accepted.connect(self.on_accept)
        self.buttonBox.rejected.connect(self.on_reject)

        self.reset_ui()

    def on_accept(self):
        self.cleanup_overlay()
        self.accept()

    def on_reject(self):
        self.cleanup_overlay()
        self.reject()

    def closeEvent(self, event):
        self.cleanup_overlay()
        super().closeEvent(event)

    def cleanup_overlay(self):
        if self.rasterOverlayItem:
            canvas = self.iface.mapCanvas()
            canvas.scene().removeItem(self.rasterOverlayItem)
            del self.rasterOverlayItem
            self.rasterOverlayItem = None


    def unload(self):
        self.cleanup_overlay()

    def isTrue(self, value):
        """Check if the value is a string representation of True."""
        return str(value).lower() == "true"
        
    def reset_ui(self):
        # pass
        self.pushButtonLoad.setEnabled(True)
        self.progressBar.setVisible(False)
        self.progressBar.setValue(0)

    def on_checkbox_changed(self):
        # Save the current settings
        settings = QSettings()
        settings.setValue("GeomorphEye/viewFlow", self.viewFlowCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewPit", self.viewPitsCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewValues", self.viewValuesCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewBorders", self.viewBordersCheckbox.isChecked())
        settings.setValue("GeomorphEye/viewColors", self.viewColorsCheckbox.isChecked())

        # Re-trigger the overlay if it's already visible
        if self.rasterOverlayItem:
            self.load_raster_info(reload=True)
    
    def on_fontsize_changed(self):
        # Save the current settings
        settings = QSettings()
        settings.setValue("GeomorphEye/fontSize", self.fontSizeSpinBox.value())

        # Re-trigger the overlay if it's already visible
        if self.rasterOverlayItem:
            self.load_raster_info(reload=True)

    def on_color_changed(self):
        # Save the current settings
        settings = QSettings()
        settings.setValue("GeomorphEye/cellBorderColor", self.cellBorderColorButton.color().name())

        # Re-trigger the overlay if it's already visible
        if self.rasterOverlayItem:
            self.load_raster_info(reload=True)


    def load_raster_info(self, reload=False):
        canvas = self.iface.mapCanvas()
        if self.rasterOverlayItem:
            self.cleanup_overlay()
            if not reload:
                self.pushButtonLoad.setText("Load On-Screen Raster Info")
                self.reset_ui()
                return
        
        # get raster layer from layer combobox
        rasterLayer = self.rasterLayerCombobox.currentLayer()
        if not rasterLayer:
            iface.messageBar().pushWarning("No Raster Layer", "Please select a raster layer.")
            return
        if not isinstance(rasterLayer, QgsRasterLayer):
            iface.messageBar().pushWarning("Invalid Layer", "Selected layer is not a raster layer.")
            return

        # Disable button and show progress bar
        self.pushButtonLoad.setEnabled(False)
        self.progressBar.setVisible(True)
        self.progressBar.setValue(0)

        # get the raster        
        canvasExtent = canvas.extent()  # QgsRectangle of current view
        raster_crs = rasterLayer.crs()
        canvas_crs = canvas.mapSettings().destinationCrs()

        # Reproject extent if necessary
        if raster_crs != canvas_crs:
            iface.messageBar().pushWarning("CRS Mismatch", "This only works if the raster has the same CRS as the map canvas.")
            return
            # transform = QgsCoordinateTransform(canvas_crs, raster_crs, QgsProject.instance())
            # extent = transform.transformBoundingBox(extent)

        raster_provider = rasterLayer.dataProvider()
        rasterExtent = rasterLayer.extent()
        rasterNorth = rasterExtent.yMaximum()
        rasterSouth = rasterExtent.yMinimum()
        rasterWest = rasterExtent.xMinimum()
        rasterEast = rasterExtent.xMaximum()
        rasterCols = rasterLayer.width()
        rasterRows = rasterLayer.height()
        rasterXres = rasterLayer.rasterUnitsPerPixelX()
        rasterYres = rasterLayer.rasterUnitsPerPixelY()

        # now the same for the canvas
        canvasNorth = canvasExtent.yMaximum()
        canvasSouth = canvasExtent.yMinimum()
        canvasWest = canvasExtent.xMinimum()
        canvasEast = canvasExtent.xMaximum()

        # the reading extent is the intersection of the two extents
        doIntersect = canvasExtent.intersects(rasterExtent)
        if not doIntersect:
            iface.messageBar().pushWarning("No Data", "No data found in the selected extent.")
            self.reset_ui()
            return
        
        # now snap the extent to the raster grid
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
        readCols = int(readExtent.width()/rasterXres)
        readRows = int(readExtent.height()/rasterYres)
        block = raster_provider.block(1, readExtent, readCols, readRows)
        if block is None:
            iface.messageBar().pushWarning("No Data", "No data found in the selected extent.")
            self.reset_ui()
            return
        
        self.progressBar.setValue(50)
        
        x_y_c_r_v_sink_dir_List  = []
        startWorldX = readWest + rasterXres / 2
        startWorldY = readNorth - rasterYres / 2
        for row in range(readRows):
            for col in range(readCols):
                value = block.value(row, col)
                if value is not None:
                    worldX = startWorldX + col * rasterXres
                    worldY = startWorldY - row * rasterYres
                    # get the orig raster row and col
                    origRow = int((rasterNorth - worldY) / rasterYres)
                    origCol = int((worldX - rasterWest) / rasterXres)
                    
                    # get surrounding cells
                    tl = block.value(row - 1, col - 1) if row > 0 and col > 0 else None
                    tlDir = (tl, 4)
                    tc = block.value(row - 1, col) if row > 0 else None
                    tcDir = (tc, 3)
                    tr = block.value(row - 1, col + 1) if row > 0 and col < rasterCols - 1 else None
                    trDir = (tr, 2)
                    cl = block.value(row, col - 1) if col > 0 else None
                    clDir = (cl, 5)
                    cr = block.value(row, col + 1) if col < rasterCols - 1 else None
                    crDir = (cr, 1)
                    bl = block.value(row + 1, col - 1) if row < rasterRows - 1 and col > 0 else None
                    blDir = (bl, 6)
                    bc = block.value(row + 1, col) if row < rasterRows - 1 else None
                    bcDir = (bc, 7)
                    br = block.value(row + 1, col + 1) if row < rasterRows - 1 and col < rasterCols - 1 else None
                    brDir = (br, 8)
                    allValues = [tl, tc, tr, cl, cr, bl, bc, br]
                    # check sink
                    isSink = True
                    for val in allValues:
                        if val is not None and val < value:
                            isSink = False
                            break
                    # check steepest direction
                    steepestDir = None
                    steepestValue = None
                    for val, dir in [tlDir, tcDir, trDir, clDir, crDir, blDir, bcDir, brDir]:
                        if val is not None and (steepestValue is None or val < steepestValue):
                            steepestValue = val
                            steepestDir = dir
                    
                    x_y_c_r_v_sink_dir_List.append((worldX, worldY, origCol, origRow, value, isSink, steepestDir))


        overlay = RasterOverlay(canvas, rasterLayer,
                                x_y_c_r_v_sink_dir_List,
                                readExtent,
                                rasterXres,
                                rasterYres,
                                fontSize=self.fontSizeSpinBox.value(),
                                borderColor=self.cellBorderColorButton.color().name(),
                                draw_pits=self.viewPitsCheckbox.isChecked(),
                                draw_flow=self.viewFlowCheckbox.isChecked(),
                                draw_values=self.viewValuesCheckbox.isChecked(),
                                draw_cells=self.viewBordersCheckbox.isChecked(),
                                draw_colors=self.viewColorsCheckbox.isChecked()
                                )

        canvas.scene().addItem(overlay)
        self.rasterOverlayItem = overlay

        self.pushButtonLoad.setText("Remove On-Screen Raster Info")

        self.progressBar.setValue(100)

        self.reset_ui()

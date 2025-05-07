from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QAction
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer,QgsMapLayer
from qgis.utils import iface
import os
from .rasterfromvectorfieldloader_dialog import Ui_Dialog
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from .ui import IconRasterLoader

class RasterLoaderPlugin(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        
        self.setupUi(self)
        self.setWindowTitle("Load Rasters from Vector Field")
        # Make the dialog stay on top without blocking interaction with QGIS
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # Restore previous settings
        settings = QSettings()
        last_folder = settings.value("RasterFieldLoader/lastFolder", "")
        last_field = settings.value("RasterFieldLoader/lastField", "")

        self.lineEditRasterFolder.setText(last_folder)
        self.lineEditFieldName.setText(last_field)

        self.reset_ui()
        
        self.pushButtonBrowse.clicked.connect(self.browse_folder)
        self.pushButtonLoad.clicked.connect(self.load_rasters)

        self.raster_folder = None
        self.field_name = None

    def initGui(self):
        """Initialize the plugin GUI (adds the action to QGIS)."""
        # self.action = QAction("G-LdRst", self.iface.mainWindow())
        self.action = QAction(IconRasterLoader, "Raster from vector loader", self.iface.mainWindow())

        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("&G-ANT", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the plugin from QGIS when it's disabled."""
        self.iface.removePluginMenu("&G-ANT", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Show the plugin dialog when triggered."""
        self.show()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Raster Folder")
        if folder:
            self.lineEditRasterFolder.setText(folder)

    def reset_ui(self):
        self.pushButtonLoad.setEnabled(True)
        self.progressBar.setVisible(False)
        self.progressBar.setValue(0)

    def load_rasters(self):
        raster_folder = self.lineEditRasterFolder.text().strip()
        field_name = self.lineEditFieldName.text().strip()

        settings = QSettings()
        settings.setValue("RasterFieldLoader/lastFolder", raster_folder)
        settings.setValue("RasterFieldLoader/lastField", field_name)

        # Disable button and show progress bar
        self.pushButtonLoad.setEnabled(False)
        self.progressBar.setVisible(True)
        self.progressBar.setValue(0)

        if not os.path.isdir(raster_folder):
            iface.messageBar().pushWarning("Invalid Folder", "Please select a valid raster folder.")
            return

        if not field_name:
            iface.messageBar().pushWarning("Missing Field", "Please enter a field name.")
            return
        
        # Gather selected vector layers and features
        selected_layers = iface.layerTreeView().selectedLayers()
        features = []

        for layer in selected_layers:
            if not isinstance(layer, QgsVectorLayer):
                continue
            features.extend(layer.selectedFeatures())

        if not features:
            iface.messageBar().pushWarning("No Features", "No features selected.")
            self.reset_ui()
            return

        total = len(features)
        loaded_rasters = set()
        for i, feature in enumerate(features, start=1):
            QApplication.processEvents()  # Allow UI update
            raster_name = feature[field_name] if field_name in feature.fields().names() else None
            if not raster_name:
                continue

            raster_path = os.path.join(raster_folder, raster_name)
            if not os.path.exists(raster_path):
                iface.messageBar().pushWarning("Raster Missing", f"Raster '{raster_name}' not found.")
                continue

            if raster_path in loaded_rasters:
                continue

            # Check if a raster with the same file path is already loaded
            already_loaded = any(
                lyr.type() == QgsMapLayer.RasterLayer and
                isinstance(lyr, QgsRasterLayer) and
                lyr.source() == raster_path
                for lyr in QgsProject.instance().mapLayers().values()
            )
            if already_loaded:
                continue

            raster_layer = QgsRasterLayer(raster_path, raster_name)
            if raster_layer.isValid():
                QgsProject.instance().addMapLayer(raster_layer)
                loaded_rasters.add(raster_path)
            else:
                iface.messageBar().pushCritical("Invalid Raster", f"Failed to load raster '{raster_path}'")

            self.progressBar.setValue(int(i / total * 100))

        self.reset_ui()

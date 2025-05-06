from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QAction
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.utils import iface
import os
from .rasterfromvectorfieldloader_dialog import Ui_Dialog

class RasterLoaderPlugin(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        
        self.setupUi(self)

        self.pushButtonBrowse.clicked.connect(self.browse_folder)
        self.pushButtonLoad.clicked.connect(self.load_rasters)

        self.raster_folder = None
        self.field_name = None

    def initGui(self):
        """Initialize the plugin GUI (adds the action to QGIS)."""
        self.action = QAction("G-LdRst", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("&G-LdRst", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the plugin from QGIS when it's disabled."""
        self.iface.removePluginMenu("&G-LdRst", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Show the plugin dialog when triggered."""
        self.show()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Raster Folder")
        if folder:
            self.lineEditRasterFolder.setText(folder)

    def load_rasters(self):
        raster_folder = self.lineEditRasterFolder.text().strip()
        field_name = self.lineEditFieldName.text().strip()

        if not os.path.isdir(raster_folder):
            iface.messageBar().pushWarning("Invalid Folder", "Please select a valid raster folder.")
            return

        if not field_name:
            iface.messageBar().pushWarning("Missing Field", "Please enter a field name.")
            return

        loaded_rasters = set()
        for layer in iface.layerTreeView().selectedLayers():
            if not isinstance(layer, QgsVectorLayer):
                continue

            selected_features = layer.selectedFeatures()
            if not selected_features:
                continue

            for feature in selected_features:
                if field_name not in feature.fields().names():
                    iface.messageBar().pushWarning("Field Missing", f"Field '{field_name}' not found in layer '{layer.name()}'")
                    continue

                raster_name = feature[field_name]
                raster_path = os.path.join(raster_folder, f"{raster_name}.tif")

                if not os.path.exists(raster_path):
                    iface.messageBar().pushWarning("Raster Missing", f"Raster '{raster_name}' not found.")
                    continue

                if raster_path in loaded_rasters:
                    continue

                raster_layer = QgsRasterLayer(raster_path, raster_name)
                if raster_layer.isValid():
                    QgsProject.instance().addMapLayer(raster_layer)
                    loaded_rasters.add(raster_path)
                else:
                    iface.messageBar().pushCritical("Invalid Raster", f"Failed to load raster '{raster_path}'")

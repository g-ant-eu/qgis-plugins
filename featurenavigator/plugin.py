from qgis.PyQt.QtWidgets import QDialog, QAction
from qgis.core import QgsProject
from qgis.utils import iface
from .feature_navigator_dialog import Ui_Dialog

class FeatureNavigatorPlugin(QDialog, Ui_Dialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        
        self.setupUi(self)
        self.setWindowTitle("Navigate features of a vector layer")

        # Connect buttons to actions
        self.loadLayerButton.clicked.connect(self.load_layer)
        self.previousButton.clicked.connect(self.previous_feature)
        self.nextButton.clicked.connect(self.next_feature)
        
        self.layer = None
        self.features = []
        self.current_index = -1

    def initGui(self):
        """Initialize the plugin GUI (adds the action to QGIS)."""
        self.action = QAction("G-FtNv", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("&G-FtNv", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the plugin from QGIS when it's disabled."""
        self.iface.removePluginMenu("&G-FtNv", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        """Show the plugin dialog when triggered."""
        self.show()

    def load_layer(self):
        """Load selected layer and initialize feature navigation."""
        self.layer = self.vectorComboSelector.currentLayer()
        if self.layer is not None:
            self.features = list(self.layer.getFeatures())
            self.featureCountValue.setText(str(len(self.features)))
            self.current_index = 0
            self.update_feature_display()

    def previous_feature(self):
        """Navigate to the previous feature."""
        if self.layer and self.features:
            self.current_index = max(0, self.current_index - 1)
            self.update_feature_display()

    def next_feature(self):
        """Navigate to the next feature."""
        if self.layer and self.features:
            self.current_index = min(len(self.features) - 1, self.current_index + 1)
            self.update_feature_display()

    def update_feature_display(self):
        """Update the feature display with the current feature's ID."""
        if self.features:
            feature = self.features[self.current_index]
            self.currentFeatureValue.setText(str(feature.id()))
            self.iface.mapCanvas().setCenter(feature.geometry().boundingBox().center())
            self.iface.mapCanvas().refresh()

            self.layer.removeSelection() 
            self.layer.select(feature.id())

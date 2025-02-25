# G-ANT QGIS-plugins

## Feature Navigator

A QGIS plugin to navigate through the features of a vector layer.

After selecting a layer in the layer combo, the plugin will load the features in memory and by using next and previous, teh plugin centers the map on the feature and selects it.


The ```feature_navigation_dialog.py``` is created using:

```
pyuic5 -o feature_navigator_dialog.py feature-navigator_dialog_base.ui
```
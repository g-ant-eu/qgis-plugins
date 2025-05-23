from qgis.gui import QgsMapCanvasItem, QgsMapCanvas
from qgis.core import QgsPointXY, QgsRasterLayer, QgsRectangle
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtCore import QRectF, Qt
from qgis.core import QgsColorRampShader, QgsStyle
import math

class RasterOverlay(QgsMapCanvasItem):
    def __init__(self, canvas:QgsMapCanvas, x_y_c_r_v_sink_dir_List,
                 readExtent:QgsRectangle, xRes:float, yRes:float, elevMin:float, elevMax:float,
                 fontSize, borderColor, draw_pits, draw_flow, draw_values, draw_cells, draw_colors, draw_colrow):
        print("=======> INITIALIZING RASTER OVERLAY1")
        super().__init__(canvas)
        print("=======> INITIALIZING RASTER OVERLAY2")
        self.x_y_c_r_v_sink_dir_List = x_y_c_r_v_sink_dir_List
        self.readExtent = readExtent
        self.xRes = xRes
        self.yRes = yRes
        self.elevMin = elevMin
        self.elevMax = elevMax
        self.fontSize = fontSize
        self.cellBorderColorHex = borderColor
        self.draw_pits = draw_pits
        self.draw_flow = draw_flow
        self.draw_values = draw_values
        self.draw_cells = draw_cells
        self.draw_colors = draw_colors
        self.draw_colrow = draw_colrow
        self.setZValue(1000)  # draw on top

        self.radiusRatio = 7
        self.textColorHex = "#000000"
        self.flowLinesColorHex = "#1868C4"
        self.sinkColorHex = "#FF0000"
        self.haloColorHex = "#FFFFFF"
        print("=======> INITIALIZING RASTER OVERLAY3")

    def boundingRect(self):
        print("=======> BOUNDING RECT")
        top_left = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMinimum(), self.readExtent.yMaximum()))
        bottom_right = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMaximum(), self.readExtent.yMinimum()))
        bRect = QRectF(top_left, bottom_right)
        print(f"=======> BOUNDING RECT2: {bRect}")
        return bRect
    
    def setFontSize(self, fontSize):
        self.fontSize = fontSize
        self.update()

    def setDrawAttributes(self, enable_flow, enable_pits, enable_values, enable_cells, enable_colors, enable_colrow):
        self.draw_flow = enable_flow
        self.draw_pits = enable_pits
        self.draw_values = enable_values
        self.draw_cells = enable_cells
        self.draw_colors = enable_colors
        self.draw_colrow = enable_colrow
        self.update()
        
    def setBorderColor(self, color):
        self.cellBorderColorHex = color
        self.update()

    def paint(self, painter, option, widget):
        print("=======> STARTING PAINTING")
        self.drawColor(painter)
        self.drawCells(painter)
        self.drawFlow(painter)
        self.drawSinks(painter)
        self.drawValues(painter)
        print("=======> FINISHED PAINTING")

    def drawValues(self, painter):
        if self.draw_values:
            painter.setFont(QFont("Arial", self.fontSize))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if value is not None:
                    upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                    lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                    rect = QRectF(upperLeft, lowerRight)
                    # write col, row and value below each other inside the cell
                    if self.draw_colrow:
                        text = f"c: {origCol}\nr: {origRow}\nv: {value}"
                    else:
                        text = f"{value}"

                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            offset_rect = QRectF(rect)
                            offset_rect.translate(dx, dy)
                            painter.setPen(QPen(QColor(self.haloColorHex), 1))
                            painter.drawText(offset_rect, Qt.AlignCenter, text)


                    painter.setPen(QPen(QColor(self.textColorHex), 1))
                    painter.drawText(rect, Qt.AlignCenter, text)

    def drawSinks(self, painter):
        if self.draw_pits:
            painter.setPen(QPen(QColor(self.sinkColorHex), 1))
            painter.setBrush(QColor(self.sinkColorHex))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if isSink:
                    upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                    lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                    rect = QRectF(upperLeft, lowerRight)
                    # draw a point at the center of the cell
                    center = self.toCanvasCoordinates(QgsPointXY(worldX, worldY))

                    radius = rect.width() / self.radiusRatio
                    painter.drawEllipse(center, radius, radius)

    def drawFlow(self, painter):
        if self.draw_flow:
            painter.setPen(QPen(QColor(self.flowLinesColorHex), 1))
            painter.setBrush(QColor(self.flowLinesColorHex))
            scale = 0.85 # to avoid touching the cell borders
            
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if isSink:
                    continue

                center = QgsPointXY(worldX, worldY)

                dx = dy = 0
                if steepestDir == 1:   dx =  self.xRes / 2
                elif steepestDir == 2: dx =  self.xRes / 2; dy =  self.yRes / 2
                elif steepestDir == 3: dy =  self.yRes / 2
                elif steepestDir == 4: dx = -self.xRes / 2; dy =  self.yRes / 2
                elif steepestDir == 5: dx = -self.xRes / 2
                elif steepestDir == 6: dx = -self.xRes / 2; dy = -self.yRes / 2
                elif steepestDir == 7: dy = -self.yRes / 2
                elif steepestDir == 8: dx =  self.xRes / 2; dy = -self.yRes / 2

                if steepestDir is not None:
                    end = QgsPointXY(worldX + dx * scale, worldY + dy * scale)
                    canvas_center = self.toCanvasCoordinates(center)
                    canvas_end = self.toCanvasCoordinates(end)
                    
                    # distance between points
                    distance = math.sqrt((canvas_center.x() - canvas_end.x())**2 + (canvas_center.y() - canvas_end.y())**2)
                    radius = distance / self.radiusRatio
                    painter.drawEllipse(canvas_center, radius, radius)
                    painter.drawLine(canvas_center, canvas_end)

    def drawCells(self, painter):
        if self.draw_cells:
            painter.setPen(QPen(QColor(self.cellBorderColorHex), 1))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                rect = QRectF(upperLeft, lowerRight)
                painter.drawRect(rect)

    def drawColor(self, painter):
        if self.draw_colors:
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                rect = QRectF(upperLeft, lowerRight)
                color = self.getColor(value)
                painter.fillRect(rect, color)
            
    

    def getColor(self, value):
        if value is None:
            return QColor(255, 255, 255, 0)  # transparent

        # Normalize
        if self.elevMax == self.elevMin:
            ratio = 0.5
        else:
            val = max(self.elevMin, min(self.elevMax, value))
            ratio = (val - self.elevMin) / (self.elevMax - self.elevMin)

        # convert hex to rgb
        stops = [
            (0.0, (0, 191, 191)),  # #00bfbf
            (0.2, (0, 255, 0)),   # #00ff00
            (0.4, (255, 255, 0)), # #ffff00
            (0.6, (255, 127, 0)), # #ff7f00
            (0.8, (191, 127, 63)),# #bf7f3f
            (1.0, (20, 21, 20))   # #141514
        ]

        for i in range(len(stops) - 1):
            r1, c1 = stops[i]
            r2, c2 = stops[i + 1]
            if r1 <= ratio <= r2:
                # Interpolate between c1 and c2
                t = (ratio - r1) / (r2 - r1)
                r = int(c1[0] + (c2[0] - c1[0]) * t)
                g = int(c1[1] + (c2[1] - c1[1]) * t)
                b = int(c1[2] + (c2[2] - c1[2]) * t)
                return QColor(r, g, b, 170)

        return QColor(255, 0, 0)

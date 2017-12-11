# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

class FreehandEditingTool(QgsMapTool):

    rbFinished = pyqtSignal('QgsGeometry*','bool')

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.rb = None
        self.mCtrl = None
        self.drawing = False
        self.ignoreclick = False
        #our own fancy cursor
        self.cursor = QCursor(QPixmap(["16 16 3 1",
                                       "      c None",
                                       ".     c #FF0000",
                                       "+     c #faed55",
                                       "                ",
                                       "       +.+      ",
                                       "      ++.++     ",
                                       "     +.....+    ",
                                       "    +.  .  .+   ",
                                       "   +.   .   .+  ",
                                       "  +.    .    .+ ",
                                       " ++.    .    .++",
                                       " ... ...+... ...",
                                       " ++.    .    .++",
                                       "  +.    .    .+ ",
                                       "   +.   .   .+  ",
                                       "   ++.  .  .+   ",
                                       "    ++.....+    ",
                                       "      ++.++     ",
                                       "       +.+      "]))

    # def keyPressEvent(self, event):
    #     QgsMessageLog.logMessage("key:{}".format(event.key()), 'MyPlugin', QgsMessageLog.INFO)
    #     if event.key() == Qt.Key_Control:
    #         self.mCtrl = True
    #
    # def keyReleaseEvent(self, event):
    #     if event.key() == Qt.Key_Control:
    #         self.mCtrl = False

    def getSnapPoint(self,event,layer):
        x = event.pos().x()
        y = event.pos().y()
        if self.isPolygon:
            if self.snapping:
                startingPoint = QPoint(x, y)
                snapper = QgsMapCanvasSnapper(self.canvas)
                (retval, result) = \
                    snapper.snapToCurrentLayer(startingPoint,
                                               QgsSnapper.SnapToVertex)
                if result:
                    point = result[0].snappedVertex
                else:
                    (retval, result) = \
                        snapper.snapToBackgroundLayers(startingPoint)
                    if result:
                        point = result[0].snappedVertex
                    else:
                        point = self.toLayerCoordinates(layer, event.pos())
            else:
                point = self.toLayerCoordinates(layer, event.pos())
            pointMap = self.toMapCoordinates(layer, point)
            self.rb.addPoint(pointMap)
        else:
            point = self.toLayerCoordinates(layer, event.pos())
            pointMap = self.toMapCoordinates(layer, point)
            self.rb.addPoint(pointMap)

    def canvasPressEvent(self, event):
        if self.ignoreclick or self.drawing:
            # ignore secondary canvasPressEvents if already drag-drawing
            # NOTE: canvasReleaseEvent will still occur (ensures rb is deleted)
            # click on multi-button input device will halt drag-drawing
            return
        layer = self.canvas.currentLayer()
        if not layer:
            return
        #QgsMessageLog.logMessage("{}".format(layer.id()), 'MyPlugin', QgsMessageLog.INFO)
        self.snapping = True
        proj = QgsProject.instance()
        snapmode = proj.readEntry('Digitizing', 'SnappingMode')[0]
        #QgsMessageLog.logMessage("{}".format(snapmode), 'MyPlugin', QgsMessageLog.INFO)
        if snapmode=="advanced":
            snaplayer = proj.readListEntry('Digitizing', 'LayerSnappingList')[0]
            snapenabled = proj.readListEntry('Digitizing', 'LayerSnappingEnabledList')[0]
            snapavoid = proj.readListEntry('Digitizing', 'AvoidIntersectionsList')[0]
            snaptype=snapenabled[snaplayer.index(layer.id())]
            self.snapavoidbool = layer.id() in snapavoid
            #QgsMessageLog.logMessage("sss:{}".format(type(self.snapavoidbool)), 'MyPlugin', QgsMessageLog.INFO)
            if snaptype=="disabled":
                self.snapping=False
        else:
            snaptype=proj.readEntry('Digitizing','DefaultSnapType')[0]
            if snaptype=="off":
                self.snapping = False
            self.snapavoidbool = False
        self.drawing = True
        self.type = layer.geometryType()
        self.isPolygon = (self.type != QGis.Line)
        if self.isPolygon:
            #print "self is a polygon"
            self.rb = QgsRubberBand(self.canvas, QGis.Polygon)
            self.rb.setColor(QColor(255, 0, 0, 63))
            self.rb.setWidth(2)
        else:
            #print "self is not a polygon"
            self.rb = QgsRubberBand(self.canvas)
            self.rb.setColor(QColor(255, 0, 0, 150))
            self.rb.setWidth(1)
        self.getSnapPoint(event,layer)


    def canvasMoveEvent(self, event):
        if self.ignoreclick or not self.rb:
            return
        layer = self.canvas.currentLayer()
        if not layer:
            return
        self.getSnapPoint(event,layer)

    def canvasReleaseEvent(self, event):
        if self.ignoreclick:
            return
        layer = self.canvas.currentLayer()
        if not layer:
            return
        self.drawing = False
        if not self.rb:
            return
        if self.rb.numberOfVertices() > 2:
            geom = self.rb.asGeometry()
            self.rbFinished.emit(geom,self.snapavoidbool)
        # reset rubberband and refresh the canvas
        self.rb.reset()
        self.rb = None
        self.isPolygon = (self.type != QGis.Line)
        self.canvas.refresh()

    def setIgnoreClick(self, ignore):
        """Used to keep the tool from registering clicks during modal dialogs"""
        self.ignoreclick = ignore

    def showSettingsWarning(self):
        pass

    def activate(self):
        mc = self.canvas
        mc.setCursor(self.cursor)
        # Check whether Geometry is a Line or a Polygon
        layer = mc.currentLayer()
        self.type = layer.geometryType()
        # toolbar button is only active with editable line and polygon layers
        self.isPolygon = (self.type != QGis.Line)

    def deactivate(self):
        pass

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return True
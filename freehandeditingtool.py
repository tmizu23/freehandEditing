# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

class FreehandEditingTool(QgsMapTool):

    rbFinished = pyqtSignal('QgsGeometry*','bool')
    editFinished = pyqtSignal('QgsGeometry*', 'int')

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.snapping = True
        self.snapavoidbool = True
        self.state = "free" #free,drawing,draw_suspended,selected,editing,edit_suspended
        self.rb = None
        self.oldrbgeom = None
        self.startmarker = None
        self.vmarker = None
        self.startpoint = None
        self.lastpoint = None
        self.mCtrl = False
        self.mShift =False
        self.featid_list = []
        self.ignoreclick = False
        self.layer = False
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
        #QgsMessageLog.logMessage("start freehand plugin", 'MyPlugin', QgsMessageLog.INFO)

    def keyPressEvent(self, event):

        if event.key() == Qt.Key_Escape:
            if self.state == "draw_suspended":
                self.rb.reset()
                self.rb = QgsRubberBand(self.canvas, QGis.Polygon)
                self.rb.setColor(QColor(255, 0, 0, 150))
                self.rb.setFillColor(QColor(255, 255, 255, 10))
                self.rb.setWidth(2)
                self.rb.addGeometry(self.oldrbgeom, self.layer)
                self.rb.removeLastPoint()
                self.lastpoint=self.oldlastpoint
                self.vmarker.setCenter(self.lastpoint)
                self.vmarker.show()
                self.canvas.refresh()
            else:
                self.canvas.currentLayer().removeSelection()
                self.state = "free"
                self.featid_list = []
        #QgsMessageLog.logMessage("{}".format(event.key()), 'MyPlugin', QgsMessageLog.INFO)
        if event.key() == Qt.Key_Control:
            self.mCtrl = True
            #QgsMessageLog.logMessage("{}".format(self.mCtrl), 'MyPlugin', QgsMessageLog.INFO)


    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.mCtrl = False

    def getSnapPoint(self,event,layer):
        result = []
        self.snapmarker.hide()
        x = event.pos().x()
        y = event.pos().y()
        #QgsMessageLog.logMessage("snapping:{}".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
        if self.snapping:
            startingPoint = QPoint(x, y)
            snapper = QgsMapCanvasSnapper(self.canvas)
            (retval, result) = snapper.snapToCurrentLayer(startingPoint,QgsSnapper.SnapToVertex)
            if result:
                point = result[0].snappedVertex
                self.snapmarker.setCenter(point)
                self.snapmarker.show()
                point = self.toLayerCoordinates(layer,point)
                #QgsMessageLog.logMessage("a".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
            else:
                point = self.toLayerCoordinates(layer, event.pos())
                #QgsMessageLog.logMessage("b".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
        else:
            point = self.toLayerCoordinates(layer, event.pos())
            #QgsMessageLog.logMessage("c".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)

        pnt = self.toMapCoordinates(layer, point)

        #新規で再開地点にスナップ
        d = 10
        if self.state == "draw_suspended" or self.state == "edit_suspended":
            if (self.lastpoint.x()-d <= pnt.x() <= self.lastpoint.x()+d) and (self.lastpoint.y()-d<=pnt.y() <= self.lastpoint.y()+d):
                self.snapmarker.setCenter(self.lastpoint)
                self.snapmarker.show()
                pnt = self.lastpoint
                #QgsMessageLog.logMessage("d".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
        #新規でポリゴンを閉じる時、スタート地点にスナップ
        if self.state=="drawing" or self.state=="editing":#or self.state=="selected":
            if (self.startpoint.x()-d <= pnt.x() <= self.startpoint.x()+d) and (self.startpoint.y()-d<=pnt.y() <= self.startpoint.y()+d):
                #QgsMessageLog.logMessage("e".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
                self.snapmarker.setCenter(self.startpoint)
                self.snapmarker.show()
                pnt= self.startpoint
        return pnt,result

    def objselect(self,event):
        point = self.toLayerCoordinates(self.layer, event.pos())
        d = self.canvas.mapUnitsPerPixel() * 4
        request = QgsFeatureRequest()
        request.setLimit(1)
        request.setFilterRect(QgsRectangle((point.x() - d), (point.y() - d), (point.x() + d), (point.y() + d)))
        f = [feat for feat in self.layer.getFeatures(request)]  # only one because of setlimit(1)
        if len(f)==1:
            #既存の図形あり
            if f[0].id() in self.featid_list:
                idx = self.featid_list.index(f[0].id())
                self.featid_list.pop(idx)
                self.layer.deselect(f[0].id())
                #残っているなら
                if len(self.featid_list)>0:
                    self.state = "selected"
                #ないなら
                else:
                    self.state = "free"
            else:
                #新規図形
                self.featid_list.append(f[0].id())
                #選択追加。
                self.layer.select(self.featid_list)
                self.state = "selected"
        #図形なし。なにもしない
        else:
            pass

    def canvasPressEvent(self, event):
        if self.ignoreclick:
            # ignore secondary canvasPressEvents if already drag-drawing
            # NOTE: canvasReleaseEvent will still occur (ensures rb is deleted)
            # click on multi-button input device will halt drag-drawing
            return
        if not self.layer:
            return
        button_type = event.button()
        self.check_snapsetting()

        # select one feature
        if self.state == "free"  and button_type == 2:
            self.objselect(event)
        # select two feature
        elif self.state == "selected" and button_type == 2 and not self.mCtrl:
            self.objselect(event)
        # merge
        elif self.state == "selected" and button_type == 2 and self.mCtrl and len(self.featid_list) >= 2:
            #QgsMessageLog.logMessage("merge", 'MyPlugin', QgsMessageLog.INFO)

            point = self.toLayerCoordinates(self.layer, event.pos())
            d = self.canvas.mapUnitsPerPixel() * 4
            request = QgsFeatureRequest()
            request.setFilterRect(QgsRectangle((point.x() - d), (point.y() - d), (point.x() + d), (point.y() + d)))
            f = [feat for feat in self.layer.getFeatures(request)]  # only one because of setlimit(1)
            if len(f)>0:
                select_feat = f[0]
                if select_feat.id() in self.featid_list:
                    self.featid_list.remove(select_feat.id())
                    features = self.layer.getFeatures(QgsFeatureRequest().setFilterFids(self.featid_list))
                    geom = QgsGeometry(select_feat.geometry())
                    for f in features:
                        geom = QgsGeometry(geom.combine(f.geometry()))
                    self.layer.beginEditCommand("Feature merge")
                    self.layer.deleteFeatures(self.featid_list)
                    self.layer.changeGeometry(select_feat.id(), geom)
                    self.layer.endEditCommand()
            self.state = "free"
            self.canvas.currentLayer().removeSelection()
            self.featid_list = []
            self.rb.reset()
            self.rb = None
            self.startmarker.hide()
            self.vmarker.hide()
            self.canvas.refresh()

        # start editing
        elif button_type == 1 and len(self.featid_list) >= 1 and self.state == "selected":
            self.set_rb()
            pnt, result = self.getSnapPoint(event, self.layer)
            self.rb.addPoint(pnt)
            self.startmarker.setCenter(pnt)
            self.startmarker.show()
            self.startpoint = pnt
            self.lastpoint = pnt
            self.state = "editing"
        # start drawing
        elif button_type == 1 and self.state == "free":
            self.set_rb()
            pnt, result = self.getSnapPoint(event, self.layer)
            self.rb.addPoint(pnt)
            self.startmarker.setCenter(pnt)
            self.startmarker.show()
            self.startpoint = pnt
            self.lastpoint = pnt
            self.state = "drawing"
        # restart editing
        elif button_type == 1 and self.state == "edit_suspended":
            self.oldrbgeom = self.rb.asGeometry()
            self.oldlastpoint = self.lastpoint
            self.state = "editing"
        # restart drawing
        elif button_type == 1 and self.state == "draw_suspended":
            self.oldrbgeom = self.rb.asGeometry()
            self.oldlastpoint = self.lastpoint
            self.state = "drawing"
        # finish editing
        elif button_type == 2 and self.state=="edit_suspended":
            if self.rb.numberOfVertices() > 2:
                rbgeom=self.rb.asGeometry()
                self.checkcrs()
                if self.layerCRSSrsid != self.projectCRSSrsid:
                    rbgeom.transform(QgsCoordinateTransform(self.projectCRSSrsid,self.layerCRSSrsid))
                features=self.layer.getFeatures(QgsFeatureRequest().setFilterFids(self.featid_list))
                for f in features:
                    featid = f.id()
                    drawline = QgsGeometry(rbgeom)
                    startpnt = drawline.asPolyline()[0]
                    lastpnt = drawline.asPolyline()[-1]
                    #分割
                    if self.mCtrl:
                        #QgsMessageLog.logMessage("split", 'MyPlugin', QgsMessageLog.INFO)
                        #toleranceの値取得
                        settings = QSettings()
                        if self.layer.crs().projectionAcronym() == "longlat":
                            tolerance = 0.000
                        else:
                            tolerance = settings.value("/freehandEdit/tolerance",
                                                       0.000, type=float)
                        self.layer.beginEditCommand("Feature split")
                        drawline = rbgeom
                        s = drawline.simplify(tolerance)
                        splitline = [QgsPoint(pair[0], pair[1]) for pair in s.asPolyline()]
                        self.layer.splitFeatures(splitline,True)
                        self.layer.endEditCommand()

                    # 穴を開ける.交差していない。始点と終点が同じ
                    elif f.geometry().contains(rbgeom) and startpnt[0]==lastpnt[0] and startpnt[1]==lastpnt[1]:
                        obj = []
                        for poly in f.geometry().asPolygon():
                            obj.append([QgsPoint(pair[0], pair[1]) for pair in poly])
                        polyline = rbgeom.asPolyline()
                        ring = [QgsPoint(pair[0], pair[1]) for pair in polyline]
                        obj.append(ring)
                        geom = QgsGeometry.fromPolygon(obj)
                        self.editFinished.emit(geom, featid)

                    # 修正
                    else:
                        obj=[]
                        #リングごとに修正
                        for poly in f.geometry().asPolygon():
                            geom = QgsGeometry.fromPolygon([[QgsPoint(pair[0], pair[1]) for pair in poly]])
                            objline = [QgsPoint(pair[0], pair[1]) for pair in poly]
                            geomline = QgsGeometry.fromPolyline(objline)
                            snapstart = geomline.intersects(QgsGeometry.fromPoint(QgsPoint(startpnt[0], startpnt[1])))
                            snaplast = geomline.intersects(QgsGeometry.fromPoint(QgsPoint(lastpnt[0], lastpnt[1])))
                            # 編集のラインを図形のラインで分割。交差する部分を出す。
                            success, splits, topo = drawline.splitGeometry(objline, True)
                            polyline = []
                            # 始点、終点ともにスナップ
                            if snapstart and snaplast:
                                startidx = geom.closestVertexWithContext(startpnt)[1]
                                lastidx = geom.closestVertexWithContext(lastpnt)[1]
                                polyline = rbgeom.asPolyline()
                                poly = self.objmodify(geom, polyline, startidx, lastidx)
                            # 始点、終点ともにスナップしていない。最初と最後の交差部を始点、終点にする
                            elif not snapstart and not snaplast and len(splits) > 1:
                                startpnt = drawline.asPolyline()[-1]
                                startidx = geom.closestSegmentWithContext(startpnt)[2]
                                geom.insertVertex(startpnt[0], startpnt[1], startidx)

                                lastpnt = splits[-1].asPolyline()[0]
                                lastidx = geom.closestSegmentWithContext(lastpnt)[2]
                                geom.insertVertex(lastpnt[0], lastpnt[1], lastidx)
                                # startidxの方が大きい場合、lastidxが挿入されてidがズレるため
                                if startidx >= lastidx:
                                    startidx = startidx + 1
                                # 始点と終点の間のラインを1本につなぐ。splitされた最初のセグメントは、drawline。以降は、splits。
                                polyline = splits[0].asPolyline()
                                for g in splits[1:-1]:
                                    polyline.extend(g.asPolyline()[1:])  # セグメントの始点は重複するので2つ目から
                                poly = self.objmodify(geom, polyline, startidx, lastidx)
                            # 始点だけがスナップしている。最後の交差部分を終点にする
                            elif snapstart and len(splits) > 0:
                                startidx = geom.closestVertexWithContext(startpnt)[1]
                                lastpnt = splits[-1].asPolyline()[0]
                                lastidx = geom.closestSegmentWithContext(lastpnt)[2]
                                geom.insertVertex(lastpnt[0], lastpnt[1], lastidx)
                                # startidxの方が大きい場合、lastidxが挿入されてidがズレるため
                                if startidx >= lastidx:
                                    startidx = startidx + 1
                                # 始点と終点の間のラインを1本につなぐ
                                polyline = drawline.asPolyline()
                                for g in splits[:-1]:
                                    polyline.extend(g.asPolyline()[1:])
                                poly = self.objmodify(geom, polyline, startidx, lastidx)
                            # 終点だけがスナップしている。最初の交差部分を始点にする
                            elif snaplast and len(splits) > 0:
                                lastidx = geom.closestVertexWithContext(lastpnt)[1]
                                startpnt = drawline.asPolyline()[-1]
                                startidx = geom.closestSegmentWithContext(startpnt)[2]
                                geom.insertVertex(startpnt[0], startpnt[1], startidx)
                                # startidxの方が大きい場合、lastidxが挿入されてidがズレるため
                                if startidx <= lastidx:
                                    lastidx = lastidx + 1
                                # 始点と終点の間のラインを1本につなぐ。
                                polyline = splits[0].asPolyline()
                                for g in splits[1:]:
                                    polyline.extend(g.asPolyline()[1:])  # セグメントの始点は重複するので2つ目から
                                poly = self.objmodify(geom, polyline, startidx, lastidx)
                            else:
                                #関係ないリングはそのまま
                                pass
                            obj.append(poly)
                        geom = QgsGeometry.fromPolygon(obj)
                        self.editFinished.emit(geom, featid)

            self.state = "free"
            self.canvas.currentLayer().removeSelection()
            self.featid_list = []
            self.rb.reset()
            self.rb = None
            self.startmarker.hide()
            self.vmarker.hide()
            self.canvas.refresh()

        # finish drawing
        elif button_type == 2 and self.state == "draw_suspended":
            if self.rb.numberOfVertices() > 2:
                self.layer.beginEditCommand("Feature added")
                #線と重なるフィーチャ選択
                for f in self.layer.getFeatures():
                    drawline = QgsGeometry(self.rb.asGeometry())
                    if drawline.intersects(f.geometry()):
                        #フィーチャとクロスする点を追加
                        geom = QgsGeometry(f.geometry())
                        objline = [QgsPoint(pair[0], pair[1]) for pair in geom.asPolygon()[0]]
                        success, splits, topo = drawline.splitGeometry(objline, True)
                        for s in splits:
                            pnt = s.asPolyline()[0]
                            pntidx = geom.closestSegmentWithContext(pnt)[2]
                            geom.insertVertex(pnt[0], pnt[1], pntidx)
                        self.layer.changeGeometry(f.id(), geom)

                poly = self.rb.asGeometry().asPolyline()
                geom = QgsGeometry.fromPolygon([[QgsPoint(pair[0], pair[1]) for pair in poly]])
                self.rbFinished.emit(geom, self.snapavoidbool)

            # reset rubberband and refresh the canvas
            self.state = "free"
            self.canvas.currentLayer().removeSelection()
            self.rb.reset()
            self.rb = None
            self.vmarker.hide()
            self.startmarker.hide()
            self.canvas.refresh()

    def objmodify(self,geom,polyline,startidx,lastidx):
        poly = geom.asPolygon()[0]
        # 始点、終点を逆にする.idxを0からに変更
        if startidx < lastidx:
            polyline.reverse()
            n = lastidx - startidx + 1
            idx = startidx - 1
        else:
            n = startidx - lastidx + 1
            idx = lastidx - 1
        # 重複削除、入れ替え
        poly = poly[:-1]
        tmp = poly[0:idx + 1]
        del poly[0:idx + 1]
        poly.extend(tmp)

        # p1
        p1 = poly[:]
        # 修正箇所削除
        del p1[0:n]
        # 挿入
        for (x0, y0) in polyline:
            p1.insert(0, (x0, y0))
        p1.append(p1[0])
        poly1= [QgsPoint(pair[0], pair[1]) for pair in p1]
        geom1 = QgsGeometry.fromPolygon([poly1])
        # p2
        p2 = poly[:]
        # 修正箇所削除
        del p2[n - 1:]
        del p2[0]
        p2.extend(polyline)
        p2.append(p2[0])
        poly2 = [QgsPoint(pair[0], pair[1]) for pair in p2]
        geom2 = QgsGeometry.fromPolygon([poly2])
        if geom1.area() > geom2.area():
            #geom = geom1
            poly = poly1
        else:
            #geom = geom2
            poly = poly2

        return poly


    def canvasMoveEvent(self, event):
        if not self.layer:
            return
        #ポイントに近いポイント
        pnt,result = self.getSnapPoint(event, self.layer)

        #編集
        if self.state=="editing":
            self.lastpoint = pnt
            self.rb.addPoint(pnt)
        #新規、描画中
        elif self.state == "drawing":
            self.lastpoint = pnt
            self.rb.addPoint(pnt)


    def canvasReleaseEvent(self, event):

        # edit suspend
        if self.state == "editing":
            #QgsMessageLog.logMessage("edit_suspended", 'MyPlugin', QgsMessageLog.INFO)
            self.vmarker.setCenter(self.lastpoint)
            self.vmarker.show()
            self.state = "edit_suspended"
        # edit suspend
        elif self.state == "drawing":
            self.vmarker.setCenter(self.lastpoint)
            self.vmarker.show()
            self.state = "draw_suspended"

    def set_rb(self):
        self.rb = QgsRubberBand(self.canvas)
        self.rb.setColor(QColor(255, 0, 0, 150))
        self.rb.setWidth(2)

    def checkcrs(self):
        renderer = self.canvas.mapSettings()
        self.layerCRSSrsid = self.layer.crs().srsid()
        self.projectCRSSrsid = renderer.destinationCrs().srsid()
        #QgsMessageLog.logMessage("{},{}".format(self.layerCRSSrsid,self.projectCRSSrsid), 'MyPlugin', QgsMessageLog.INFO)

    def check_snapsetting(self):
        proj = QgsProject.instance()
        snapmode = proj.readEntry('Digitizing', 'SnappingMode')[0]
        #QgsMessageLog.logMessage("snapmode:{}".format(snapmode), 'MyPlugin', QgsMessageLog.INFO)
        if snapmode == "advanced":
            snaplayer = proj.readListEntry('Digitizing', 'LayerSnappingList')[0]
            snapenabled = proj.readListEntry('Digitizing', 'LayerSnappingEnabledList')[0]
            snapavoid = proj.readListEntry('Digitizing', 'AvoidIntersectionsList')[0]
            layerid = self.canvas.currentLayer().id()
            if layerid in snaplayer:#新規のレイヤーだとない場合がある？
                snaptype = snapenabled[snaplayer.index(layerid)]
                #QgsMessageLog.logMessage("snaptype:{}".format(snaptype), 'MyPlugin', QgsMessageLog.INFO)
                self.snapavoidbool = self.canvas.currentLayer().id() in snapavoid
                if snaptype == "disabled":
                    self.snapping = False
                else:
                    self.snapping = True
            else:
                self.snapping = True
        else:
            snaptype = proj.readEntry('Digitizing', 'DefaultSnapType')[0]
            if snaptype == "off":
                self.snapping = False
            else:
                self.snapping = True
            self.snapavoidbool = False

    def setIgnoreClick(self, ignore):
        """Used to keep the tool from registering clicks during modal dialogs"""
        self.ignoreclick = ignore

    def showSettingsWarning(self):
        pass

    def activate(self):
        mc = self.canvas
        mc.setCursor(self.cursor)
        self.layer = mc.currentLayer()
        self.checkcrs()
        # Check whether Geometry is a Line or a Polygon

        self.snapmarker = QgsVertexMarker(self.canvas)
        self.snapmarker.setIconType(QgsVertexMarker.ICON_BOX)
        self.snapmarker.setColor(QColor(255,165,0))
        self.snapmarker.setPenWidth(3)
        self.snapmarker.hide()
        self.check_snapsetting()
        self.startmarker = QgsVertexMarker(self.canvas)
        self.startmarker.setIconType(QgsVertexMarker.ICON_X)
        self.startmarker.hide()
        self.vmarker = QgsVertexMarker(self.canvas)
        self.vmarker.setIconType(QgsVertexMarker.ICON_X)
        self.vmarker.hide()


    def deactivate(self):
        pass

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return True
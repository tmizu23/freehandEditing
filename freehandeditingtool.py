# -*- coding: utf-8 -*-

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

class FreehandEditingTool(QgsMapTool):


    def __init__(self, canvas,iface):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.iface = iface
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
        if self.snapping:
            startingPoint = QPoint(x, y)
            snapper = QgsMapCanvasSnapper(self.canvas)
            (retval, result) = snapper.snapToCurrentLayer(startingPoint,QgsSnapper.SnapToVertex)
            if result:
                point = result[0].snappedVertex
                self.snapmarker.setCenter(point)
                self.snapmarker.show()
                point = self.toLayerCoordinates(layer,point)
            else:
                point = self.toLayerCoordinates(layer, event.pos())
        else:
            point = self.toLayerCoordinates(layer, event.pos())

        pnt = self.toMapCoordinates(layer, point)

        #再開地点にスナップ。rbは通常のスナップ機能は有効でないため自分で実装
        d = self.canvas.mapUnitsPerPixel() * 4
        if self.state == "draw_suspended" or self.state == "edit_suspended":
            if (self.lastpoint.x()-d <= pnt.x() <= self.lastpoint.x()+d) and (self.lastpoint.y()-d<=pnt.y() <= self.lastpoint.y()+d):
                self.snapmarker.setCenter(self.lastpoint)
                self.snapmarker.show()
                pnt = self.lastpoint
                #QgsMessageLog.logMessage("d".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
        #ポリゴンを閉じる時、スタート地点にスナップ
        if self.state=="drawing" or self.state=="editing":#or self.state=="selected":
            if (self.startpoint.x()-d <= pnt.x() <= self.startpoint.x()+d) and (self.startpoint.y()-d<=pnt.y() <= self.startpoint.y()+d):
                #QgsMessageLog.logMessage("e".format(self.snapping), 'MyPlugin', QgsMessageLog.INFO)
                self.snapmarker.setCenter(self.startpoint)
                self.snapmarker.show()
                pnt= self.startpoint
        return pnt,result

    def select_obj(self,event):
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

    def merge_obj(self,event):
        point = self.toLayerCoordinates(self.layer, event.pos())
        d = self.canvas.mapUnitsPerPixel() * 4
        request = QgsFeatureRequest()
        request.setFilterRect(QgsRectangle((point.x() - d), (point.y() - d), (point.x() + d), (point.y() + d)))
        f = [feat for feat in self.layer.getFeatures(request)]  # only one because of setlimit(1)
        if len(f) > 0:
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

    def split_obj(self,rbgeom):
        # QgsMessageLog.logMessage("split", 'MyPlugin', QgsMessageLog.INFO)
        # toleranceの値取得
        tolerance = self.get_tolerance()
        self.layer.beginEditCommand("Feature split")
        drawline = rbgeom
        s = drawline.simplify(tolerance)
        splitline = [QgsPoint(pair[0], pair[1]) for pair in s.asPolyline()]
        self.layer.splitFeatures(splitline, True)
        self.layer.endEditCommand()
    
    def hole_obj(self,rbgeom,f):
        obj = []
        featid = f.id()
        for poly in f.geometry().asPolygon():
            obj.append([QgsPoint(pair[0], pair[1]) for pair in poly])
        polyline = rbgeom.asPolyline()
        ring = [QgsPoint(pair[0], pair[1]) for pair in polyline]
        obj.append(ring)
        geom = QgsGeometry.fromPolygon(obj)
        self.editFeature(geom, featid)

    def modify_obj(self,rbgeom,f):
        obj = []
        featid = f.id()
        drawline = QgsGeometry(rbgeom)
        startpnt = drawline.asPolyline()[0]
        lastpnt = drawline.asPolyline()[-1]
        # リングごとに修正
        for poly in f.geometry().asPolygon():
            geom = QgsGeometry.fromPolygon([[QgsPoint(pair[0], pair[1]) for pair in poly]])
            objline = [QgsPoint(pair[0], pair[1]) for pair in poly]
            geomline = QgsGeometry.fromPolyline(objline)
            #投影法が違うと投影変換でずれてintersectsしない場合がある
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
                poly = self.modify_exec(geom, polyline, startidx, lastidx)
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
                poly = self.modify_exec(geom, polyline, startidx, lastidx)
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
                poly = self.modify_exec(geom, polyline, startidx, lastidx)
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
                poly = self.modify_exec(geom, polyline, startidx, lastidx)
            else:
                # 関係ないリングはそのまま
                pass
            obj.append(poly)
        geom = QgsGeometry.fromPolygon(obj)
        self.editFeature(geom, featid)

    def modify_exec(self, geom, polyline, startidx, lastidx):
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
        poly1 = [QgsPoint(pair[0], pair[1]) for pair in p1]
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
            # geom = geom1
            poly = poly1
        else:
            # geom = geom2
            poly = poly2

        return poly

    def createFeature(self, geom):
        settings = QSettings()
        provider = self.layer.dataProvider()

        self.check_crs()
        # On the Fly reprojection.
        if self.layerCRSSrsid != self.projectCRSSrsid:
            geom.transform(QgsCoordinateTransform(self.projectCRSSrsid,
                                                  self.layerCRSSrsid))
        tolerance = self.get_tolerance()
        s = geom.simplify(tolerance)
        if self.snapavoidbool:
            s.avoidIntersections()
        # validate geometry
        f = QgsFeature()
        if not (s.validateGeometry()):
            f.setGeometry(s)
        else:
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                'Feature not valid',
                "The geometry of the feature you just added isn't valid."
                "Do you want to use it anyway?",
                QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                f.setGeometry(s)
            else:
                self.layer.endEditCommand()
                return
        # add attribute fields to feature
        fields = self.layer.pendingFields()
        f.initAttributes(fields.count())
        for i in range(fields.count()):
            if provider.defaultValue(i):
                f.setAttribute(i, provider.defaultValue(i))
        if (settings.value(
                "/qgis/digitizing/disable_enter_attribute_values_dialog",
                False, type=bool)):
            # layer.beginEditCommand("Feature added")
            self.layer.addFeature(f)
            self.layer.endEditCommand()
        else:
            dlg = self.iface.getFeatureForm(self.layer, f)
            self.setIgnoreClick(True)
            # layer.beginEditCommand("Feature added")
            if dlg.exec_():
                self.layer.endEditCommand()
            else:
                self.layer.destroyEditCommand()
            self.setIgnoreClick(False)

    def editFeature(self, geom, fid):
        tolerance = self.get_tolerance()
        s = geom.simplify(tolerance)
        # validate geometry
        if s.validateGeometry():
            reply = QMessageBox.question(
                self.iface.mainWindow(),
                'Feature not valid',
                "The geometry of the feature you just added isn't valid."
                "Do you want to use it anyway?",
                QMessageBox.Yes, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        self.layer.beginEditCommand("Feature edited")
        self.layer.changeGeometry(fid, s)
        self.layer.endEditCommand()

    def canvasPressEvent(self, event):
        if self.ignoreclick:
            # ignore secondary canvasPressEvents if already drag-drawing
            # NOTE: canvasReleaseEvent will still occur (ensures rb is deleted)
            # click on multi-button input device will halt drag-drawing
            return
        self.layer = self.canvas.currentLayer()
        if not self.layer:
            return
        button_type = event.button()
        self.check_snapsetting()
        if self.state == "free" or self.state=="selected":
            self.check_selection()
        # select one feature
        if self.state == "free"  and button_type == 2:
            self.select_obj(event)
        # select two feature
        elif self.state == "selected" and button_type == 2 and not self.mCtrl:
            self.select_obj(event)
        # merge
        elif self.state == "selected" and button_type == 2 and self.mCtrl and len(self.featid_list) >= 2:
            #QgsMessageLog.logMessage("merge", 'MyPlugin', QgsMessageLog.INFO)
            self.merge_obj(event)
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
                #描画ラインを画面の投影からレイヤの投影に変換
                self.check_crs()
                if self.layerCRSSrsid != self.projectCRSSrsid:
                    rbgeom.transform(QgsCoordinateTransform(self.projectCRSSrsid,self.layerCRSSrsid))
                features=self.layer.getFeatures(QgsFeatureRequest().setFilterFids(self.featid_list))
                #選択フィーチャ全部に対して処理
                for f in features:
                    #分割
                    if self.mCtrl:
                        self.split_obj(rbgeom)
                    # 穴を開ける.交差していない。始点と終点が同じ
                    elif f.geometry().contains(rbgeom) and rbgeom.asPolyline()[0][0]==rbgeom.asPolyline()[-1][0] and rbgeom.asPolyline()[0][1]==rbgeom.asPolyline()[-1][1]:
                        self.hole_obj(rbgeom,f)
                    # 修正
                    else:
                        self.modify_obj(rbgeom,f)
            else:
                pass
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
                self.createFeature(geom)

            # reset rubberband and refresh the canvas
            self.state = "free"
            self.canvas.currentLayer().removeSelection()
            self.rb.reset()
            self.rb = None
            self.vmarker.hide()
            self.startmarker.hide()
            self.canvas.refresh()

 
    def canvasMoveEvent(self, event):
        self.layer = self.canvas.currentLayer()
        if not self.layer:
            return
        #ポイントに近いポイント
        pnt,result = self.getSnapPoint(event, self.layer)
        #作成中、編集中
        if self.state=="editing" or self.state=="drawing":
            self.lastpoint = pnt
            self.rb.addPoint(pnt)

    def canvasReleaseEvent(self, event):

        # edit suspend
        if self.state == "editing":
            self.vmarker.setCenter(self.lastpoint)
            self.vmarker.show()
            self.state = "edit_suspended"
        # draw suspend
        elif self.state == "drawing":
            self.vmarker.setCenter(self.lastpoint)
            self.vmarker.show()
            self.state = "draw_suspended"

    def set_rb(self):
        self.rb = QgsRubberBand(self.canvas)
        self.rb.setColor(QColor(255, 0, 0, 150))
        self.rb.setWidth(2)

    def check_crs(self):
        renderer = self.canvas.mapSettings()
        self.layerCRSSrsid = self.layer.crs().srsid()
        self.projectCRSSrsid = renderer.destinationCrs().srsid()
        #QgsMessageLog.logMessage("{},{}".format(self.layerCRSSrsid,self.projectCRSSrsid), 'MyPlugin', QgsMessageLog.INFO)

    def get_tolerance(self):
        settings = QSettings()
        if self.layer.crs().projectionAcronym() == "longlat":
            tolerance = 0.000
        else:
            tolerance = settings.value("/freehandEdit/tolerance",
                                       0.000, type=float)
        return tolerance

    def check_selection(self):
        self.featid_list = self.layer.selectedFeaturesIds()
        if len(self.featid_list) > 0:
            self.state = "selected"
        else:
            self.state = "free"

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
        self.canvas.setCursor(self.cursor)
        self.layer = self.canvas.currentLayer()
        self.check_crs()
        self.check_snapsetting()
        self.snapmarker = QgsVertexMarker(self.canvas)
        self.snapmarker.setIconType(QgsVertexMarker.ICON_BOX)
        self.snapmarker.setColor(QColor(255,165,0))
        self.snapmarker.setPenWidth(3)
        self.snapmarker.setIconSize(20)
        self.snapmarker.hide()
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




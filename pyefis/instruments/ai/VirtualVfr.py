#  Copyright (c) 2018-2019 Garrett Herschleb
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import copy
import math
import time
import threading
import os

from geomag import declination

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import logging

import pyavtools.fix as fix

from pyefis.instruments.ai import AI
import pyavtools.Spatial as Spatial
import pyavtools.CIFPObjects as CIFPObjects

log = logging.getLogger(__name__)

M_PI = math.pi
RAD_DEG = M_PI / 180.0
DEG_RAD = 180.0 / M_PI

METERS_FOOT = 0.3048
FEET_METER = 1.0 / METERS_FOOT
EARTH_RADIUS_M=6356752.0
EARTH_RADIUS=EARTH_RADIUS_M * FEET_METER

class VirtualVfr(AI):
    CENTERLINE_WIDTH = 3
    MIN_FONT_SIZE=7
    RUNWAY_LABEL_FONT_FAMILY="Courier"
    AIRPORT_FONT_FAMILY="Sans"
    AIRPORT_FONT_SIZE=9
    PAPI_YOFFSET = 8
    PAPI_LIGHT_SPACING = 9
    VORTAC_ICON_PATH="vortac.png"
    def __init__(self, parent=None, font_percent=None):
        super(VirtualVfr, self).__init__(parent, font_percent=font_percent)
        self.display_objects = dict()
        time.sleep(.6)      # Pause to let DB load

        self.font_percent = font_percent
        self._VFROld = dict()
        self._VFRBad = dict()
        self._VFRFail = dict()
        for p in ['LAT', 'HEAD', 'ALT', 'LONG']:
            self._VFROld[p] = True
            self._VFRBad[p] = True
            self._VFRFail[p] = True

        self.lng_item = fix.db.get_item("LONG")
        self.lat_item = fix.db.get_item("LAT")
        self.head_item = fix.db.get_item("HEAD")
        self.alt_item = fix.db.get_item("ALT")
        self._VFROld['LONG'] = self.lng_item.old
        self._VFRBad['LONG'] = self.lng_item.bad
        self._VFRFail['LONG'] = self.lng_item.fail
        self.lng = self.lng_item.value

        self._VFROld['LAT'] = self.lat_item.old
        self._VFRBad['LAT'] = self.lat_item.bad
        self._VFRFail['LAT'] = self.lat_item.fail
        self.lat = self.lat_item.value

        self._VFROld['HEAD'] = self.head_item.old
        self._VFRBad['HEAD'] = self.head_item.bad
        self._VFRFail['HEAD'] = self.head_item.fail
        self.head = self.head_item.value

        # BUG: convert magnetic heading
        self.true_heading = self.head_item.value

        self._VFROld['ALT'] = self.alt_item.old
        self._VFRBad['ALT'] = self.alt_item.bad
        self._VFRFail['ALT'] = self.alt_item.fail
        self.altitude = self.alt_item.value

        self.last_mag_update = 0
        self.magnetic_declination = None
        self.missing_lat = True
        self.missing_lng = True
  
        self.myparent = parent
        minfont = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, VirtualVfr.MIN_FONT_SIZE, QFont.Bold)
        t = QGraphicsSimpleTextItem ("9 9")
        t.setFont (minfont)
        self.min_font_width = t.boundingRect().width()
        self.pov = None

    def resizeEvent(self, event):
        super(VirtualVfr, self).resizeEvent(event)
        self.pov = PointOfView(os.path.expanduser(self.myparent.get_config_item('dbpath')),
                               os.path.expanduser(self.myparent.get_config_item('indexpath')),
                               self.myparent.get_config_item('refresh_period'))
        self.pov.initialize(["Runway", "Airport"], self.scene.width(),
                    self.lng, self.lat, self.altitude, self.true_heading)

        # Must happen here to prevent race
        self.lng_item.valueChanged[float].connect(self.setLongitude)
        self.lng_item.badChanged[bool].connect(self.setLngBad)
        self.lng_item.oldChanged[bool].connect(self.setLngOld)
        self.lng_item.failChanged[bool].connect(self.setLngFail)
        self.lat_item.valueChanged[float].connect(self.setLatitude)
        self.lat_item.badChanged[bool].connect(self.setLatBad)
        self.lat_item.oldChanged[bool].connect(self.setLatOld)
        self.lat_item.failChanged[bool].connect(self.setLatFail)
        self.head_item.valueChanged[float].connect(self.setHeading)
        self.head_item.badChanged[bool].connect(self.setHeadBad)
        self.head_item.oldChanged[bool].connect(self.setHeadOld)
        self.head_item.failChanged[bool].connect(self.setHeadFail)
        self.alt_item.valueChanged[float].connect(self.setAltitude)
        self.alt_item.badChanged[bool].connect(self.setAltBad)
        self.alt_item.oldChanged[bool].connect(self.setAltOld)
        self.alt_item.failChanged[bool].connect(self.setAltFail)

        if not self.rendering_prohibited():
            self.pov.render(self)

    def get_largest_font_size(self, width):
        max_size = 25
        min_size = VirtualVfr.MIN_FONT_SIZE
        incr = (max_size - min_size) / 4
        ret = (max_size - min_size) / 2
        t = QGraphicsSimpleTextItem ("9 9")
        while True:
            font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, qRound(ret), QFont.Bold)
            t.setFont (font)
            if t.boundingRect().width() * 1.5 > width:
                max_size = ret
                ret -= incr
                if ret < min_size:
                    ret = min_size
                    break
            else:
                break
        incr = int((max_size - min_size) / 2)
        while incr > 0:
            ret += incr
            font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, qRound(ret), QFont.Bold)
            t.setFont (font)
            if t.boundingRect().width() * 1.1 > width:
                ret -= incr
                incr /= 2
                incr = int(incr)
        return ret

    def get_runway_labels(self, name):
        rwnum_string = ''.join([d for d in name if d >= '0' and d <= '9'])
        rwnum = int(rwnum_string)
        postfix = name[4:]
        ret = [rwnum_string + postfix]
        rwnum += 18
        if rwnum > 36:
            rwnum -= 36
        rwnum_string = str(rwnum)
        if len(rwnum_string) == 1:
            rwnum_string = "0" + rwnum_string
        recip_postfix = {"L":"R", "C":"C", "R":"L", "W":"W", "":""}
        ret.append(rwnum_string + recip_postfix[postfix])
        return ret

    def render_runway(self, p11, p12, p21, p22, touchdown_distance,
                            elevation, length, bearing, name, airport_id, zoom):
        if not self.isVisible():
            return

        rwlabels = self.get_runway_labels (name)
        if p11[1] > p21[1]:
            draw_width = abs(p11[0] - p12[0])
            if p11[0] < p12[0]:
                left_bottom = p11
            else:
                left_bottom = p12
            label = rwlabels[0]
        else:
            draw_width = abs(p21[0] - p22[0])
            if p21[0] < p22[0]:
                left_bottom = p21
            else:
                left_bottom = p22
            label = rwlabels[1]

        key = name+airport_id
        if key in self.display_objects:
            # print ("update existing runway polygon %s"%key)
            poly = QPolygonF([QPointF(*p11), QPointF(*p12), QPointF(*p21), QPointF(*p22)])
            rw = self.display_objects[key]
            rw.setPolygon(poly)
        else:
            # print ("make new runway polygon %s"%key)
            poly = QPolygonF([QPointF(*p11), QPointF(*p12), QPointF(*p21), QPointF(*p22)])
            pen = QPen(QColor(Qt.white))
            brush = QBrush(QColor(Qt.black))
            if label[-1] == "W":
                brush = QBrush(QColor("#000070"))
            rw = self.scene.addPolygon(poly, pen, brush)
            rw.setX(self.scene.width()/2)
            rw.setY(self.scene.height()/2)
            rw.setZValue(0)
            self.display_objects[key] = rw

        # Add the runway centerline, if appropriate
        xdiff = p11[0] - p12[0]
        ydiff = p11[1] - p12[1]
        dist1 = math.sqrt(xdiff*xdiff + ydiff*ydiff)
        xdiff = p21[0] - p22[0]
        ydiff = p21[1] - p22[1]
        dist2 = math.sqrt(xdiff*xdiff + ydiff*ydiff)
        clpoints = [((p11[0] + p12[0]) / 2.0, (p11[1] + p12[1]) / 2.0)
                   ,((p21[0] + p22[0]) / 2.0, (p21[1] + p22[1]) / 2.0)]
        centerline = None
        centerline_function = get_line(clpoints, FOFY)
        clkey = key + "_c"
        if dist1 > 3 * VirtualVfr.CENTERLINE_WIDTH and dist2 > 3*VirtualVfr.CENTERLINE_WIDTH and \
                abs(clpoints[0][1]-clpoints[1][1]) > 5*VirtualVfr.CENTERLINE_WIDTH:
            # Runway polygon large enough to add a centerline
            cline_function = get_line (clpoints, FOFY)
            if clpoints[0][1] > clpoints[1][1]:
                bottomi = 0
                topi = 1
            else:
                bottomi = 1
                topi = 0
            bottomy = clpoints[bottomi][1]-2*VirtualVfr.CENTERLINE_WIDTH
            clpoints[bottomi] = (F(bottomy, cline_function), bottomy)
            topy = clpoints[topi][1]+2*VirtualVfr.CENTERLINE_WIDTH
            clpoints[topi] = (F(topy, cline_function), topy)
            cline = QLineF(QPointF(*clpoints[0]), QPointF(*clpoints[1]))
            if clkey in self.display_objects:
                 centerline = self.display_objects[clkey]
                 centerline.setLine(cline)
            else:
                clpen = QPen(QBrush(QColor(Qt.white)), VirtualVfr.CENTERLINE_WIDTH, Qt.DashLine)
                clpen.setWidth(VirtualVfr.CENTERLINE_WIDTH)
                centerline = self.scene.addLine (cline, clpen)
                centerline.setX(self.scene.width()/2)
                centerline.setY(self.scene.height()/2)
                centerline.setZValue(0)
                self.display_objects[clkey] = centerline
                #print ("%s centerline because(%f,%f) %s->%s"%(key, dist1, dist2, clpoints[0], clpoints[1]))
            # Add a runway label, if appropriate
            lkey = key + label
            if draw_width > self.min_font_width*1.5:
                #print ("Runway label will fit underneath runway polygon. font size is %d"%font_size)
                font_size = self.get_largest_font_size(draw_width)
                font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, qRound(font_size), QFont.Bold)
                label = label[0] + " " + label[1:]
                if lkey in self.display_objects:
                    # Update label position
                    qlabel = self.display_objects[lkey]
                    qlabel.setFont(font)
                    qlabel.setX(self.scene.width()/2 + left_bottom[0])
                    qlabel.setY(self.scene.height()/2 + left_bottom[1])
                else:
                    # Create new label
                    qlabel = self.scene.addSimpleText(label, font)
                    qlabel.setPen(QPen(QColor(Qt.black)))
                    qlabel.setBrush(QBrush(QColor(Qt.white)))
                    qlabel.setX(self.scene.width()/2 + left_bottom[0])
                    qlabel.setY(self.scene.height()/2 + left_bottom[1])
                    qlabel.setZValue(0)
                    self.display_objects[lkey] = qlabel

            elif lkey in self.display_objects:
                #print ("remove runway label")
                self.scene.removeItem (self.display_objects[lkey])
                del self.display_objects[lkey]
            #print ("make or update runway label finished")

        else:
            if clkey in self.display_objects:
                self.scene.removeItem (self.display_objects[clkey])
                del self.display_objects[clkey]
            rwlabels = self.get_runway_labels (name)
            for label in rwlabels:
                lkey = key + label
                if lkey in self.display_objects:
                    self.scene.removeItem (self.display_objects[lkey])
                    del self.display_objects[lkey]


        # Add an extended centerline, if appropriate
        bottom_intercept = F(self.scene.height()/2, centerline_function)
        elkey = key + "_e"
        pkey = key + "_p"
        if abs(bottom_intercept) < self.scene.width():
            if clpoints[0][1] > clpoints[1][1]:
                touchdown_point = QPointF (*clpoints[0])
            else:
                touchdown_point = QPointF (*clpoints[1])
            extended_point = QPointF(bottom_intercept, self.scene.height()/2)
            eline = QLineF(touchdown_point, extended_point)
            if elkey in self.display_objects:
                 extendedline = self.display_objects[elkey]
                 extendedline.setLine(eline)
            else:
                extendedline = self.scene.addLine (eline,
                    QPen(QColor(Qt.white), 1, Qt.DashLine))
                extendedline.setX(self.scene.width()/2)
                extendedline.setY(self.scene.height()/2)
                extendedline.setZValue(0)
                self.display_objects[elkey] = extendedline
                #print ("%s extendedline %s->%s"%(key, touchdown_point, extended_point))

            # Draw PAPI lights
            height_touchdown = self.altitude - elevation
            approach_angle = math.atan(height_touchdown / touchdown_distance) * DEG_RAD
            self.approach_low = 2.5
            self.approach_slightly_low = 2.8
            self.approach_slightly_high = 3.2
            self.approach_very_high = 3.5
            if approach_angle < self.approach_low:
                papi_redcount = 4
            elif approach_angle < self.approach_slightly_low:
                papi_redcount = 3
            elif approach_angle < self.approach_slightly_high:
                papi_redcount = 2
            elif approach_angle < self.approach_very_high:
                papi_redcount = 1
            else:
                papi_redcount = 0
            papi_total_width = 5 * VirtualVfr.PAPI_LIGHT_SPACING
            x = left_bottom[0] - papi_total_width + VirtualVfr.PAPI_LIGHT_SPACING/2
            y = left_bottom[1] - VirtualVfr.PAPI_YOFFSET
            x += self.scene.width()/2
            y += self.scene.height()/2
            wpen = QPen(QColor(Qt.white))
            rpen = QPen(QColor(Qt.red))
            wbsh = QBrush(QColor(Qt.white))
            rbsh = QBrush(QColor(Qt.red))
            if pkey in self.display_objects:
                lights = self.display_objects[pkey]
            else:
                lights = list()
            for i in range(4):
                rect = QRectF (QPointF(-2,-2), QPointF(2,2))
                pen,bsh = (rpen,rbsh) if papi_redcount > 0 else (wpen,wbsh)
                light = self.scene.addEllipse (rect, pen, bsh)
                light.setX(x)
                light.setY(y)
                if len(lights) < i+1:
                    lights.append(light)
                else:
                    self.scene.removeItem (lights[i])
                    lights[i] = light
                x += VirtualVfr.PAPI_LIGHT_SPACING
                papi_redcount -= 1
                self.display_objects[pkey] = lights
        else:
            if elkey in self.display_objects:
                self.scene.removeItem (self.display_objects[elkey])
                del self.display_objects[elkey]
            if pkey in self.display_objects:
                for l in self.display_objects[pkey]:
                    self.scene.removeItem (l)
                del self.display_objects[pkey]


    def eliminate_runway (self, name, airport_id):
        key = name+airport_id
        if key in self.display_objects:
            self.scene.removeItem (self.display_objects[key])
            del self.display_objects[key]
            clkey = key + "_c"
            if clkey in self.display_objects:
                self.scene.removeItem (self.display_objects[clkey])
                del self.display_objects[clkey]
            elkey = key + "_e"
            if elkey in self.display_objects:
                self.scene.removeItem (self.display_objects[elkey])
                del self.display_objects[elkey]
            elkey = key + "_e"
            if elkey in self.display_objects:
                self.scene.removeItem (self.display_objects[elkey])
                del self.display_objects[elkey]
            rwlabels = self.get_runway_labels (name)
            for l in rwlabels:
                rwlkey = key + l
                if rwlkey in self.display_objects:
                    self.scene.removeItem (self.display_objects[rwlkey])
                    del self.display_objects[rwlkey]
            pkey = key + "_p"
            if pkey in self.display_objects:
                for l in self.display_objects[pkey]:
                    self.scene.removeItem (l)
                del self.display_objects[pkey]


    def render_airport(self, point, name, airport_id, zoom, space_occupied):
        akey = airport_id
        if akey in self.display_objects:
            ap = self.display_objects[akey]
        else:
            font = QFont(VirtualVfr.AIRPORT_FONT_FAMILY, VirtualVfr.AIRPORT_FONT_SIZE, QFont.Bold)
            ap = self.scene.addSimpleText(airport_id, font)
            ap.setPen(QPen(QColor(Qt.blue)))
            ap.setBrush(QBrush(QColor(Qt.white)))
            ap.setZValue(0)
            self.display_objects[akey] = ap
        rect = ap.boundingRect()
        xoff = self.scene.width()/2 + point[0] - rect.width()/2
        ap.setX(xoff)
        yoff = self.scene.height()/2 + point[1] - rect.height()/2
        ap.setY(yoff)
        rect.translate(xoff,yoff)
        for s in space_occupied:
            if s.intersects(rect):
                self.eliminate_airport(airport_id)
                return None
        return rect

    def eliminate_airport(self, airport_id):
        akey = airport_id
        if akey in self.display_objects:
            ap = self.display_objects[akey]
            self.scene.removeItem(ap)
            del self.display_objects[akey]

    def render_navaid(self, point, navaid_id):
        vkey = navaid_id
        vlkey = navaid_id + "_l"
        if vkey in self.display_objects:
            vtlabel = self.display_objects[vlkey]
            vticon = self.display_objects[vkey]
        else:
            font = QFont(VirtualVfr.AIRPORT_FONT_FAMILY, VirtualVfr.AIRPORT_FONT_SIZE-2, QFont.Bold)
            vtlabel = self.scene.addSimpleText(navaid_id, font)
            vtlabel.setPen(QPen(QColor(Qt.blue)))
            vtlabel.setBrush(QBrush(QColor(Qt.white)))
            vtlabel.setZValue(0)
            vticon = self.scene.addPixmap (QPixmap (VirtualVfr.VORTAC_ICON_PATH))
            self.display_objects[vlkey] = vtlabel
            self.display_objects[vkey] = vticon
        rect = vtlabel.boundingRect()
        xoff = self.scene.width()/2 + point[0] - rect.width()/2
        vtlabel.setX(xoff)
        yoff = self.scene.height()/2 + point[1]
        vtlabel.setY(yoff)

        rect = vticon.boundingRect()
        xoff = self.scene.width()/2 + point[0] - rect.width()/2
        vticon.setX(xoff)
        yoff = self.scene.height()/2 + point[1] - rect.height()
        vticon.setY(yoff)

    def eliminate_navaid(self, navaid_id):
        vkey = navaid_id
        vlkey = navaid_id + "_l"
        if vkey in self.display_objects:
            self.scene.removeItem (self.display_objects[vkey])
            self.scene.removeItem (self.display_objects[vlkey])
            del self.display_objects[vkey]
            del self.display_objects[vlkey]

    def setLatitude(self, lat):
        self.lat = lat
        self.missing_lat = False
        #print ("New latitude %f"%self.lat)
        self.pov.update_position (self.lat, self.lng)
        if not self.rendering_prohibited():
            self.pov.render(self)

    def setLongitude(self, lng):
        self.lng = lng
        self.missing_lng = False
        #print ("New longitude %f"%self.lng)
        self.pov.update_position (self.lat, self.lng)
        if not self.rendering_prohibited():
            self.pov.render(self)

    def setAltitude(self, alt):
        self.altitude = alt
        self.pov.update_altitude (alt)

    def setHeading(self, heading):
        curtime = time.time()
        if curtime - self.last_mag_update > 60 or self.magnetic_declination is None:
            # update every minute at the most
            if not (self.missing_lat or self.missing_lng):
                self.last_mag_update = curtime
                self.magnetic_declination = declination (self.lat, self.lng, self.altitude)
        md = self.magnetic_declination
        if md is None:
            md = 0
        self.pov.update_heading (heading + md)
        if not self.rendering_prohibited():
            self.pov.render(self)

    def getVfrBad(self):
        #print(self._VFRBad)
        return True in self._VFRBad.values()

    def setVfrBad(self, bad, item=None):
        self._VFRBad[item] = bad
        self.setBlank(bad)
        if item in self._AIBad and bad != self._AIBad[item]:
            self._AIBad[item] = bad
            if hasattr(self, 'sky_rect'):
                if self.getAIBad():
                    self.sky_rect.setBrush (self.gray_sky)
                    self.land_rect.setBrush (self.gray_land)
                    #self.bad_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    self.land_rect.setBrush (self.gbrown_brush)
                    #self.bad_text.hide()
                self.redraw()

    def setLngBad(self,bad):
        self.setVfrBad(bad,'LONG')

    def setLatBad(self,bad):
        self.setVfrBad(bad,'LAT')

    def setHeadBad(self,bad):
        self.setVfrBad(bad,'HEAD')

    def setAltBad(self,bad):
        self.setVfrBad(bad,'ALT')

    def getVfrOld(self):
        #print(f"VFR getVfrOld {self._VFROld}")
        return True in self._VFROld.values()

    def setOld(self, old, item=None):
        #print(f"VFR setOld {self._VFROld}")
        self._VFROld[item] = old
        self.setBlank(old)
        if item in self._AIOld and old != self._AIOld[item]:
            self._AIOld[item] = old
            if hasattr(self, 'sky_rect'):
                if self.getAIOld():
                    self.sky_rect.setBrush (self.gray_sky)
                    self.land_rect.setBrush (self.gray_land)
                    #self.old_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    self.land_rect.setBrush (self.gbrown_brush)
                    #self.old_text.hide()
                self.redraw()
    def setLngOld(self,old):
        #print(f"VFR setLngOld {old}")
        self.setOld(old,'LONG')

    def setLatOld(self,old):
        self.setOld(old,'LAT')

    def setHeadOld(self,old):
        self.setOld(old,'HEAD')

    def setAltOld(self,old):
        self.setOld(old,'ALT')

    def getVfrFail(self):
        #print(self._VFRFail)
        return True in self._VFRFail.values()

    def setVfrFail(self, fail, item=None):
        self._VFRFail[item] = fail
        self.setBlank(fail)
        if item in self._AIFail and fail != self._AIFail[item]:
            self._AIFail[item] = fail
            if hasattr(self, 'fail_scene'):
                if self.getAIFail():
                    self.resetTransform()
                    self.setScene (self.fail_scene)
                else:
                    self.setScene (self.scene)
                    # Initially set to grey
                    # we may have old data while recovering
                    if hasattr(self, 'sky_rect'):
                        if self.getAIFail():
                            self.sky_rect.setBrush (self.gray_sky)
                            self.land_rect.setBrush (self.gray_land)
                        else:
                            self.sky_rect.setBrush (self.gblue_brush)
                            self.land_rect.setBrush (self.gbrown_brush)
                self.redraw()

    def setLngFail(self,fail):
        self.setVfrFail(fail,'LONG')

    def setLatFail(self,fail):
        self.setVfrFail(fail,'LAT')

    def setHeadFail(self,fail):
        self.setVfrFail(fail,'HEAD')

    def setAltFail(self,fail):
        self.setVfrFail(fail,'ALT')

    def rendering_prohibited(self):
        return self.getVfrFail() or self.getVfrBad() or self.getVfrOld()

    def setBlank(self, b):
        if self.rendering_prohibited() and len(self.display_objects) > 0:
            for key in self.display_objects.keys():
                # The lights seem to be stored in a list 
                if isinstance(self.display_objects[key],list):
                    for delobj in self.display_objects[key]:
                        self.scene.removeItem(delobj)
                else:
                    self.scene.removeItem(self.display_objects[key])
            self.display_objects = dict()

VIEWPORT_ANGLE100 = 35.0 / 2.0 * RAD_DEG

class PointOfView:
    sorted_object_types = ["Airport", "Fix"]
    def __init__(self, dbpath, index_path, refresh_period):
        # Inputs
        self.altitude = 0
        self.gps_lat = 0
        self.gps_lng = 0
        self.true_heading = 0
        self.show_object_types = set()
        self.zoom = 100.0
        self.display_width = 0
        self.index_path = index_path
        self.dbpath = dbpath
        self.refresh_period = .1 if refresh_period is None else refresh_period
        self.cache_refresh_period = self.refresh_period * 100

        # Computed State
        self.view_screen = None
        self.object_cache = dict()
        self.elevation = 0
        self.last_time = None
        self.last_cache_time = None
        self.do_render = False

    def initialize(self, show_what, display_width, lng, lat, alt, head):
        self.display_width = display_width
        if isinstance(show_what,list) or isinstance(show_what,set):
            self.show_object_types.update(show_what)
        else:
            self.show_object_types.add(show_what)
        self.gps_lat = lat
        self.gps_lng = lng
        self.true_heading = head
        self.altitude = alt
        self.update_cache()
        self.elevation = self.approximate_elevation()
        self.update_screen()

    def dont_show(self, what):
        if isinstance(what,list) or isinstance(what,set):
            self.show_object_types.difference_update(what)
        else:
            self.show_object_types.remove(what)

    def update_position(self, lat, lng):
        self.gps_lat = lat
        self.gps_lng = lng
        self.update_cache()
        self.elevation = self.approximate_elevation()
        self.update_screen()

    def update_altitude(self, alt):
        self.altitude = alt

    def update_heading(self, true_heading):
        self.true_heading = true_heading
        self.update_screen()

    def update_screen(self):
        if self.last_time is not None and \
                (time.time() - self.last_time < self.refresh_period):
            return
        earth_radius = EARTH_RADIUS + self.elevation
        pov_radius = EARTH_RADIUS + self.altitude
        if pov_radius <= earth_radius:
            pov_radius = earth_radius + 10
        pov_polar = Spatial.Polar (self.gps_lng * RAD_DEG, self.gps_lat * RAD_DEG, pov_radius)
        self.pov_position = pov_polar.to3()
        # pov_position: pilot's position

        nvec = Spatial.Vector(0,0,1.0)
        center_vec = Spatial.Vector(ref=self.pov_position)
        center_vec.div(center_vec.norm())
        if abs(nvec.dot_product(center_vec)) >= .999:
            # Special case we're exactly over a pole
            # Just continue to use the old screen until the next update, when there's no way
            # you're still EXACTLY over a pole
            return
        else:
            yvec1 = nvec.cross_product (center_vec)
            yvec1.div(yvec1.norm())
            if not yvec_points_east (yvec1, self.pov_position, pov_polar):
                yvec1.mult(-1)
            xvec1 = yvec1.cross_product(center_vec)
            if xvec1.z < 0:
                xvec1.mult(-1)
        plane1 = Spatial.Plane(self.pov_position, normal=center_vec)
        # screen1 has the plane parallel to the earth's surface beneath the aircraft,
        #  with yvec pointing east and xvec pointing north
        screen1 = Spatial.Screen (plane1, self.pov_position, xvec=xvec1, yvec=yvec1)
        hrad = self.true_heading * RAD_DEG
        forward_point = screen1.point((math.cos(hrad), math.sin(hrad)))
        plane2 = Spatial.Plane(Spatial.Cartesian(), self.pov_position, forward_point)
        xvec2 = copy.copy(forward_point)
        xvec2.sub(self.pov_position)
        xvec2.div(xvec2.norm())
        yvec2 = copy.copy(self.pov_position)
        yvec2.mult(-1)
        yvec2.div (yvec2.norm())
        # screen2 is the plane slicing through the center of the earth, the aircraft center,
        #       and the aircraft nose.
        # xvec(2) is pointing aircraft forward, yvec(2) is pointing to earth center
        screen2 = Spatial.Screen (plane2, self.pov_position, xvec=xvec2, yvec=yvec2)
        # cos(view_declination) = earth_radius / pov_radius
        view_declination = math.acos(earth_radius / pov_radius)
        # view_declination: angle you have to look down to center on the horizon
        view_point = screen2.point ((math.cos(view_declination),math.sin(view_declination)))
        view_vector = copy.copy(view_point)
        view_vector.sub(self.pov_position)
        view_vector.div(view_vector.norm())
        # view_vector is pointing to the center of the horizon from the pilot's viewpoint

        viewray = Spatial.Ray (self.pov_position,dir=view_vector)
        # tan(VIEWPORT_ANGLE100) = (display_width/2) / view_distance100
        view_distance100 = (self.display_width/2) / math.tan(VIEWPORT_ANGLE100)
        viewscreen_distance = view_distance100 * (self.zoom / 100.0)
        screen_point = viewray.project(viewscreen_distance)
        viewplane = Spatial.Plane (p1=screen_point,normal=view_vector)
        xvec = view_vector.cross_product(xvec2)
        xvec.div(xvec.norm())
        yvec = view_vector.cross_product(xvec)
        self.view_screen = Spatial.Screen(viewplane, self.pov_position, xvec=xvec, yvec=yvec)
        self.last_time = time.time()
        self.do_render = True
        #print ("new view screen %s"%str(self.view_screen))

    def update_cache(self):
        if self.last_cache_time is not None and \
                (time.time() - self.last_cache_time < self.cache_refresh_period):
            return
        center_lat = int(self.gps_lat)
        center_lng = int(self.gps_lng)
        for lat_inc in range(-1,2,1):
            for lng_inc in range(-1,2,1):
                block = (center_lat + lat_inc, center_lng + lng_inc)
                if not block in self.object_cache:
                    self.object_cache[block] = CIFPObjects.find_objects(
                                    self.dbpath, self.index_path, block[0], block[1])
                    #print ("New cache block has %d objects at %f,%f"%(len(self.object_cache[block]), self.gps_lat, self.gps_lng))
        # Match runways
        self.last_cache_time = time.time()
        while True:
            rwsearch = None
            rwsearchblock = None
            rwsearchnum = -1
            rwdelete = -1
            rwdeleteblock = None
            for block,olist in self.object_cache.items():
                for i,o in enumerate(olist):
                    if isinstance(o, CIFPObjects.Runway) and (not o.matched()):
                        if rwsearch is None:
                            rwsearch = o
                            rwsearchblock = block
                            rwsearchnum = i
                            #print ("Search match for %s"%str(o))
                        else:
                            try:
                                # Try is hack to prevent exception
                                # Sometimes the runway is empty string
                                # pyavtools/CIFPObjects.py", line 258, in match
                                #  rwnum = int(label)
                                # ValueError: invalid literal for int() with base 10: ''                          

                                if rwsearch.match(o):
                                    rwdelete = i
                                    rwdeleteblock = block
                                    rwsearch = None
                                    break
                                else:
                                    #print ("Mis match for %s"%str(o))
                                    pass
                            except:
                              pass
                if rwdeleteblock is not None:
                    break
            if rwdeleteblock is not None:
                del self.object_cache[rwdeleteblock][rwdelete]
            else:
                if rwsearch is None:
                    break
                else:
                    log.debug ("Unable to find match for %s"%str(rwsearch))
                    del self.object_cache[rwsearchblock][rwsearchnum]
        self.garbage_collect_cache()


    def garbage_collect_cache(self):
        center_lat = int(self.gps_lat)
        center_lng = int(self.gps_lng)
        keeplist = list()
        for lat_inc in range(-1,2,1):
            for lng_inc in range(-1,2,1):
                block = (center_lat + lat_inc, center_lng + lng_inc)
                keeplist.append(block)
        purge_list = list()
        for cacheline in self.object_cache.keys():
            if not cacheline in keeplist:
                purge_list.append(cacheline)
        for p in purge_list:
            del self.object_cache[p]

    def approximate_elevation(self):
        """ Find the approximate elevation of the land beneath the aircraft by
            finding the elevation of the nearest runway
        """
        NOMIN = 99999999
        min_distance = NOMIN
        elevation = 0
        rel_lng = 0
        curpos = (self.gps_lng,self.gps_lat)
        for object_list in self.object_cache.values():
            for obj in object_list:
                if isinstance(obj, CIFPObjects.Runway):
                    course = [curpos, (obj.lng,obj.lat)]
                    distance, rel_lng = \
                            Distance(course, rel_lng=rel_lng)
                    if distance < min_distance:
                        min_distance = distance
                        elevation = obj.elevation
        return elevation

    def render(self, display_object):
        if not self.do_render:
            return
        sorted_objects = list()
        for oblist in self.object_cache.values():
            for ob in oblist:
                if ob.typestr() in self.show_object_types:
                    if ob.typestr() in self.sorted_object_types:
                        sorted_objects.append (ob)
                    else:
                        ob.render (self, display_object, self.display_width,
                                    (self.gps_lng, self.gps_lat))
        rel_lng = GetRelLng(self.gps_lat)
        sorted_objects = [(Distance( [(self.gps_lng, self.gps_lat), (so.lng,so.lat)],
                                    rel_lng)[0], so) for so in sorted_objects]
        sorted_objects.sort()
        space_occupied = list()
        for d,so in sorted_objects:
            rect = so.render (self, display_object, self.display_width,
                                    (self.gps_lng, self.gps_lat), space_occupied)
            if rect is not None:
                space_occupied.append(rect)

        self.do_render = False

    def point2D (self, lat, lng, debug=False):
        """ Find the projected point on the view screen given a latitude and longitude
            of the point.
        """
        point_radius = EARTH_RADIUS + self.elevation
        point_polar = Spatial.Polar (lng * RAD_DEG, lat * RAD_DEG, point_radius)
        point_position = point_polar.to3()
        r = Spatial.Ray(self.pov_position, pos2=point_position)
        try:
            p = self.view_screen.point2D (r)
        except:
            p = None
        if debug:
            log.debug ("point2D %s->%s ==> %s ==> %s"%(str(self.pov_position), str(point_position), str(r), str(p)))
        return p

def yvec_points_east (yvec, pov_position, pov_polar):
    yvec_pos = copy.copy(yvec)
    yvec_pos.mult(10000)
    yvec_pos.add(pov_position)
    yvec_polar = yvec_pos.to_polar()
    theta_diff = yvec_polar.theta - pov_polar.theta
    if theta_diff > math.pi * 2:
        theta_diff -= math.pi * 2
    if theta_diff < -math.pi * 2:
        theta_diff += math.pi * 2
    return theta_diff > 0


FOFY=1
FOFX=0

def get_line(points, fofwhat=FOFX):
    if fofwhat==FOFX:
        divi = 0
        numi = 1
    else:
        divi = 1
        numi = 0
    div = (points[1][divi] - points[0][divi])
    if div == 0:
        slope = math.inf
        intercept = 0
    else:
        slope = (points[1][numi] - points[0][numi]) / div
        # f(x) = slope * x + intercept
        # points[0][numi] = slope * points[0][divi] + intercept
        # points[0][numi] - intercept = slope * points[0][divi]
        #  - intercept = slope * points[0][divi] - points[0][numi]
        #  intercept = -slope * points[0][divi] + points[0][numi]
        intercept = points[0][numi] - slope*points[0][divi]
    return (slope,intercept)

def F(var, function):
    slope,intercept = function
    if slope == math.inf:
        return math.inf
    else:
        return slope * var + intercept

def get_polar_deltas(course):
    lng1,lat1 = course[0]
    lng2,lat2 = course[1]
    dlng = lng2 - lng1
    dlat = lat2 - lat1
    return (dlng,dlat)

def GetRelLng(lat1):
    return math.cos(lat1)

# Computes true heading from a given course
def Distance(course, rel_lng=0):
    dlng,dlat = get_polar_deltas(course)
    lat1 = course[0][1] * M_PI / 180.0

    # Determine how far is a longitude increment relative to latitude at this latitude
    if rel_lng == 0:
        relative_lng_length = GetRelLng(lat1)
    else:
        relative_lng_length = rel_lng
    dlng *= relative_lng_length

    distance = math.sqrt(dlng * dlng + dlat * dlat) * 60.0      # Multiply by 60 to convert from degrees to nautical miles.

    return distance, relative_lng_length


if __name__ == "__main__":
    # Unit testing for POV class
    pov = PointOfView()
    pov.initialize (0, 0, 1000, 0, [], 400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 180, [], 400)
    assert(pov.view_screen.x.dir.y < -0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 90, [], 400)
    assert(pov.view_screen.x.dir.z < -0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 270, [], 400)
    assert(pov.view_screen.x.dir.z > 0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > EARTH_RADIUS)

    pov.initialize (0, 180, 1000, 0, [], 400)
    assert(pov.view_screen.x.dir.y < -0.99)
    assert(pov.view_screen.y.dir.x > 0.99)
    assert(pov.view_screen.x.org.x < -EARTH_RADIUS)

    pov.initialize (0, 180, 1000, 180, [], 400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x > 0.99)
    assert(pov.view_screen.x.org.x < -EARTH_RADIUS)

    pov.initialize (45, 0,  1000,  0,  [],  400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.7)
    assert(pov.view_screen.y.dir.z < -0.7)

    pov.initialize (-45, 0,  1000,  0,  [],  400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.7)
    assert(pov.view_screen.y.dir.z > 0.7)

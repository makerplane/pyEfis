#  Copyright (c) 2018 Garrett Herschleb
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

from geomag import declination

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *
import efis
import logging

import fix

from instruments.ai import AI
from instruments.ai import util
from instruments.ai import Spatial
from instruments.ai import CIFPObjects

log = logging.getLogger(__name__)

class VirtualVfr(AI):
    CENTERLINE_WIDTH = 3
    MIN_FONT_SIZE=7
    RUNWAY_LABEL_FONT_FAMILY="Courier"
    AIRPORT_FONT_FAMILY="Sans"
    AIRPORT_FONT_SIZE=9
    PAPI_YOFFSET = 8
    PAPI_LIGHT_SPACING = 9
    VORTAC_ICON_PATH="vortac.png"
    def __init__(self, parent=None):
        super(VirtualVfr, self).__init__(parent)
        self.display_objects = dict()
        time.sleep(.4)      # Pause to let DB load
        lng = fix.db.get_item("LONG")
        lng.valueChanged[float].connect(self.setLongitude)
        lat = fix.db.get_item("LAT")
        lat.valueChanged[float].connect(self.setLatitude)
        head = fix.db.get_item("HEAD")
        head.valueChanged[float].connect(self.setHeading)
        alt = fix.db.get_item("ALT")
        alt.valueChanged[float].connect(self.setAltitude)
        self.last_mag_update = 0
        self.magnetic_declination = None
        self.missing_lat = True
        self.missing_lng = True
        self.lat = lat.value
        self.lng = lng.value
        self.altitude = alt.value
        # BUG: convert magnetic heading
        self.true_heading = head.value
        self.myparent = parent
        minfont = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, VirtualVfr.MIN_FONT_SIZE, QFont.Bold)
        t = QGraphicsSimpleTextItem ("9 9")
        t.setFont (minfont)
        self.min_font_width = t.boundingRect().width()

    def resizeEvent(self, event):
        super(VirtualVfr, self).resizeEvent(event)
        self.pov = PointOfView(self.myparent.get_config_item('dbpath'), 
                               self.myparent.get_config_item('indexpath'))
        self.pov.initialize(["Runway", "Airport"], self.scene.width(),
                    self.lng, self.lat, self.altitude, self.true_heading)
        self.pov.render(self)

    def get_largest_font_size(self, width):
        max_size = 25
        min_size = VirtualVfr.MIN_FONT_SIZE
        incr = (max_size - min_size) / 4
        ret = (max_size - min_size) / 2
        t = QGraphicsSimpleTextItem ("9 9")
        while True:
            font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, ret, QFont.Bold)
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
            font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, ret, QFont.Bold)
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
            poly = QPolygonF([QPoint(*p11), QPoint(*p12), QPoint(*p21), QPoint(*p22)])
            rw = self.display_objects[key]
            rw.setPolygon(poly)
        else:
            # print ("make new runway polygon %s"%key)
            poly = QPolygonF([QPoint(*p11), QPoint(*p12), QPoint(*p21), QPoint(*p22)])
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
        centerline_function = util.get_line(clpoints, util.FOFY)
        clkey = key + "_c"
        if dist1 > 3 * VirtualVfr.CENTERLINE_WIDTH and dist2 > 3*VirtualVfr.CENTERLINE_WIDTH and \
                abs(clpoints[0][1]-clpoints[1][1]) > 5*VirtualVfr.CENTERLINE_WIDTH:
            # Runway polygon large enough to add a centerline
            cline_function = util.get_line (clpoints, util.FOFY)
            if clpoints[0][1] > clpoints[1][1]:
                bottomi = 0
                topi = 1
            else:
                bottomi = 1
                topi = 0
            bottomy = clpoints[bottomi][1]-2*VirtualVfr.CENTERLINE_WIDTH
            clpoints[bottomi] = (util.F(bottomy, cline_function), bottomy)
            topy = clpoints[topi][1]+2*VirtualVfr.CENTERLINE_WIDTH
            clpoints[topi] = (util.F(topy, cline_function), topy)
            cline = QLineF(QPoint(*clpoints[0]), QPoint(*clpoints[1]))
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
                font = QFont(VirtualVfr.RUNWAY_LABEL_FONT_FAMILY, font_size, QFont.Bold)
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
                if pkey in self.display_objects:
                    for l in self.display_objects[pkey]:
                        self.scene.removeItem (l)
                    del self.display_objects[pkey]
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
        bottom_intercept = util.F(self.scene.height()/2, centerline_function)
        elkey = key + "_e"
        pkey = key + "_p"
        if abs(bottom_intercept) < self.scene.width():
            if clpoints[0][1] > clpoints[1][1]:
                touchdown_point = QPoint (*clpoints[0])
            else:
                touchdown_point = QPoint (*clpoints[1])
            extended_point = QPoint(bottom_intercept, self.scene.height()/2)
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
            approach_angle = math.atan(height_touchdown / touchdown_distance) * util.DEG_RAD
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
        self.pov.render(self)

    def setLongitude(self, lng):
        self.lng = lng
        self.missing_lng = False
        #print ("New longitude %f"%self.lng)
        self.pov.update_position (self.lat, self.lng)
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
        self.pov.render(self)

VIEWPORT_ANGLE100 = 35.0 / 2.0 * util.RAD_DEG

class PointOfView:
    UPDATE_PERIOD = .1
    sorted_object_types = ["Airport", "Fix"]
    def __init__(self, dbpath, index_path):
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

        # Computed State
        self.view_screen = None
        self.object_cache = dict()
        self.elevation = 0
        self.last_time = None
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
        if self.last_time is not None and (time.time() - self.last_time < self.UPDATE_PERIOD):
            return
        earth_radius = util.EARTH_RADIUS + self.elevation
        pov_radius = util.EARTH_RADIUS + self.altitude
        if pov_radius <= earth_radius:
            pov_radius = earth_radius + 10
        pov_polar = Spatial.Polar (self.gps_lng * util.RAD_DEG, self.gps_lat * util.RAD_DEG, pov_radius)
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
        hrad = self.true_heading * util.RAD_DEG
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
                            if rwsearch.match(o):
                                rwdelete = i
                                rwdeleteblock = block
                                rwsearch = None
                                break
                            else:
                                #print ("Mis match for %s"%str(o))
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
                    heading, distance, rel_lng = \
                            util.TrueHeadingAndDistance(course, rel_lng=rel_lng)
                    if distance < min_distance:
                        min_distance = distance
                        elevation = obj.elevation
        return elevation

    def render(self, display_object):
        if not self.do_render:
            return
        """     To test runway rendering with artificial data:
        r = CIFPObjects.Runway()
        r.airport_id = 'test'
        r.name = 'RW36'
        r.lng,r.lat = util.AddPosition((self.gps_lng,self.gps_lat), .9, 0)
        r.length = 5000
        r.bearing = 0
        r.elevation = 0
        r.opposing_rw = CIFPObjects.Runway()
        r.opposing_rw.airport_id = 'test'
        r.opposing_rw.name = 'RW18'
        r.opposing_rw.lng,r.opposing_rw.lat = util.AddPosition((r.lng,r.lat), .9, 0)
        r.opposing_rw.length = 5000
        r.opposing_rw.bearing = 0
        r.opposing_rw.elevation = 0
        r.render (self, display_object, self.display_width)
        """
        sorted_objects = list()
        for oblist in self.object_cache.values():
            for ob in oblist:
                if ob.typestr() in self.show_object_types:
                    if ob.typestr() in self.sorted_object_types:
                        sorted_objects.append (ob)
                    else:
                        ob.render (self, display_object, self.display_width,
                                    (self.gps_lng, self.gps_lat))
        sorted_objects = [(util.TrueHeadingAndDistance(
                                            [(self.gps_lng, self.gps_lat), (so.lng,so.lat)]) [1],
                           so) for so in sorted_objects]
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
        point_radius = util.EARTH_RADIUS + self.elevation
        point_polar = Spatial.Polar (lng * util.RAD_DEG, lat * util.RAD_DEG, point_radius)
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

if __name__ == "__main__":
    # Unit testing for POV class
    pov = PointOfView()
    pov.initialize (0, 0, 1000, 0, [], 400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > util.EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 180, [], 400)
    assert(pov.view_screen.x.dir.y < -0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > util.EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 90, [], 400)
    assert(pov.view_screen.x.dir.z < -0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > util.EARTH_RADIUS)
    pov.initialize (0, 0, 1000, 270, [], 400)
    assert(pov.view_screen.x.dir.z > 0.99)
    assert(pov.view_screen.y.dir.x < -0.99)
    assert(pov.view_screen.x.org.x > util.EARTH_RADIUS)

    pov.initialize (0, 180, 1000, 0, [], 400)
    assert(pov.view_screen.x.dir.y < -0.99)
    assert(pov.view_screen.y.dir.x > 0.99)
    assert(pov.view_screen.x.org.x < -util.EARTH_RADIUS)

    pov.initialize (0, 180, 1000, 180, [], 400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x > 0.99)
    assert(pov.view_screen.x.org.x < -util.EARTH_RADIUS)

    pov.initialize (45, 0,  1000,  0,  [],  400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.7)
    assert(pov.view_screen.y.dir.z < -0.7)

    pov.initialize (-45, 0,  1000,  0,  [],  400)
    assert(pov.view_screen.x.dir.y > 0.99)
    assert(pov.view_screen.y.dir.x < -0.7)
    assert(pov.view_screen.y.dir.z > 0.7)

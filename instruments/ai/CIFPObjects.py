#!/usr/bin/env python3
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

#from __future__ import print_function

import sys
import re
import logging
from functools import partial
import struct

import instruments.ai.util as util

logger = logging.getLogger(__name__)

NM_FEET= util.NAUT_MILES_PER_METER / util.FEET_METER 

def make_float(s, nleading_digits):
    float_string = s[:nleading_digits] + '.' + s[nleading_digits:]
    return float(float_string)

class IndexNode:
    packer = struct.Struct("<iiI")
    def __init__(self, lat_or_fd, lng=None, file_offset=None):
        if isinstance(lat_or_fd, str):
            self.latitude = lat_or_fd
            self.longitude = lng
            self.file_offset = file_offset
        else:
            self.latitude,self.longitude,self.file_offset = IndexNode.packer.unpack(
                    lat_or_fd.read (IndexNode.packer.size))

    def get_lat_number(self):
        return (1 if self.latitude[0] == 'N' else -1) * int(self.latitude[1:])

    def get_lng_number(self):
        return (1 if self.longitude[0] == 'E' else -1) * int(self.longitude[1:])

    def __str__(self):
        return "   " + self.latitude+self.longitude+str(self.file_offset) + "\n"

    def pack(self):
        return IndexNode.packer.pack (self.get_lat_number(), self.get_lng_number(), self.file_offset)

class Index:
    INDEX_LEN_LAT=3
    INDEX_LEN_LONG=4
    pack_int = struct.Struct("<i")
    pack_short = struct.Struct("<h")
    def __init__(self):
        self.latitudes = list()

    def get_lat_index(self, l):
        return (1 if l[0] == 'N' else -1) * int(l[1:Index.INDEX_LEN_LAT])

    def get_lng_index(self, l):
        return (1 if l[0] == 'E' else -1) * int(l[1:Index.INDEX_LEN_LONG])

    def add(self, node):
        # Insert into list to keep it sorted
        latindex = self.get_lat_index (node.latitude)
        lngindex = self.get_lng_index (node.longitude)
        lti = 0
        while lti < len(self.latitudes) and latindex > self.latitudes[lti][0]:
            lti += 1
        if lti == len(self.latitudes) or latindex > self.latitudes[lti][0]:
            # Append to the end
            self.latitudes.append (self.new_latitude (latindex, lngindex, node))
        elif latindex == self.latitudes[lti][0]:
            self.add_lng (self.latitudes[lti], lngindex, node)
        else:
            self.latitudes.insert (lti, self.new_latitude (latindex, lngindex, node))

    def new_latitude(self, latindex, lngindex, node):
        return [latindex, self.new_longitude (lngindex, node)]

    def new_longitude(self, lngindex, node):
        return [lngindex, node]

    def add_lng(self, latlist, lngindex, node):
        lgi = 1
        while lgi < len(latlist) and lngindex > latlist[lgi][0]:
            lgi += 1
        if lgi == len(latlist) or lngindex > latlist[lgi][0]:
            # Append to the end
            latlist.append (self.new_longitude (lngindex, node))
        elif lngindex == latlist[lgi][0]:
            latlist[lgi].append(node)
        else:
            latlist.insert (lgi, self.new_longitude (lngindex, node))

    def __str__(self):
        return str(self.latitudes)

    def pack(self, fd):
        for lat in self.latitudes:
            result = self.pack_latitude(lat)
            fd.write (Index.pack_int.pack (len(result)))
            fd.write (result)

    def pack_latitude(self, lat):
        result = Index.pack_short.pack(lat[0])
        for lng in lat[1:]:
            pack_lng = self.pack_longitude(lng)
            result = result + Index.pack_int.pack(len(pack_lng)) + pack_lng
        return result

    def pack_longitude(self, lng):
        result = Index.pack_short.pack(lng[0])
        for node in lng[1:]:
            result = result + node.pack()
        return result

class Airport:
    def __init__(self):
        self.id = ''
        self.name = ''
        self.lat = 0
        self.lng = 0

    def parseCIFP (self, line):
        if line[12] != 'A':
            raise RuntimeError ("CIFP line is not an airport: %s"%line)
        self.id = line[6:10]
        """ example:
SUSAP KABQK2AABQ     0     137YHN35022015W106362974E011005355         1800018000C    MNAR    ALBUQUERQUE INTL SUNPORT
 """
        self.lat = read_lat (line[32:41])
        self.lng = read_lng (line[41:51])
        self.name = line[93:123]
        self.name = self.name.strip()

    def __str__(self):
        return "Airport " + self.id + "(" + self.name + ") " + str(self.lat) + " / " + str(self.lng)

    def typestr(self):
        return "Airport"

def read_lat(s):
    latsign = s[0]
    deg = float(s[1:3])
    minutes = float(s[3:5])
    sec = s[5:9]
    return ((1 if latsign == 'N' else -1) *
            (deg + minutes / 60.0 + make_float(sec, 2) / 3600.0))

def read_lng(s):
    lngsign = s[0]
    deg = float(s[1:4])
    minutes = float(s[4:6])
    sec = s[6:10]
    return ((1 if lngsign == 'E' else -1) *
            (deg + minutes / 60.0 + make_float(sec, 2) / 3600.0))

class Runway:
    WIDTH_RATIO = 100.0 / 5000.0
    RENDER_HEIGHT_THRESHOLD = 1.0
    def __init__(self):
        self.airport_id = ''
        self.name = ''
        self.lat = 0
        self.lng = 0
        self.length = 0
        self.bearing = 0
        self.elevation = 0
        self.opposing_rw = None

    def parseCIFP (self, line):
        if line[12] != 'G':
            raise RuntimeError ("CIFP line is not a runway: %s"%line)
        self.airport_id = line[6:10]
        """ example:
SUSAP KABQK2GRW03    0100000340 N35012009W106375017         +1595705305000060150IIBZY1                                     064111711
"""
        self.lat = read_lat (line[32:41])
        self.lng = read_lng (line[41:51])
        self.name = line[13:18]
        self.name = self.name.strip()
        self.bearing = make_float(line[27:31], 3)
        self.length = int(line[22:27])
        self.elevation = int(line[66:71])

    def __str__(self):
        return "Runway " + self.name + " at airport " + self.airport_id + " " + \
                str(self.lat) + " / " + str(self.lng) + \
                " bearing %f, elevation %d, length %d feet"%(self.bearing, self.elevation, self.length)

    def typestr(self):
        return "Runway"

    def set_opposing_runway(self, rw):
        self.opposing_rw = rw

    def matched(self):
        return self.opposing_rw is not None

    def match(self, candidate):
        if self.airport_id != candidate.airport_id:
            return False        # Runways have to be at the same airport
        # match parallel runways
        if self.name[-1] == 'C' and candidate.name[-1] != 'C':
            return False
        if self.name[-1] == 'L' and candidate.name[-1] != 'R':
            return False
        if self.name[-1] == 'R' and candidate.name[-1] != 'L':
            return False

        # Runway numbers should match
        label = ''.join([d for d in self.name if d >= '0' and d <= '9'])
        candidate_label = ''.join([d for d in candidate.name if d >= '0' and d <= '9'])
        rwnum = int(label)
        candidate_rwnum = int(candidate_label)
        rwnum += 18
        if rwnum > 36:
            rwnum -= 36
        if rwnum != candidate_rwnum:
            return False
        else:
            self.opposing_rw = candidate
            #print ("Runways %s and %s matched at airport %s"%(self.name, candidate.name, self.airport_id))
            return True

    def render(self, pov, display_object, display_width, aircraft_pos):
        # see if we're in view
        centerpoint = pov.point2D (self.lat, self.lng)
        if centerpoint is None:
            #print ("%s out of screen: %f,%f"%(str(self), self.lat, self.lng))
            display_object.eliminate_runway (self.name, self.airport_id)
            return
        px,py = centerpoint

        dw2 = display_width / 2
        clip_minx = -dw2
        clip_maxx = dw2
        clip_miny = 0
        clip_maxy = dw2

        side1_out = False
        if px < clip_minx or px > clip_maxx or py < clip_miny or py > clip_maxy:
            #print ("%s out of clipping: %f,%f"%(str(self), px, py))
            side1_out = True
        otherpoint = pov.point2D (self.opposing_rw.lat, self.opposing_rw.lng)
        if otherpoint is None:
            #print ("%s side2 out of screen: %f,%f"%(str(self), self.opposing_rw.lat, self.opposing_rw.lng))
            display_object.eliminate_runway (self.name, self.airport_id)
            return
        px,py = otherpoint
        if px < clip_minx or px > clip_maxx or py < clip_miny or py > clip_maxy:
            if side1_out:
                #print ("%s all out of clipping: %f,%f"%(str(self), px, py))
                display_object.eliminate_runway (self.name, self.airport_id)
                return
        width_2 = self.length * Runway.WIDTH_RATIO / 2
        width_2_nm = width_2 * NM_FEET
        width_bearing = self.bearing + 90
        if width_bearing >= 360:
            width_bearing -= 360
        if width_bearing <= -360:
            width_bearing += 360

        centerpoint = (self.lng, self.lat)
        otherpoint = (self.opposing_rw.lng, self.opposing_rw.lat)
        p11_lng,p11_lat = util.AddPosition(centerpoint, width_2_nm, width_bearing)
        p11 = pov.point2D (p11_lat, p11_lng)
        p21_lng,p21_lat = util.AddPosition(otherpoint, width_2_nm, width_bearing)
        p21 = pov.point2D (p21_lat, p21_lng)

        width_bearing = self.bearing - 90
        if width_bearing >= 360:
            width_bearing -= 360
        if width_bearing <= -360:
            width_bearing += 360
        p12_lng,p12_lat = util.AddPosition(centerpoint, width_2_nm, width_bearing)
        p12 = pov.point2D (p12_lat, p12_lng)
        p22_lng,p22_lat = util.AddPosition(otherpoint, width_2_nm, width_bearing)
        p22 = pov.point2D (p22_lat, p22_lng)

        ys = [p11[1], p12[1], p21[1], p22[1]]
        if max(ys) - min(ys) < Runway.RENDER_HEIGHT_THRESHOLD:
            #print ("%s too far off on the horizon"%str(self))
            #print ("points %s,%s,%s,%s"%(str(p11), str(p12), str(p21), str(p22)))
            display_object.eliminate_runway (self.name, self.airport_id)
            return

        #print ("Display %s, points %s,%s,%s,%s"%(str(self), str(p11), str(p12), str(p21), str(p22)))
        # Compute approach angle for PAPI lights
        course = [aircraft_pos, (self.lng,self.lat)]
        h,dist1,_ = util.TrueHeadingAndDistance(course)
        course = [aircraft_pos, (self.opposing_rw.lng,self.opposing_rw.lat)]
        h,dist2,_ = util.TrueHeadingAndDistance(course)
        dist = min([dist1,dist2])
        dist *= util.FEET_NM
        display_object.render_runway (p12, p11, p21, p22, dist, self.elevation, self.length,
                self.bearing, self.name, self.airport_id, pov.zoom)


class Navaid:
    def __init__(self):
        self.id = ''
        self.name = ''
        self.lat = 0
        self.lng = 0
        self.deviation = 0

    def parseCIFP (self, line):
        if line[4:10] != 'D     ':
            raise RuntimeError ("CIFP line is not a Navaid: %s"%line)
        self.id = line[13:16]
        """ example:
SUSAD        ABI   K4011370VTHW N32285279W099514843    N32285279W099514843E0100018092     NARABILENE                       214151810
SUSAD        GSB   K7011650 TLW                    GSB N35200671W077581674W0080000691     NARSEYMOUR JOHNSON
"""
        try:
            self.lat = read_lat (line[32:41])
            self.lng = read_lng (line[41:51])
        except:
            self.lat = read_lat (line[55:64])
            self.lng = read_lng (line[64:74])
        self.name = line[93:123]
        self.name = self.name.strip()
        devsign = line[74]
        self.deviation = (1 if devsign == 'E' else -1) * make_float(line[75:80], 3)

    def __str__(self):
        return "NAVAID " + self.id + " (" + self.name + ") " + \
                str(self.lat) + " / " + str(self.lng) + \
                " deviation %f"%(self.deviation, )

    def typestr(self):
        return "NAVAID"

class RouteNode:
    def __init__(self):
        self.id = ''
        self.navid = ''
        self.ib_course = 0
        self.ob_course = 0
        self.dist = 0

    def parseCIFP (self, line):
        if line[4:10] != 'ER    ':
            raise RuntimeError ("CIFP line is not a Route: %s"%line)
        self.id = line[13:17].strip()
        """ Example:
SUSAER       V10         0710WILSSK6EA0E    OL                        110205571100 05000                                   546211806
"""
        self.ib_course = make_float(line[78:82], 3)
        self.ob_course = make_float(line[70:74], 3)
        self.navid = line[29:34].strip()
        self.dist = int(line[74:78])

    def __str__(self):
        return "ROUTE " + self.id + " (" + self.navid + ") " + \
                " Inbound mag course %f, outbound %f, route from distance %d"%(self.ib_course, self.ob_course, self.dist)

    def typestr(self):
        return "RouteNode"


location_re = re.compile(r'(?P<latitude>[NS]\d\d\d\d\d\d\d\d)(?P<longitude>[EW]\d\d\d\d\d\d\d\d\d)')

def lines_in_file(fn):
    buffer=2**16
    with open(fn) as f:
        ret = sum(x.count('\n') for x in iter(partial(f.read,buffer), ''))
        f.close()
    return ret

def find_routes(fn, navid):
    ret = list()
    buffer_size=2**16
    route_re = re.compile(r'ER       [ABJLMQTVY]\d')
    """ Example:
SUSAER       V10         0710WILSSK6EA0E    OL                        110205571100 05000                                   546211806
"""
    with open(fn, 'rb') as f:
        while True:
            buf = f.read(buffer_size)
            if len(buf) == 0:
                break
            buf = buf.decode('utf-8')
            if 'ER       ' in buf:
                ind = 0
                found = False
                while True:
                    ind = buf.find('ER       ',  ind)
                    if ind < 0:
                        break
                    if (ind > 5 and (buf[ind-5] == '\n' or buf[ind-5] == '\r')) and \
                            (route_re.match(buf[ind:ind+40]) is not None):
                        found = True
                        break
                    else:
                        ind += 8
                if found:
                    f.seek (ind - buffer_size - 4, 1)
                    while True:
                        line = f.readline().decode('utf-8')
                        if line[4:6] != 'ER':
                            break
                        if line[29:34].strip() == navid:
                            route = RouteNode ()
                            try:
                                route.parseCIFP(line)
                                if route.dist > 0:
                                    ret.append(route)
                            except:
                                pass
        f.close()
    return ret

def find_nodes(ifd, find_lat, find_long):
    find_lat_index = int(round(find_lat))
    find_lng_index = int(round(find_long))
    assert(IndexNode.packer.size == 12)
    ret = list()
    done = False
    while not done:
        latlenbytes = ifd.read(4)
        if len(latlenbytes) != 4:
            break
        latlen = Index.pack_int.unpack(latlenbytes)[0]
        latindex = Index.pack_short.unpack(ifd.read(2))[0]
        latlen -= 2
        if latindex == find_lat_index:
            while not done:
                lnglen = Index.pack_int.unpack(ifd.read(4))[0]
                lngindex = Index.pack_short.unpack(ifd.read(2))[0]
                latlen -= (lnglen+2)
                lnglen -= 2
                if lngindex == find_lng_index:
                    while lnglen >= IndexNode.packer.size:
                        ret.append (IndexNode(ifd))
                        lnglen -= IndexNode.packer.size
                    done = True
                elif lngindex > find_lng_index:
                    done = True
                else:
                    ifd.seek(lnglen,1)
                    if latlen <= 0:
                        done = True
        else:
            ifd.seek(latlen,1)
    return ret

def parse_line(dbfd):
    line = dbfd.read(256)
    if len(line) < 30:
        log.debug ("Error parsing CIFP database. Got '%s'"%line)
        return None
    line = line.decode('utf-8')
    if '\n' in line:
        line = line[:line.index('\n')]
    if len(line) < 30:
        log.debug ("Error parsing CIFP database line. Got '%s'"%line)
        return None
    ret = None
    if line[12] == 'A':
        try: 
            ret = Airport()
            ret.parseCIFP (line)
        except Exception as e:
            print ("Error (%s) parsing airport:\n%s"%(str(e), line))
    elif line[12] == 'G' and line[13:17] != " PAD":
        try:
            ret = Runway()
            ret.parseCIFP (line)
        except:
            print ("Error parsing runway:\n%s"%line)
    elif line[4:10] == 'D     ':
        try:
            ret = Navaid()
            ret.parseCIFP (line)
        except:
            print ("Error parsing Navaid:\n%s"%line)
    return ret

def index_db (dbfilename, indexfilename):
    nlines = lines_in_file (dbfilename)
    line_number = 1
    file_offset = 0
    node_count = 0
    index = Index()
    spinner = 0
    with open(dbfilename, 'r') as cifp:
        while True:
            l = cifp.readline()
            if len(l) == 0:
                break
            location = location_re.search(l)
            if location:
                try:
                    node = IndexNode (location.group('latitude'),location.group('longitude'), file_offset)
                    index.add (node)
                except Exception as e:
                    print ("Error %s on line %d"%(str(e), line_number))
                    sys.exit(-1)
                node_count += 1
            file_offset += len(l) + 1
            if line_number % 1000 == 0:
                percent_complete = float(line_number) * 100 / nlines
                print ("\r%5.2f%% %s (%d nodes)  "%(percent_complete, r'|/-\|-'[spinner], node_count), end='')
                spinner += 1
                if spinner >= 6:
                    spinner = 0
            line_number += 1

        cifp.close()
    with open(indexfilename, 'wb') as fd:
        index.pack (fd)
        fd.close()

def find_objects(dbfilename, indexfilename, find_lat, find_long):
    objects = list()
    try:
        with open(indexfilename, 'rb') as ifd:
            with open(dbfilename, 'rb') as dbfd:
                nodes = find_nodes (ifd, find_lat, find_long)
                for node in nodes:
                    dbfd.seek(node.file_offset)
                    o = parse_line (dbfd)
                    if o != None:
                        objects.append (o)
                dbfd.close()
            ifd.close()
    except Exception as e:
        logger.error ("Unable to load chart objects: %s", str(e))
    return objects

def print_objects(objects, dbfilename):
    for o in objects:
        print (str(o))
        if isinstance(o, Navaid):
            for route in find_routes(dbfilename, o.id):
                print (str(route))

if __name__ == "__main__":
    index_db(sys.argv[1], 'index.bin')
    #objects = find_objects (sys.argv[1], 'index.bin', 38.0, -77.0)
    #print_objects (objects, sys.argv[1])

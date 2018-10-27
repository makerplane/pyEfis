# Copyright (C) 2012-2018  Garrett Herschleb
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import math, logging, functools

try:
    import instruments.ai.Spatial as Spatial
except:
    import Spatial

logger=logging.getLogger(__name__)

M_PI = math.pi
NAUT_MILES_PER_METER = .0005399568
# m / s^2 * nm / m
# nm / s^2 * 3600 s / hour
# nm / s * h
# knots / s
G_IN_KNOTS_PER_SEC = 9.98 * NAUT_MILES_PER_METER * 3600.0
RAD_DEG = M_PI / 180.0
DEG_RAD = 180.0 / M_PI

METERS_FOOT = 0.3048
FEET_METER = 1.0 / METERS_FOOT
FEET_NM = FEET_METER / NAUT_MILES_PER_METER
MM_INCHES = 25.4
EARTH_RADIUS_M=6356752.0
EARTH_RADIUS=EARTH_RADIUS_M * FEET_METER

def read_cont_expr (first_args, lines):
    ret = None
    line = ' '.join(first_args)
    while not ret:
        try:
            ret = eval(line)
            return ret
        except:
            if len (lines) == 0:
                raise RuntimeError ('Incomplete expression: ' + line)
            line += lines[0]
            del lines[0]

def millis(t):
    # TODO: Handle positive/negative wrap
    return int((t * 1000)%2147483648)

def rotate2d(angle,  x,  y):
    xprime = x * math.cos(angle) - y * math.sin(angle)
    yprime = y * math.cos(angle) + x * math.sin(angle)
    return xprime, yprime

def get_polar_deltas(course):
    lng1,lat1 = course[0]
    lng2,lat2 = course[1]
    dlng = lng2 - lng1
    dlat = lat2 - lat1
    return (dlng,dlat)

MAX_COURSE_HOP_LENGTH_DEG = 1.0/3.0
MAX_COURSE_HOP_LENGTH_RAD = MAX_COURSE_HOP_LENGTH_DEG * M_PI/180.0

def GetRelLng(lat1):
    return math.cos(lat1)

def GetAdjustedPolarDeltas(course, rel_lng=0):
    dlng,dlat = get_polar_deltas(course)
    if rel_lng == 0:
        rel_lng = GetRelLng(course[0][1] * RAD_DEG)
    return (dlng*rel_lng, dlat)

# Computes true heading from a given course
def TrueHeadingAndDistance(course, periodic_logging=None, frequency=10, rel_lng=0):
    dlng,dlat = get_polar_deltas(course)
    if dlng > MAX_COURSE_HOP_LENGTH_DEG or dlat > MAX_COURSE_HOP_LENGTH_DEG:
        expanded_course = ExpandCourseList(course, MAX_COURSE_HOP_LENGTH_DEG)
        dlng,dlat = get_polar_deltas(expanded_course)
    lat1 = course[0][1] * M_PI / 180.0

    # Determine how far is a longitude increment relative to latitude at this latitude
    if rel_lng == 0:
        relative_lng_length = GetRelLng(lat1)
    else:
        relative_lng_length = rel_lng
    dlng *= relative_lng_length

    heading = atan_globe(dlng, dlat) * 180 / M_PI
    distance = math.sqrt(dlng * dlng + dlat * dlat) * 60.0      # Multiply by 60 to convert from degrees to nautical miles.
    if periodic_logging:
        log_occasional_info (periodic_logging, "course (%g,%g)->(%g,%g) d=(%g,%g), rel_lng=%g, distance=%g"%(
            course[0][0], course[0][1],
            course[1][0], course[1][1],
            dlng, dlat, relative_lng_length, distance
            ), frequency)

    return heading, distance, relative_lng_length

def TrueHeading (course, periodic_logging=None, frequency=10):
    ret,a,b = TrueHeadingAndDistance(course, periodic_logging, frequency)
    return ret

def deg_min_to_radians(deg,minutes):
    return ((deg + minutes/60.0) * M_PI / 180.0)

def get_intermediate_points(begin, end, degrees_per_hop):
    radians_per_hop = degrees_per_hop * M_PI / 180.0
    begin = (begin[0] * M_PI / 180.0, begin[1] * M_PI / 180.0)       # Convert to radians for spatial math
    end = (end[0] * M_PI / 180.0, end[1] * M_PI / 180.0)
    last_waypoint = Spatial.Polar(begin[0], begin[1], 1.0)
    org = last_waypoint.to3(robot_coordinates=False)
    route_vec = Spatial.Polar(end[0], end[1], 1.0).to3(robot_coordinates=False)
    r = Spatial.Ray(org, pos2=route_vec)
    route_vec.sub(org)
    total_time = route_vec.norm()
    cartinc1 = Spatial.Polar(0.0,0.0,1.0).to3(robot_coordinates=False)

    ret = list()
    tm = 0.0
    while True:
        # For determining the time increment:
        radius = last_waypoint.rad
        # time_increment / radius = tan (radians_per_hop)
        time_increment = math.tan(radians_per_hop) * radius
        tm += time_increment
        if tm >= total_time:
            break
        waypoint = r.project(tm).to_polar(robot_coordinates=False)
        ret.append ((waypoint.theta * 180.0 / M_PI, waypoint.phi * 180.0 / M_PI))
        last_waypoint = waypoint
    return ret

def ExpandCourseList(course, degrees_per_hop):
    last_point = 0
    ret = [course[0]]
    for this_point in range(1,len(course)):
        ret += get_intermediate_points(course[last_point], course[this_point], degrees_per_hop)
        ret.append (course[this_point])
    return ret

log_sources = dict()

def log_occasional_info(source, string, frequency=10):
    global log_sources
    if not (source in log_sources):
        log_sources[source] = 0
    if log_sources[source] == 0:
        logger.info (source + ": " + string)
    log_sources[source] += 1
    if log_sources[source] >= frequency:
        log_sources[source] = 0

def get_rate(current, desired, time_divisor, limits):
    error = desired - current
    rate = error / time_divisor
    if isinstance(limits,tuple) or isinstance(limits,list):
        mn = limits[0]
        mx = limits[1]
    else:
        mn = -limits
        mx = limits

    if rate > mx:
        rate = mx
    if rate < mn:
        rate = mn
    return rate

def rate_curve(x, curve_pieces):
    last_piece = 0
    sign = 1 if x >= 0 else -1
    x = abs(x)
    for piece in range(1,len(curve_pieces)):
        if x >= curve_pieces[last_piece][0] and x < curve_pieces[piece][0]:
            x0 = curve_pieces[last_piece][0]
            x1 = curve_pieces[piece][0]
            if x >= x0 and x < x1:
                y0 = curve_pieces[last_piece][1]
                y1 = curve_pieces[piece][1]
                xpiece = (x - x0) / (x1 - x0)
                y = xpiece * (y1 - y0) + y0
                logger.log(3, "rate_curve: x=%g [%g,%g]==> %g ; y = %g [%g,%g]",
                        x, x0, x1, xpiece, y, y0, y1)
                return sign * y
        last_piece = piece
    else:
        return sign * curve_pieces[-1][1]


def AddPosition(position, distance, direction, rel_lng = 0.0, periodic_logging=None, frequency=10):
    if not rel_lng:
        rel_lng = GetRelLng(position[1] * RAD_DEG)
    direction *= M_PI / 180.0
    dlat = distance * math.cos(direction) / 60.0
    dlng = distance * math.sin(direction) / (rel_lng * 60.0)
    ret = (position[0] + dlng, position[1] + dlat)
    if periodic_logging:
        logstr = "AddPosition (%g,%g)+(%g/%g) =(%g,%g) / (%g,%g), rel_lng=%g"%(
            position[0], position[1], distance, direction, dlng, dlat, ret[0], ret[1], rel_lng)
        log_occasional_info (periodic_logging, logstr, frequency)

    return ret


def atan_globe(lng, lat):
    return math.atan2(lng,lat)

def FIRFilter (current, history, taps):
    while len(history) >= len(taps):
        del history[-1]
    history.insert(0, current)
    mult = map(lambda h,a: h*a if h != None else 0.0, history, taps)
    ret = functools.reduce(lambda x,y: x+y, mult)
    return ret

LowPassFIR = [0.45, 0.2, 0.1, 0.05, 0.05, .05, .05, .05]
def LowPassFilter (current, history):
    return FIRFilter (current, history, LowPassFIR)

def RMSDiff (l1, l2):
    length1 = len(l1)
    length2 = len(l2)
    length = length1 if length1 > length2 else length2
    sum = 0
    for i in range(length):
        diff = l1[i] - l2[i]
        sum += (diff * diff)
    ret = math.sqrt(sum) / length
    return ret

def CourseDeviation(pos, course, rel_lng = 0):
    if rel_lng == 0:
        rel_lng = GetRelLng(course[0][1] * RAD_DEG)
    dlng, dlat = GetAdjustedPolarDeltas(course, rel_lng)
    heading = atan_globe(dlng, dlat) * 180 / M_PI
    cvec = Spatial.Vector(dlng,dlat,0)
    up = Spatial.Vector(0,0,1)
    pnormal = cvec.cross_product(up)
    destpoint = Spatial.Point3(course[1][0] * rel_lng, course[1][1], 0)
    course_plane = Spatial.Plane(destpoint, normal=pnormal)
    curpoint = Spatial.Point3 (pos[0] * rel_lng, pos[1], 0)
    r = Spatial.Ray(curpoint,dir=pnormal)
    intersect = course_plane.intersect(r)

    deviation_vect = Spatial.Point3(ref=intersect)
    deviation_vect.sub(curpoint)
    remaining_distance_vect = Spatial.Point3(ref=destpoint)
    remaining_distance_vect.sub (intersect)
    side = deviation_vect.norm()
    forward = remaining_distance_vect.norm()
    side *= 60.0        # 60 nm per degree
    forward *= 60.0
    dlng, dlat = GetAdjustedPolarDeltas ([pos, course[1]], rel_lng)
    heading_to_dest = atan_globe(dlng, dlat) * 180 / M_PI
    hdiff = heading_to_dest - heading
    if hdiff > 180:
        hdiff -= 360
    elif hdiff < -180:
        hdiff += 360
    if hdiff > 0:
        side *= -1

    return (side, forward, heading, heading_to_dest)

def CourseHeading(pos, course, turn_radius, periodic_logging=None, frequency=10):
    side, forward, course_heading, heading_to_dest = CourseDeviation(pos, course)
    if abs(side) > turn_radius:
        diff = heading_to_dest - course_heading
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        if diff > 0:
            intercept_heading = course_heading + 90
        else:
            intercept_heading = course_heading - 90
    else:
        d1 = turn_radius - abs(side)
        # cos(a1) = d1 / turn_radius
        a1 = math.acos (d1 / turn_radius) * DEG_RAD
        if side > 0:
            intercept_heading = course_heading - a1
        else:
            intercept_heading = course_heading + a1
        # Example 1: course_heading = 0, side = .1, turn_radius = .5
        #   d1 = .4
        #   a1 = acos (.4 / .5) = 37 degrees
        #   ih = -37
        # Example 2: course_heading = 0, side = 0, turn_radius = .5
        #   d1 = .5
        #   a1 = acos (.5 / .5) = 0 degrees
        #   ih = 0
        # Example 3: course_heading = 0, side = -.1, turn_radius = .5
        #   d1 = .4
        #   a1 = acos (.4 / .5) = 37 degrees
        #   ih = 37
    if periodic_logging != None:
        log_occasional_info(periodic_logging,
                "cur_pos = (%g,%g), to=(%g,%g), course_h=%g, h_dest=%g, side = %g, forward=%g, intercept=%g"%(
                    pos[0], pos[1],
                    course[1][0], course[1][1],
                    course_heading, heading_to_dest, side, forward, intercept_heading), frequency)
    return intercept_heading



def VORDME(pos, course_or_pos):
    a,b = course_or_pos
    if isinstance(a,tuple):
        course_heading,_,rel_lng = TrueHeadingAndDistance(course_or_pos)
        rel_course = (course_or_pos[0], pos)
    else:
        course_heading = 0
        rel_lng=0
        rel_course = (course_or_pos, pos)
    direct_heading,dist,rel_lng = TrueHeadingAndDistance(rel_course, rel_lng=rel_lng)
    bearing = direct_heading - course_heading
    if bearing > 180:
        bearing -= 360
    elif bearing < -180:
        bearing += 360
    return bearing,dist,course_heading,rel_lng

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

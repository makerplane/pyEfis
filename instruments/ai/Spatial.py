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


import copy
import math
import logging

logger=logging.getLogger(__name__)

M_PI_2=math.pi/2.0

def rotate2d(angle,  x,  y):
    xprime = x * math.cos(angle) - y * math.sin(angle)
    yprime = y * math.cos(angle) + x * math.sin(angle)
    return xprime, yprime

class Point3:
    def __init__(self, x=0, y=0, z=0, ref=None):
        if ref:
            self.x = ref.x
            self.y = ref.y
            self.z = ref.z
        else:
            self.x = x
            self.y = y
            self.z = z
    
    def __str__(self):
        return "%g,%g,%g"%(round(self.x,4), round(self.y,4), round(self.z,4))

    def norm(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def to_polar(self,  limit_phi = False, robot_coordinates=False):
        rad = self.norm()
        if (0 == rad):
            theta = phi = 0
        else:
            if robot_coordinates:
                phi = M_PI_2 - math.asin (self.z / rad)
                theta = math.atan2 (self.y, self.x) - M_PI_2
                if math.fabs(phi) < 1e-6:
                    theta = 0
                if math.fabs(theta) > M_PI_2 and (not limit_phi):
                    phi *= -1
                    if (theta > 0):
                        theta -= math.pi
                    else:
                        theta += math.pi
            else:
                phi = math.asin (self.z / rad)
                theta = math.atan2 (self.y, self.x)

        return Polar(theta,phi,rad)

    def from_polar(self, p, robot_coordinates=False):
        if robot_coordinates:
            phi = M_PI_2 - p.phi
            theta = p.theta + M_PI_2
        else:
            phi = p.phi
            theta = p.theta
        self.x = p.rad * math.cos (theta) * math.cos (phi)
        self.y = p.rad * math.sin (theta) * math.cos (phi)
        self.z = p.rad * math.sin (phi)

    def add(self,o):
        self.x += o.x
        self.y += o.y
        self.z += o.z

    def sub(self,o):
        self.x -= o.x
        self.y -= o.y
        self.z -= o.z

    def cross_product(self,o):
        x = self.y * o.z - self.z * o.y
        y = self.z * o.x - self.x * o.z
        z = self.x * o.y - self.y * o.x
        return Point3(x,y,z)
    
    def dot_product(self,o):
        return (self.x * o.x + self.y * o.y + self.z * o.z)
        
    def angle(self,  o):
        return math.acos(self.dot_product(o) / (self.norm() * o.norm()))

    def mult(self,time_or_vect):
        if isinstance(time_or_vect,Point3):
            self.x = self.x * time_or_vect.x
            self.y = self.y * time_or_vect.y
            self.z = self.z * time_or_vect.z
        else:
            self.x = self.x * time_or_vect
            self.y = self.y * time_or_vect
            self.z = self.z * time_or_vect
        
    def div(self,time):
        self.x = self.x / time
        self.y = self.y / time
        self.z = self.z / time
        
    def assign(self,  ref):
        self.x = ref.x
        self.y = ref.y
        self.z = ref.z
        
    def distance(self,  o):
        x = self.x - o.x
        y = self.y - o.y
        z = self.z - o.z
        return (math.sqrt (x*x + y*y + z*z))
    
    def rotate_zaxis(self, angle):
        self.x, self.y = rotate2d(angle, self.x,  self.y)
        
    def rotate_yaxis(self,  angle):
        self.x, self.z = rotate2d(angle,  self.x,  self.z)
    
    def rotate_xaxis(self,  angle):
        self.z, self.y = rotate2d(angle,  self.z,  self.y)
        
    def rotate_given_axis(self,  forward,  axis,  xaxis_or_angle,  rot0_xaxis=None):
        # Get the 2D representation of the point on the current axes, with an arbitrary orthogonal axis
        if not rot0_xaxis:
            rot0_xaxis = get_non_rotated_axis(axis)
        screen = get_non_rotated_screen (self,  axis,  rot0_xaxis)
        if isinstance(xaxis_or_angle,  float):
            angle = xaxis_or_angle
        else:
            angle = get_rotation (screen,  xaxis_or_angle)
        px, py=screen.point2D(self)
#        checkpoint = screen.point((px, py))
#        checkpoint.sub(self)
#        assert(math.fabs(checkpoint.x) < .00001)
#        assert(math.fabs(checkpoint.y) < .00001)
#        assert(math.fabs(checkpoint.z) < .00001)
        
        if not forward:
            angle *= -1
        px, py=rotate2d(angle,  px,  py)
        
#        checkray = Ray(org, axis)
#        assert(math.fabs(plane.timeto(checkray)) < .0001)
#        checkray = Ray(self,  axis)
#        assert(math.fabs(plane.timeto(checkray)) < .0001)
        
        self.assign(screen.point((px, py)))

    def round(self, decimal_places):
        self.x = round(self.x, decimal_places)
        self.x = 0 if self.x == -0 else self.x
        self.y = round(self.y, decimal_places)
        self.y = 0 if self.y == -0 else self.y
        self.z = round(self.z, decimal_places)
        self.z = 0 if self.z == -0 else self.z

class Cartesian(Point3):
    def __init__(self,x=0, y=0, z=0,  ref=None):
        Point3.__init__(self,  x, y, z,  ref)

class Vector(Point3):
    def __init__(self,x=0, y=0, z=0,  ref=None):
        Point3.__init__(self, x, y, z,  ref)

class Polar:
    def __init__(self,t=0,p=0,r=0,ref=None):
        if ref:
            self.theta = ref.theta
            self.phi = ref.phi
            self.rad = ref.rad
        else:
            self.theta = t
            self.phi = p
            self.rad = r

    def from3 (self, p3,  limit_phi=False, robot_coordinates=False):
        self.rad = p3.norm()
        if (0 == self.rad):
            self.theta = self.phi = 0
        else:
            if robot_coordinates:
                self.phi = M_PI_2 - math.asin (p3.z / rad)
                self.theta = math.atan2 (p3.y, p3.x) - M_PI_2
                if math.fabs(self.phi) < 1e-6:
                    self.theta = 0
                if math.fabs(self.theta) > M_PI_2 and (not limit_phi):
                    self.phi *= -1
                    if (self.theta > 0):
                        self.theta -= math.pi
                    else:
                        self.theta += math.pi
            else:
                self.phi = math.asin (p3.z / rad)
                self.theta = math.atan2 (p3.y, p3.x)

    def to3 (self, robot_coordinates=False):
        if robot_coordinates:
            phi = M_PI_2 - self.phi
            theta = self.theta + M_PI_2
        else:
            phi = self.phi
            theta = self.theta
        x = self.rad * math.cos (theta) * math.cos (phi)
        y = self.rad * math.sin (theta) * math.cos (phi)
        z = self.rad * math.sin (phi)
        return Point3(x,y,z)

    def to_vector(self):
        return Vector(ref=self.to3())

    def to_cartesian(self):
        return Cartesian(ref=self.to3())

class Ray:
    def __init__(self,org,dir=None,pos2=None):
        if pos2:
            self.org = Cartesian(ref=org)
            self.dir = Vector(ref=pos2)
            self.dir.sub(org)
            self.dir.div (self.dir.norm())
        elif dir:
            self.org = Point3(ref=org)
            self.dir = Point3(ref=dir)
        else:
            raise RuntimeError ('Not enough information to initialize Ray')

    def project(self,time):
        ret = Cartesian(ref=self.dir)
        ret.mult(time)
        ret.add(self.org)
        return ret

    def __str__(self):
        return 'ray org %s, dir %s'%(str(self.org), str(self.dir))

class Plane:
    def __init__(self, p1=None,p2=None,p3=None,normal=None):
        if normal and p1:
            self.normal = Vector(ref=normal)
            self.normal.div (self.normal.norm())
            self.c = self.normal.dot_product(p1)
        elif p1 and p2 and p3:
            v1 = Vector(ref=p2)
            v2 = Vector(ref=p3)
            v1.sub(p1)
            v2.sub(p1)

            self.normal = v1.cross_product(v2)
            self.normal.div (self.normal.norm())
            self.c = self.normal.dot_product(p1)

    def timeto(self,r):
        return (self.c - (self.normal.dot_product(r.org))) / (r.dir.dot_product(self.normal))

    def intersect(self,r, allow_negative_time=True):
        ret = Cartesian(ref=r.dir)
        t = self.timeto(r)
        if t < 0 and (not allow_negative_time):
            raise RuntimeError ("No Intersection")
        ret.mult(t)
        ret.add(r.org)
        return ret

    def distance(self,c):
        r = Ray(c,dir=self.normal)
        return abs(self.timeto(r))

    def project(self,c):
        r = Ray(c,dir=self.normal)
        return self.intersect(r)

    def __str__(self):
        return 'plane normal %s, c=%g'%(str(self.normal), self.c)

class Screen:
    def __init__(self, plane, org, xvec,  yvec=None):
        self.plane = plane
        self.x = Ray(org,dir=xvec)
        if not yvec:
            yvec = plane.normal.cross_product(xvec)
        self.y = Ray(org,dir=yvec)

    def point(self,p):
        if isinstance(p,tuple):
            x,y = p
        else:
            x = p.coordinate.x
            y = p.coordinate.y

        pos = self.x.project(x)
        yvec = Vector(ref=self.y.dir)
        yvec.mult(y)
        pos.add(yvec)
        return pos

    def point2D(self,r,allow_negative_time=False):
        if isinstance(r,Ray):
            intr = self.plane.intersect(r, allow_negative_time)
            svct = Vector(ref=intr)
        elif isinstance(r,Point3):
            svct = copy.deepcopy(r)
        else:
            raise RuntimeError ('invalid argument to Screen.point2D')
        svct.sub(self.x.org)
        x = (svct.dot_product(self.x.dir))
        y = (svct.dot_product(self.y.dir))
        return (x,y)

    def __str__(self):
        return 'screen %s, x %s, y%s'%(self.plane, self.x, self.y)

def get_non_rotated_screen(origin,  zvec,  rot0_xaxis, y_axis=None):
    plane=Plane(origin,  normal=zvec)
    screen=Screen(plane, origin,  rot0_xaxis, y_axis)
    return (screen)
        

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


import argparse

from instruments.ai.CIFPObjects import index_db

if __name__ == "__main__":
    opt = argparse.ArgumentParser(description='Create an index search file for an FAA CIFP Objects database')
    opt.add_argument('CIFP_File', help='The path of the CIFP file')
    opt.add_argument('-o', '--output', default='CIFP/index.bin', help='The path of the output file')
    args = opt.parse_args()

    index_db(args.CIFP_File, args.output)

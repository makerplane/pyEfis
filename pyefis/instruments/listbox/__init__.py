# This implementes a selectable list
# Could be used to select a frequency from a list or destination etc


from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import logging
import pyavtools.fix as fix
logger=logging.getLogger(__name__)

import yaml
import os
import operator
from pyefis.instruments import misc
import geopy.distance

class ListBox(QGraphicsView):
    def __init__(self, parent=None, lists=[], replace=None, encoder=None, button=None):
        super(ListBox, self).__init__(parent)
        self.parent = parent
        self.tlists = dict()
        for l in lists:
            self.tlists[l["name"]] = yaml.load(open(os.path.join(self.parent.parent.config_path,l['file'])), Loader=yaml.SafeLoader)

        list_str = yaml.dump(self.tlists)
        if replace:
            for rep in replace:
                list_str = list_str.replace(rep,str(replace[rep]))
        self.tlists = yaml.load(list_str, Loader=yaml.SafeLoader)

        self.active_list = list(self.tlists.keys())[0]
        self.header = misc.StaticText(text=self.active_list, color=QColor(Qt.white), parent=self)
        self.selected_row = 0
        self.columns = len(self.tlists[self.active_list]['display']['columns'])
        self.rows = len(self.tlists[self.active_list]['list'])
        self.sort = False
        self.table = QTableWidget(self)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)

        self.table.doubleClicked.connect(self.clicked)
        if encoder:
            self._encoder = fix.db.get_item(encoder)
            self._encoder.valueChanged[int].connect(self.encoderChanged)
        if button:
            self._button = fix.db.get_item(button)
            self._button.valueChanged[bool].connect(self.buttonChanged)

        self.nearest = False

        self.lng_item = fix.db.get_item("LONG")
        self.lat_item = fix.db.get_item("LAT")

        self.lng = self.lng_item.value
        self.lat = self.lat_item.value

        self.lng_old = self.lng_item.old
        self.lng_bad = self.lng_item.bad
        self.lng_fail = self.lng_item.fail

        self.lat_old = self.lat_item.old
        self.lat_bad = self.lat_item.bad
        self.lat_fail = self.lat_item.fail

        self.lng_item.valueChanged[float].connect(self.setLongitude)
        self.lng_item.badChanged[bool].connect(self.setLngBad)
        self.lng_item.oldChanged[bool].connect(self.setLngOld)
        self.lng_item.failChanged[bool].connect(self.setLngFail)

        self.lat_item.valueChanged[float].connect(self.setLatitude)
        self.lat_item.badChanged[bool].connect(self.setLatBad)
        self.lat_item.oldChanged[bool].connect(self.setLatOld)
        self.lat_item.failChanged[bool].connect(self.setLatFail)

    def badLocation(self):
        return True in ( self.lat_bad, self.lng_bad, self.lat_old, self.lng_old, self.lat_fail, self.lng_fail )

    def setLongitude(self, lng):
        self.lng = lng

    def setLatitude(self, lat):
        self.lat = lat

    def setLngBad(self,bad):
        self.lng_bad = bad
        self.loadList()

    def setLatBad(self,bad):
        self.lat_bad = bad
        self.loadList()

    def setLngFail(self,fail):
        self.lng_fail = fail
        self.loadList()

    def setLatFail(self,fail):
        self.lat_fail = fail
        self.loadList()

    def setLngOld(self,old):
        self.lng_old = old
        self.loadList()

    def setLatOld(self,old):
        self.lat_old = old
        self.loadList()

    def buttonChanged(self,data):
        if self._button.old or self._button.bad or self._button.fail:
            return
        if self._button.value:
            self.clicked(self.table.currentItem())

    def encoderChanged(self,data):
        # If old/bad/fail do nothing
        if self._encoder.old or self._encoder.bad or self._encoder.fail:
            return
        val = self.table.currentRow() + self._encoder.value
        # encoder could have sent enough steps to loop one or more times
        if val < 0:
            while val < 0:
                val = self.table.rowCount() + val
        elif val > self.table.rowCount() -1:
            while val > self.table.rowCount() -1:
                val = val - self.table.rowCount()
        self.table.selectRow(val) 



    def resizeEvent(self,event):

        style_sheet = f"""
        QTableView {{
            background-color: black;
            border: 1px solid white;
            gridline-color: white;
            color: white;
            font-size: {qRound(self.height() * 7/100)}px;
        }}
        QTableView::item:selected {{
            background-color: #87CEFA;
            color: black;
        }}
        QHeaderView::section {{
            background-color: black;
            color: white;
            border: 1px solid white;
            gridline-color: white;
            padding: 2px;
            font-size: {qRound(self.height() * 7/100)}px;
        }}
        QHeaderView::section:horizontal {{
            border-top: 1px solid white;
        }}
        QHeaderView::section:vertical {{
            border-right: 1px solid white;
        }}
        QTableView::indicator {{
            width: 20px;
            height: 20px;
        }}
        QTableView::indicator:checked {{
            background-color: #87CEFA;
        }}
        QTableView::indicator:unchecked {{
            background-color: black;
        }}
        """
        self.table.setStyleSheet(style_sheet)

        self.table.setMinimumWidth(self.width())
        self.table.setMinimumHeight(int(self.height() * 90/100))
        self.table.move(0,int(self.height() * 10/100))
        self.setStyleSheet("background: transparent")
        self.header.move(0,0)
        self.header.resize(self.width(),int(self.height() * 10/100))
        self.header.show()
        self.loadList()
        self.table.selectRow(0)

    def loadList(self):
        self.table.setRowCount(0)
        self.header.hide()
        self.header.text = self.active_list
        self.header.show()

        self.column_names = [ item['name'] for item in self.tlists[self.active_list]['display']['columns'] ]
        self.sort_options = [ item['name'] for item in self.tlists[self.active_list]['display']['columns'] if item.get('sort', False) ]
        loc = 0
        if self.tlists[self.active_list]['display'].get('location',False) and not self.badLocation():
            loc = 1
        self.table.setColumnCount(self.columns)
        self.table.setRowCount( self.rows + len( self.sort_options ) + len(self.tlists) - 1 + loc) 
        #self.table.setMinimumWidth(500)
        self.table.setHorizontalHeaderLabels( self.column_names )
        #self.table.horizontalHeader().stretchLastSection()
        self.table.horizontalHeader().setStretchLastSection(True) 
        #self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setMaximumSectionSize(int(self.width() * 35/100)) 
        index = 0
        self.actions = []
        if len(self.tlists) > 1:
            self.table.setItem(index,0, QTableWidgetItem("Load List"))
            self.actions.append({'select_list': True})
            index = 1
        if loc:
            self.table.setItem(index,0, QTableWidgetItem("Sort by:"))
            self.table.setItem(index,1, QTableWidgetItem("Nearest"))
            self.actions.append({'select_nearest': True})
            index += 1
        for c,o in enumerate(self.sort_options):
            self.table.setItem(index,0, QTableWidgetItem("Sort by:"))
            self.table.setItem(index,1, QTableWidgetItem(o))
            self.actions.append({'sort': True, 'option': c})
            index += 1
        # Not using the table to sort because we want 
        # some rows to always be at the top
        if self.nearest:
            the_list = sorted(self.tlists[self.active_list]['list'], key=lambda x: geopy.distance.geodesic((self.lat,self.lng), (x['lat'], x['long'])).km if x.get('lat', False) and x.get('long',False) else 9999999999)

        elif self.sort:
            # TODO nearest or text sort?
            the_list = sorted(self.tlists[self.active_list]['list'], key=operator.itemgetter(self.sort))
        else:
            the_list = self.tlists[self.active_list]['list']
        for o in the_list:
            for c,n in enumerate(self.column_names):
                self.table.setItem(index,c, QTableWidgetItem(o[n]))
            index += 1
            self.actions.append({'select': True, 'option': o})

        #self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def loadListSelector(self):
        self.table.setRowCount(0);
        self.column_names = ["Select a list"]
        self.table.setColumnCount(1)
        self.table.setRowCount(len(self.tlists) + 1)
        self.table.setHorizontalHeaderLabels( self.column_names )
        self.table.horizontalHeader().setMaximumSectionSize(0)
        self.actions = []
        self.table.setItem(0,0,QTableWidgetItem("Return"))
        # Preserve sort for return option
        self.actions.append({"load_list": True, "option": self.active_list, "sort": self.sort})
        for c,l in enumerate(self.tlists):
            self.table.setItem(c + 1, 0, QTableWidgetItem(l))
            self.actions.append({"load_list": True, "option": l})
        #self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def clicked(self, item):
        self.nearest = False
        if self.actions[item.row()].get('select_list', False):
            self.loadListSelector()
            self.table.selectRow(0)
        elif self.actions[item.row()].get('select_nearest', False):
            self.nearest = True
            self.loadList()
            self.table.selectRow(0)
        elif self.actions[item.row()].get('load_list', False):
            self.active_list = self.actions[item.row()]['option']
            self.rows = len(self.tlists[self.active_list]['list'])
            self.sort = self.actions[item.row()].get('sort',False)
            self.loadList()
            self.table.selectRow(0)
        elif self.actions[item.row()].get('sort', False):
            self.sort = self.sort_options[self.actions[item.row()]['option']]
            self.loadList()
            self.table.selectRow(0)
        elif self.actions[item.row()].get('select', False):
            for fixid, val in self.actions[item.row()]['option']['set'].items():
                f = fix.db.get_item(fixid)
                f.value = val
                f.output_value()


#Config:
#    options:
#      encoder: FIXID_ENCODER_INPUT <- Moves selection up or down
#      button: FIXID_BUTTON_INPOUT <- when pressed selects highlighted item
#      lists:  One or more lists
#        - name: Favorites #NAme displayed at top of list or when selecting a list
#          file: lists/radio/favorites.yaml Filename with the list
#
# The list files allow one to defined their own 'database' and can be as simple or complex 
# as the user desired
#
#display:
#  # The column names must be single word
#  # The exact name defined here is used for the key names 
#  # in the list below
#  show_headers: true/false <- show a header with column names or not
#  default_sort: <- Column name to sort by when loading a list, optional
#  columns:
#    - name: Name <- Display name for the column, maybe we show this at the top of the list
#      size: 15 <- how many characters for thhis column
#      sort: true <- Offer user an option to sort by this column or not
#    - name: Identifier
#      size: 4
#      sort: true
#    - name: Frequency
#      size: 11
#      sort: false #False is the default
#list:
#  - Name: Chapman Memorial  <- The values of the names in the columns list
#    Identifier: K6CM        <- are used here
#    Frequency: 122.900 Mhz
#    set:  <- One or more FIXDB items to set to a value when this record is selected
#      COMACTFREQSET{radio_id}: 122.900
# 
#    One could set a waypoint name, LONG, LAT, ALT etc, whatever you want to do

# Display should look something like this:
#
#  +---------------------------------+
#  |             Favorites           |
#  +-------------+------+------------+
#  | Name        | ICAO | Frequency  | 
#  +-------------+------+------------+
#  | Chapman Mem | K6CM | 122.900 Mhz|
#  | Knox County | K4I3 | 123.900 Mhz|



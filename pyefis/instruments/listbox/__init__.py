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

class ListBox(QGraphicsView):
    def __init__(self, parent=None, lists=[]):
        super(ListBox, self).__init__(parent)
        self.parent = parent
        self.tlists = dict()
        for l in lists:
            self.tlists[l["name"]] = yaml.load(open(os.path.join(self.parent.parent.config_path,l['file'])), Loader=yaml.SafeLoader)

        self.active_list = list(self.tlists.keys())[0]
        self.columns = len(self.tlists[self.active_list]['display']['columns'])
        self.rows = len(self.tlists[self.active_list]['list'])
        self.sort = False
        #print(self.tlists)
        #print(self.active_list)
        #print(self.columns)
        #print(self.rows)
        #print(self.width())
        #self.loadList()
        #self.insertItem(0, "Red")
        #self.insertItem(1, "Orange")
        #self.insertItem(2, "Blue")
        #self.itemDoubleClicked.connect(self.onClicked)
        self.table = QTableWidget(self)
        stylesheet = """
        background-color: #000000;
        color: #FFFFFF;
        border-color: #FFFFFF;
        gridline-color: #FFFFFF;
        """
        #self.table.horizontalHeader().setStyleSheet(stylesheet)

#        font-family: Titillium;
#        font-size: 18px;

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)

        self.table.doubleClicked.connect(self.clicked)

    def resizeEvent(self,event):

        print(self.height())
        print(qRound(self.height() * 14/100))
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

        #self.font = QFont()
        #self.font.setPixelSize(qRound(self.height() * 7/100)) # TODO, make this configurable and some of the stuff below
        #self.table.setFont(self.font)
        #self.table.horizontalHeader().setFont(self.font)
        # TODO Render the name of the list above the list
        # Set background color, white text on black backgrund?
        #self.setMinimumSize(QSize(500,500))
        self.table.setMinimumWidth(self.width())
        self.table.setMinimumHeight(int(self.height() * 90/100))
        self.table.move(0,int(self.height() * 10/100))
        self.loadList()

    def loadList(self):
        print(f"Loading: {self.active_list}")

        self.table.setRowCount(0);

        self.column_names = [ item['name'] for item in self.tlists[self.active_list]['display']['columns'] ]
        self.sort_options = [ item['name'] for item in self.tlists[self.active_list]['display']['columns'] if item.get('sort', False) ]

        self.table.setColumnCount(self.columns)
        self.table.setRowCount( self.rows + len( self.sort_options ) + len(self.tlists) - 1 ) 
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
            self.table.setItem(index,0, QTableWidgetItem("Select List:"))
            self.actions.append({'select_list': True})
            index = 1
        for c,o in enumerate(self.sort_options):
            self.table.setItem(index,0, QTableWidgetItem("Sort by:"))
            self.table.setItem(index,1, QTableWidgetItem(o))
            self.actions.append({'sort': True, 'option': c})
            index += 1
        if self.sort:
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


#    def resizeEvent(self,event):
#        pass

    def clicked(self, item):
        if self.actions[item.row()].get('select_list', False):
            print("User wants to load different list")
            self.loadListSelector()
        elif self.actions[item.row()].get('load_list', False):
            print(f"User wants to load the list {self.actions[item.row()]['option']}")
            self.active_list = self.actions[item.row()]['option']
            self.sort = self.actions[item.row()].get('sort',False)
            self.loadList()
        elif self.actions[item.row()].get('sort', False):
            print(f"User wants to sort by {self.sort_options[self.actions[item.row()]['option']]}")
            self.sort = self.sort_options[self.actions[item.row()]['option']]
            self.loadList()
        elif self.actions[item.row()].get('select', False):
            print(f"User selected the row {self.actions[item.row()]}") 

    def show_lists(self):
        pass

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



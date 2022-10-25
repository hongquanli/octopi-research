# qt libraries
from qtpy.QtCore import Qt, Signal # type: ignore
from qtpy.QtWidgets import QTableWidget, QHeaderView, QSizePolicy, QTableWidgetItem

from control._def import *

from typing import Optional, Union, List, Tuple

class WellSelectionWidget(QTableWidget):
 
    signal_wellSelected = Signal(int,int,float)
    signal_wellSelectedPos = Signal(float,float)
 
    def __init__(self, format: int):
        self.was_initialized=False
        self.set_wellplate_type(format)
        self.was_initialized=True
 
    def set_wellplate_type(self,wellplate_type:Union[str,int]):
        if type(wellplate_type)==str:
            wellplate_type_int:int=int(wellplate_type.split(" ")[0])  # type: ignore
        else:
            wellplate_type_int:int=wellplate_type # type: ignore
 
        wellplate_type_format=WELLPLATE_FORMATS[wellplate_type_int]
        self.rows = wellplate_type_format.rows
        self.columns = wellplate_type_format.columns
        self.spacing_mm = wellplate_type_format.well_spacing_mm
 
        if self.was_initialized:
            old_layout=WELLPLATE_FORMATS[self.format]
            self.set_selectable_widgets(layout=old_layout,is_selectable=True,exhaustive=True)
 
            self.format:int=wellplate_type_int
 
            self.setRowCount(self.rows)
            self.setColumnCount(self.columns)
 
            self.setData()
        else:
            self.format=wellplate_type_int
 
            QTableWidget.__init__(self, self.rows, self.columns)
 
            self.setData()
 
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        if not self.was_initialized:
            self.setEditTriggers(QTableWidget.NoEditTriggers)
            self.cellDoubleClicked.connect(self.onDoubleClick)
 
        # size
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(int(5*self.spacing_mm))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.horizontalHeader().setMinimumSectionSize(int(5*self.spacing_mm))
 
        self.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Minimum)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # type: ignore
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # type: ignore
        self.resizeColumnsToContents()
        self.setFixedSize(
            self.horizontalHeader().length() + self.verticalHeader().width(),
            self.verticalHeader().length() + self.horizontalHeader().height()
        )
 
    def set_selectable_widgets(self,layout:WellplateFormatPhysical,is_selectable:bool,exhaustive:bool=False):
        # item.flags is a bitvector, so changing the IsSelectable flag is bit manipulating magic
 
        if not is_selectable:
            assert not exhaustive, "cannot exhaustively disable only outer ring"
 
        for i in range(layout.rows):
            for j in (range(layout.columns) if exhaustive else [0,layout.columns-1]):
                item = QTableWidgetItem()
                item.setFlags((item.flags() | Qt.ItemIsSelectable) if is_selectable else (item.flags() & ~Qt.ItemIsSelectable)) # type: ignore
                self.setItem(i,j,item)
 
        if not exhaustive:
            for j in range(layout.columns):
                for i in [0,layout.rows-1]:
                    item = QTableWidgetItem()
                    item.setFlags((item.flags() | Qt.ItemIsSelectable) if is_selectable else (item.flags() & ~Qt.ItemIsSelectable)) # type: ignore
                    self.setItem(i,j,item)
 
    def setData(self):
        '''
        # cells
        for i in range(16):
            for j in range(24):
                newitem = QTableWidgetItem( chr(ord('A')+i) + str(j) )
                self.setItem(i, j, newitem)
        '''
        # row header
        row_headers = []
        for i in range(self.rows):
            row_headers.append(chr(ord('A')+i))
        self.setVerticalHeaderLabels(row_headers)
 
        # make the outer cells not selectable if using 96 and 384 well plates
        wellplate_format=WELLPLATE_FORMATS[self.format]
 
        if wellplate_format.number_of_skip==1:
            self.set_selectable_widgets(layout=wellplate_format,is_selectable=False)
        elif wellplate_format.number_of_skip>1:
            assert False, "more than one layer of disabled outer wells is currently unimplemented"
 
    def onDoubleClick(self,row:int,col:int):
        wellplate_format=WELLPLATE_FORMATS[self.format]
 
        if (row >= 0 + wellplate_format.number_of_skip and row <= self.rows-1-wellplate_format.number_of_skip ) and ( col >= 0 + wellplate_format.number_of_skip and col <= self.columns-1-wellplate_format.number_of_skip ):
            wellplateformat_384=WELLPLATE_FORMATS[384]
            x_mm = MACHINE_CONFIG.X_MM_384_WELLPLATE_UPPERLEFT + wellplateformat_384.well_size_mm/2 - (wellplateformat_384.A1_x_mm+wellplateformat_384.well_spacing_mm*wellplateformat_384.number_of_skip) + col*wellplate_format.well_spacing_mm + wellplate_format.A1_x_mm + MACHINE_CONFIG.WELLPLATE_OFFSET_X_mm
            y_mm = MACHINE_CONFIG.Y_MM_384_WELLPLATE_UPPERLEFT + wellplateformat_384.well_size_mm/2 - (wellplateformat_384.A1_y_mm+wellplateformat_384.well_spacing_mm*wellplateformat_384.number_of_skip) + row*wellplate_format.well_spacing_mm + wellplate_format.A1_y_mm + MACHINE_CONFIG.WELLPLATE_OFFSET_Y_mm
            self.signal_wellSelectedPos.emit(x_mm,y_mm)
 
    def get_selected_cells(self) -> List[Tuple[int,int]]:
        list_of_selected_cells = []
        for index in self.selectedIndexes():
             list_of_selected_cells.append((index.row(),index.column()))
        return list_of_selected_cells
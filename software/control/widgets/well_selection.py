# qt libraries
from qtpy.QtCore import Qt, Signal # type: ignore
from qtpy.QtWidgets import QTableWidget, QHeaderView, QSizePolicy, QTableWidgetItem

from control._def import *

from typing import Optional, Union, List, Tuple

from control.typechecker import TypecheckFunction
import numpy as np

class WellSelectionWidget(QTableWidget):
 
    signal_wellSelected:Signal = Signal(int,int,float)
    signal_wellSelectedPos:Signal = Signal(float,float)

    currently_selected_well_indices:List[Tuple[int,int]]=[]

    @TypecheckFunction
    def __init__(self, format: int):
        self.was_initialized=False
        self.set_wellplate_type(format)
        self.was_initialized=True

        self.itemSelectionChanged.connect(self.itemselectionchanged)
        MUTABLE_MACHINE_CONFIG.wellplate_format_change.connect(self.set_wellplate_type)

    def itemselectionchanged(self):
        self.currently_selected_well_indices = []
        for index in self.selectedIndexes():
            self.currently_selected_well_indices.append((index.row(),index.column()))

    @TypecheckFunction
    def widget_well_indices_to_physical_positions(self)->Tuple[List[str],List[Tuple[float,float]]]:
        # clear the previous selection
        self.coordinates_mm = []
        self.name = []
        
        # get selected wells from the widget
        if len(self.currently_selected_well_indices)>0:
            selected_wells = np.array(self.currently_selected_well_indices)
            # populate the coordinates
            rows = np.unique(selected_wells[:,0])
            _increasing = True

            for row in rows:
                items = selected_wells[selected_wells[:,0]==row]
                columns = items[:,1]
                columns = np.sort(columns)

                if _increasing==False:
                    columns = np.flip(columns)

                for column in columns:
                    x_mm,y_mm=self.well_index_to_physical_position(row,column)

                    self.coordinates_mm.append((x_mm,y_mm))
                    self.name.append(chr(ord('A')+row)+str(column+1))

                _increasing = not _increasing

        return self.name,self.coordinates_mm
 
    @TypecheckFunction
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
 
    @TypecheckFunction
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
 
    @TypecheckFunction
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

    @TypecheckFunction
    def well_index_to_physical_position(self,row:Union[int,np.int64],col:Union[int,np.int64])->Tuple[float,float]:
        wellplate_format=WELLPLATE_FORMATS[self.format]
        wellplate_format_384=WELLPLATE_FORMATS[384]

        # offset for coordinate origin, required because origin was calibrated based on 384 wellplate, i guess. 
        # term in parenthesis is required because A1_x/y_mm actually referes to upper left corner of B2, not A1 (also assumes that number_of_skip==1)
        assert wellplate_format_384.number_of_skip==1
        origin_x_offset=MACHINE_CONFIG.X_MM_384_WELLPLATE_UPPERLEFT-(wellplate_format_384.A1_x_mm + wellplate_format_384.well_spacing_mm * wellplate_format_384.number_of_skip)
        origin_y_offset=MACHINE_CONFIG.Y_MM_384_WELLPLATE_UPPERLEFT-(wellplate_format_384.A1_y_mm + wellplate_format_384.well_spacing_mm * wellplate_format_384.number_of_skip)

        # physical position of the well on the wellplate that the cursor should move to
        well_on_plate_offset_x=col * wellplate_format.well_spacing_mm + wellplate_format.A1_x_mm
        well_on_plate_offset_y=row * wellplate_format.well_spacing_mm + wellplate_format.A1_y_mm

        # offset from top left of well to position within well where cursor/camera should go
        # should be centered, so offset is same in x and y
        well_cursor_offset_x=wellplate_format_384.well_size_mm/2
        well_cursor_offset_y=well_cursor_offset_x

        x_mm = origin_x_offset + MACHINE_CONFIG.WELLPLATE_OFFSET_X_mm \
            + well_on_plate_offset_x + well_cursor_offset_x
        y_mm = origin_y_offset + MACHINE_CONFIG.WELLPLATE_OFFSET_Y_mm \
            + well_on_plate_offset_y + well_cursor_offset_y

        return x_mm,y_mm
 
    @TypecheckFunction
    def onDoubleClick(self,row:int,col:int):
        wellplate_format=WELLPLATE_FORMATS[self.format]
 
        row_lower_bound=0 + wellplate_format.number_of_skip
        row_upper_bound=self.rows-1-wellplate_format.number_of_skip
        column_lower_bound=0 + wellplate_format.number_of_skip
        column_upper_bound=self.columns-1-wellplate_format.number_of_skip

        if (row >= row_lower_bound and row <= row_upper_bound ) and ( col >= column_lower_bound and col <= column_upper_bound ):
            x_mm,y_mm=self.well_index_to_physical_position(row,col)
            self.signal_wellSelectedPos.emit(x_mm,y_mm)
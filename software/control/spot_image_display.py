from PyQt5.QtWidgets import * 
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtCore
import pyqtgraph.dockarea as dock
import pyqtgraph as pg
import os
import time
from datetime import datetime
import numpy as np
import pandas as pd
import cv2
import glob
import torch
import functools
import operator
import threading
from sklearn.neighbors import KNeighborsClassifier
import umap
from sklearn.decomposition import PCA

from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from mpl_interactions import ioff, panhandler, zoom_factory

import matplotlib as mpl

# from superqt import QLabeledDoubleRangeSlider, QLabeledRangeSlider, QDoubleRangeSlider # not working

##########################################################
################  Default configurations  ################
##########################################################
NUM_ROWS = 1000
MAX_NUM_ROWS_DISPLAYED_PER_PAGE = 7
num_cols = 9
SCALE_FACTOR = 4

K_SIMILAR_DEFAULT = 250

model_spec = {'model':'resnet18','n_channels':4,'n_filters':64,'n_classes':1,'kernel_size':3,'stride':1,'padding':1}
batch_size_inference = 2048
KNN_METRIC = 'cosine'

DEV_MODE = True

GENERATE_UMAP_FOR_FULL_DATASET = True
SHOW_IMAGE_IN_SCATTER_PLOT_ON_SELECTION = False
USE_UMAP = True # vs us PCA

PLOTS_FONT_SIZE = 20
SCATTER_SIZE = 5
SCATTER_SIZE_OVERLAY = 20

# on mac
# NUM_ROWS = 2
# num_cols = 4

##########################################################
#### start of loading machine specific configurations ####
##########################################################
config_files = glob.glob('.' + '/' + 'configurations*.txt')
if config_files:
    if len(config_files) > 1:
        print('multiple configuration files found, the program will exit')
        exit()
    exec(open(config_files[0]).read())
##########################################################
##### end of loading machine specific configurations #####
##########################################################

# set font size
mpl.rcParams['font.size'] = PLOTS_FONT_SIZE

if USE_UMAP:
    dimentionality_reduction = 'UMAP'
else:
    dimentionality_reduction = 'PCA'

COLOR_DICT = {0:QColor(150,200,250),1:QColor(250,200,200),9:QColor(250,250,200)} # 0: nonparasites, 1: parasites, 9: not sure
COLOR_DICT_PLOT = {-1:'#C8C8C8',0:'#96C8FA',1:'#FAC8C8',9:'#FAFAC8'}
ANNOTATIONS_DICT = {'Label as parasite':1,'Label as non-parasite':0,'Label as unsure':9,'Remove Annotation':-1}
ANNOTATIONS_REVERSE_DICT = {-1:'not labeled',0:'non-parasite',1:'parasite',9:'unsure'}
PLOTS = ['Labels','Annotation Progress','Prediction score','Similarity',dimentionality_reduction]

# modified from https://stackoverflow.com/questions/45896291/how-to-show-image-and-text-at-same-cell-in-qtablewidget-in-pyqt
def generate_overlay(image):
    images_fluorescence = image[:,2::-1,:,:]
    images_dpc = image[:,3,:,:]
    images_dpc = np.expand_dims(images_dpc, axis=1)
    images_dpc = np.repeat(images_dpc, 3, axis=1) # make it rgb
    images_overlay = 0.64*images_fluorescence + 0.36*images_dpc
    images = images_overlay.transpose(0,2,3,1)
    # frame = np.hstack([img_dpc,img_fluorescence,img_overlay]).astype('uint8')
    # print(images.shape)
    return images

def count_consecutive_rows_above_threshold(df, column_name, threshold):
    # Check if the column name exists in the DataFrame
    if column_name not in df.columns:
        raise ValueError(f"Column '{column_name}' not found in the DataFrame.")
    
    # Find the first row number at which consecutive_count did not increment
    above_threshold = (df[column_name] > threshold)
    consecutive_count = above_threshold.cumsum()
    

    first_non_incrementing_row = consecutive_count.loc[consecutive_count.diff() == 0].head(1)
    
    if first_non_incrementing_row.empty:
        return len(df)  # Return the last row number if no decrement was found
    else:
        return max(1,first_non_incrementing_row.iloc[0])

class CustomWidget(QWidget):
    def __init__(self, text, img, parent=None):
        QWidget.__init__(self, parent)

        self._text = text
        self._img = img

        self.setLayout(QVBoxLayout())
        self.lbPixmap = QLabel(self)
        self.lbText = QLabel(self)
        self.lbText.setAlignment(Qt.AlignCenter)

        self.layout().addWidget(self.lbPixmap)
        self.layout().addWidget(self.lbText)

        self.initUi()

    def initUi(self):
        # self.lbPixmap.setPixmap(QPixmap.fromImage(self._img).scaled(self.lbPixmap.size(),Qt.KeepAspectRatio))
        self.lbPixmap.setPixmap(QPixmap.fromImage(self._img))
        self.lbPixmap.setScaledContents(True)
        self.lbText.setText(self._text)

    @pyqtProperty(str)
    def img(self):
        return self._img

    @img.setter
    def total(self, value):
        if self._img == value:
            return
        self._img = value
        self.initUi()

    @pyqtProperty(str)
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        if self._text == value:
            return
        self._text = value
        self.initUi()

class TableWidget(QTableWidget):

    # signal_selected_cells = pyqtSignal(list)

    def __init__(self, rows = 10, columns = 10, parent=None):
        QTableWidget.__init__(self, parent)
        self.parent = parent
        self.num_cols = columns
        self.num_rows = rows
        self.id = None
        self.setColumnCount(columns)
        self.setRowCount(rows)
        self.cellClicked.connect(self.onCellClicked)
        # self.itemSelectionChanged.connect(self.onItemSelectionChanged)

    def populate_simulate(self, images, texts):
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                random_image = np.random.randint(0, 255, size=(256, 256, 3), dtype=np.uint8)
                qimage = QImage(random_image.data, random_image.shape[1], random_image.shape[0], QImage.Format_RGB888)
                lb = CustomWidget(str(i) + '_' + str(j), qimage)
                self.setCellWidget(i, j, lb)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        # self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(self.horizontalHeader().length()+80)
        self.setFixedHeight(5*self.rowHeight(0)+80)

    def populate(self, images, texts, annotations, image_id):
        self.id = image_id
        for i in range(self.rowCount()):
            for j in range(self.columnCount()):
                idx = i*self.num_cols + j
                if idx >= images.shape[0]:
                    self.setCellWidget(i, j, None)
                    # clear background - to improve the code
                    self.setItem(i, j, QTableWidgetItem())
                    palette = self.palette()
                    default_color = palette.color(QPalette.Window)
                    self.item(i,j).setBackground(default_color)
                else:
                    image = images[idx,].astype(np.uint8)
                    # resize
                    scale_factor = SCALE_FACTOR
                    new_height, new_width = int(image.shape[0] * scale_factor), int(image.shape[1] * scale_factor)
                    image = cv2.resize(image,(new_width, new_height),interpolation=cv2.INTER_NEAREST)
                    # image = np.random.randint(0, 255, size=(128, 128, 3), dtype=np.uint8)
                    # print(image.shape)
                    text = texts[idx]
                    qimage = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
                    lb = CustomWidget(text, qimage)
                    self.setCellWidget(i, j, lb)
                    # set color according to annotation
                    if annotations[idx] != -1:
                        self.setItem(i, j, QTableWidgetItem())
                        self.item(i,j).setBackground(COLOR_DICT[annotations[idx]])
                    else:
                        # clear background - to improve the code
                        self.setItem(i, j, QTableWidgetItem())
                        palette = self.palette()
                        default_color = palette.color(QPalette.Window)
                        self.item(i,j).setBackground(default_color)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.setFixedWidth(self.horizontalHeader().length()+80)
        self.setFixedHeight(min(self.num_rows,MAX_NUM_ROWS_DISPLAYED_PER_PAGE)*self.rowHeight(0)+80)
        # self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

    def get_selected_cells(self):
        list_of_selected_cells = []
        for index in self.selectedIndexes():
             # list_of_selected_cells.append((index.row(),index.column()))
             list_of_selected_cells.append( index.row()*self.num_cols + index.column() )
        return(list_of_selected_cells)

    def set_number_of_rows(self,rows):
        self.num_rows = rows
        self.setRowCount(rows)
        self.setFixedHeight(min(self.num_rows,MAX_NUM_ROWS_DISPLAYED_PER_PAGE)*self.rowHeight(0)+80)


    @pyqtSlot(int, int)
    def onCellClicked(self, row, column):
        w = self.cellWidget(row, column)
        if w:
            idx = row*self.num_cols + column
            print(str(self.id[idx]) + ' - ' + w.text)

    # @pyqtSlot()
    # def onItemSelectionChanged(self):
    #     selected_cells = self.get_selected_cells()
    #     self.signal_selected_cells.emit(selected_cells)

###########################################################################################
#####################################  Gallery View  ######################################
###########################################################################################

class GalleryViewWidget(QFrame):

    signal_switchTab = pyqtSignal()
    signal_similaritySearch = pyqtSignal(np.ndarray,np.ndarray,np.ndarray,np.ndarray,np.ndarray)
    signal_updatePage = pyqtSignal() # for updating the current page in other galleries
    signal_selected_images_idx_for_umap = pyqtSignal(list)
    signal_selection_cleared = pyqtSignal()

    def __init__(self, rows = 10, columns = 10, dataHandler=None, dataHandler2=None, is_main_gallery=False, is_for_similarity_search=False, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dataHandler = dataHandler
        self.dataHandler2 = dataHandler2 # secondary datahandler (in the similarity search gallery, this is linked to the full data)
        self.is_main_gallery = is_main_gallery
        self.image_id = None # for storing the ID of currently displayed images

        self.tableWidget = TableWidget(rows,columns,parent=self)
        self.tableWidget.itemSelectionChanged.connect(self.onSelectionChanged)

        # page navigation
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setMinimum(0)
        self.slider.setValue(0)
        self.slider.setSingleStep(1)

        self.entry = QSpinBox()
        self.entry.setMinimum(0)
        self.entry.setValue(0)

        self.entry_score_min = QDoubleSpinBox()
        self.entry_score_min.setDecimals(5)
        self.entry_score_min.setMinimum(0)
        self.entry_score_min.setMaximum(1)
        self.entry_score_min.setSingleStep(0.05)
        self.entry_score_min.setValue(0)

        self.entry_score_max = QDoubleSpinBox()
        self.entry_score_max.setDecimals(5)
        self.entry_score_max.setMinimum(0)
        self.entry_score_max.setMaximum(1)
        self.entry_score_max.setSingleStep(0.05)
        self.entry_score_max.setValue(1)

        # group the range widgets
        range_widget = QWidget()
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel('Score Min'))
        range_layout.addWidget(self.entry_score_min)
        range_layout.addWidget(QLabel('Score Max'))
        range_layout.addWidget(self.entry_score_max)
        range_widget.setLayout(range_layout)

        self.btn_search = QPushButton('Search Similar Images')
        self.btn_show_on_UMAP = QPushButton('Show on ' + dimentionality_reduction)
        self.btn_show_on_UMAP_live = QPushButton('Show on ' + dimentionality_reduction + ' live')
        self.btn_show_on_UMAP_live.setCheckable(True)
        self.btn_show_on_UMAP_live.setChecked(True)
        self.dropdown_sort = QComboBox()
        self.dropdown_sort.addItems(['Sort by prediction score','Sort by labels'])
        self.dropdown_filter = QComboBox()
        self.dropdown_filter.addItems(['Show all'] + ['Show ' + label for label in ANNOTATIONS_REVERSE_DICT.values()])
        if is_for_similarity_search:
            self.dropdown_sort.insertItem(0,'Sort by similarity')
            self.dropdown_sort.blockSignals(True)
            self.dropdown_sort.setCurrentIndex(0)
            self.dropdown_sort.blockSignals(False)

        # self.slider_range = QDoubleRangeSlider(Qt.Orientation.Horizontal) # not working properly
        # self.slider_range.setRange(0, 1)
        # self.slider_range.setValue((0.1, 0.9))

        self.btn_annotations = {}
        for key in ANNOTATIONS_DICT.keys():
            self.btn_annotations[key] = QPushButton(key)

        # add shortcuts
        self.shortcut = {}
        for key in ANNOTATIONS_DICT.keys():
            if ANNOTATIONS_DICT[key] >= 0:
                self.shortcut[key] = QShortcut(QKeySequence(str(ANNOTATIONS_DICT[key])), self)
                self.shortcut[key].activated.connect(self.btn_annotations[key].click)
        self.shortcut['-'] = QShortcut(QKeySequence('-'), self)
        self.shortcut['-'].activated.connect(self.btn_annotations['Remove Annotation'].click)

        vbox = QVBoxLayout()
        vbox.addWidget(self.tableWidget)
        grid = QGridLayout()
        slider = QHBoxLayout()
        slider.addWidget(self.entry)
        slider.addWidget(self.slider)
        grid.addLayout(slider,0,0,1,len(ANNOTATIONS_DICT))

        # grid.addWidget(self.dropdown_sort,2,0,1,len(ANNOTATIONS_DICT)-1)
        # grid.addWidget(self.dropdown_filter,2,len(ANNOTATIONS_DICT)-1,1,1)
        grid.addWidget(self.dropdown_sort,2,0,1,1)
        grid.addWidget(self.dropdown_filter,2,3,1,1)
        grid.addWidget(range_widget,2,1,1,2)
        # grid.addWidget(self.entry_score_min,2,2,1,1)
        # grid.addWidget(self.entry_score_max,2,3,1,1)

        '''
        if GENERATE_UMAP_FOR_FULL_DATASET:
            grid.addWidget(self.btn_search,4,0,1,len(ANNOTATIONS_DICT)-1)
            grid.addWidget(self.btn_show_on_UMAP_live,4,len(ANNOTATIONS_DICT)-1,1,1)
        else:
            grid.addWidget(self.btn_search,4,0,1,len(ANNOTATIONS_DICT)-1)
            grid.addWidget(self.btn_show_on_UMAP,4,len(ANNOTATIONS_DICT)-1,1,1)
        
        # frame = QFrame()
        # frame.setFrameShape(QFrame.HLine)
        # grid.addWidget(frame,4,0,1,len(ANNOTATIONS_DICT))

        i = 0
        for key in ANNOTATIONS_DICT.keys():
            grid.addWidget(self.btn_annotations[key],5,i)
            i = i + 1  
        '''

        vbox.addLayout(grid)
        self.setLayout(vbox)
        
        # connections
        self.entry.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.entry.setValue)
        self.entry.valueChanged.connect(self.update_page)
        self.btn_search.clicked.connect(self.do_similarity_search)
        self.dropdown_sort.currentTextChanged.connect(self.dataHandler.sort)
        self.dataHandler.signal_sorting_method.connect(self.update_displayed_sorting_method)
        for key in ANNOTATIONS_DICT.keys():
            self.btn_annotations[key].clicked.connect(functools.partial(self.assign_annotations,ANNOTATIONS_DICT[key]))
        self.btn_show_on_UMAP.clicked.connect(self.show_on_UMAP)

        self.dropdown_filter.currentTextChanged.connect(self.update_label_filter)
        self.entry_score_min.valueChanged.connect(self.dataHandler.set_filter_score_min)
        self.entry_score_max.valueChanged.connect(self.dataHandler.set_filter_score_max)

    def update_page(self):
        # clear selections
        self.tableWidget.clearSelection()
        # self.tableWidget.populate_simulate(None,None)
        if self.dataHandler is not None and self.dataHandler.images is not None:
            images,texts,self.image_id,annotations = self.dataHandler.get_page(self.entry.value())
            self.tableWidget.populate(images,texts,annotations,self.image_id)
        else:
            self.tableWidget.populate_simulate(None,None)

    def set_total_pages(self,n):
        self.slider.setMaximum(max(0,n-1))
        self.entry.setMaximum(max(0,n-1))
        self.slider.setTickInterval(int(np.ceil(n/10)))

    def populate_page0(self):
        self.entry.setValue(0)
        self.update_page()

    def do_similarity_search(self):
        selected_images = self.tableWidget.get_selected_cells()
        # ensure only one image is selected
        if len(selected_images) != 1:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("No image or more than one images selected. Please select one image.")
            msg.exec_()
            return
        # ensure a model is present
        if self.is_main_gallery:
            model_loaded = self.dataHandler.model_loaded
        else:
            model_loaded = self.dataHandler2.model_loaded
        if model_loaded == False:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Load a model first")
            msg.exec_()
            return
        '''
        # check if embedding has been loaded
        if self.dataHandler.embeddings_loaded != True:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Load the embeddings first.")
            msg.exec_()
            return
        '''
        # convert to global id
        selected_image = self.image_id[selected_images[0]]
        print( 'finding images similar to ' + str(selected_image) )

        # find similar images        
        if self.is_main_gallery:
            images, indices, scores, distances, annotations = self.dataHandler.find_similar_images(selected_image)
        else:
            images, indices, scores, distances, annotations = self.dataHandler2.find_similar_images(selected_image)
        # emit the results
        self.signal_similaritySearch.emit(images,indices,scores,distances,annotations)
        self.signal_switchTab.emit()

    def update_displayed_sorting_method(self,sorting_method):
        self.dropdown_sort.blockSignals(True)
        self.dropdown_sort.setCurrentText(sorting_method)
        self.dropdown_sort.blockSignals(False)

    def assign_annotations(self,annotation):
        selected_images = self.tableWidget.get_selected_cells() # index in the current page
        selected_images = [i for i in selected_images if i < len(self.image_id)] # filter it 
        # selected_images = self.image_id[selected_images] # global index of the images - this does not work for list, use the method below
        if len(selected_images) == 0:
            return
        selected_images = operator.itemgetter(*selected_images)(self.image_id) # selected_images = [self.image_id[i] for i in selected_images]
        print('label ' + str(selected_images) + ' as ' + str(annotation))
        self.dataHandler.update_annotation(selected_images,annotation)
        self.update_page()
        if self.is_main_gallery == False:
            # update for the full dataset
            self.dataHandler2.update_annotation(selected_images,annotation)
            self.signal_updatePage.emit()

    def set_number_of_rows(self,rows):
        self.tableWidget.set_number_of_rows(rows)
        self.signal_updatePage.emit()

    @pyqtSlot()
    def show_on_UMAP(self):

        # ensure UMAP fit has been done
        if self.is_main_gallery:
            model_loaded = self.dataHandler.reducer is not None
        else:
            model_loaded = self.dataHandler2.reducer is not None
        if model_loaded == False:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Generate UMAP first")
            msg.exec_()
            return

        if self.image_id is not None:
            selected_images = self.tableWidget.get_selected_cells() # index in the current page
            if len(selected_images) > 0:
                selected_images = [i for i in selected_images if i < len(self.image_id)] # filter it 
                selected_images = operator.itemgetter(*selected_images)(self.image_id) # selected_images = [self.image_id[i] for i in selected_images]
                selected_images = [selected_images] if not isinstance(selected_images, tuple) else list(selected_images)
                self.signal_selected_images_idx_for_umap.emit(selected_images)

    @pyqtSlot()
    def onSelectionChanged(self):
        selected_images = self.tableWidget.get_selected_cells() # index in the current page
        if self.image_id is not None:
            if self.btn_show_on_UMAP_live.isChecked() and GENERATE_UMAP_FOR_FULL_DATASET: # if SHOW_IMAGE_IN_SCATTER_PLOT_ON_SELECTION:
                # UMAP transform is too slow - almost 1 s on Mac - only do the "realtime" display if SHOW_IMAGE_IN_SCATTER_PLOT_ON_SELECTION
                if len(selected_images) > 0:
                    selected_images = [i for i in selected_images if i < len(self.image_id)] # filter it 
                    selected_images = operator.itemgetter(*selected_images)(self.image_id) # selected_images = [self.image_id[i] for i in selected_images]
                    selected_images = [selected_images] if not isinstance(selected_images, tuple) else list(selected_images)
                    self.signal_selected_images_idx_for_umap.emit(selected_images)
        # clear the overlay
        if len(selected_images) == 0:
            self.signal_selection_cleared.emit()

    def update_label_filter(self,filter_text):
        if filter_text == 'Show all':
            self.dataHandler.set_filter_labels(ANNOTATIONS_DICT.values())
        elif filter_text == 'Show not labeled':
            self.dataHandler.set_filter_labels([ANNOTATIONS_DICT['Remove Annotation']])
        elif filter_text == 'Show non-parasite':
            self.dataHandler.set_filter_labels([ANNOTATIONS_DICT['Label as non-parasite']])
        elif filter_text == 'Show parasite':
            self.dataHandler.set_filter_labels([ANNOTATIONS_DICT['Label as parasite']])
        elif filter_text == 'Show unsure':
            self.dataHandler.set_filter_labels([ANNOTATIONS_DICT['Label as unsure']])


class GalleryViewSettingsWidget(QFrame):

    signal_numRowsPerPage = pyqtSignal(int)
    signal_numImagesPerPage = pyqtSignal(int)
    signal_k_similaritySearch = pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.entry_num_rows_per_page = QSpinBox()
        self.entry_num_rows_per_page.setMinimum(NUM_ROWS)
        self.entry_num_rows_per_page.setValue(NUM_ROWS)
        self.entry_k_similarity_search = QSpinBox()
        self.entry_k_similarity_search.setMinimum(1)
        self.entry_k_similarity_search.setMaximum(10000)
        self.entry_k_similarity_search.setValue(K_SIMILAR_DEFAULT)
        
        grid_settings = QGridLayout()
        grid_settings.addWidget(QLabel('Number of rows per page'),0,0)
        grid_settings.addWidget(self.entry_num_rows_per_page,0,1)
        grid_settings.addWidget(QLabel('Number of images for similary search'),0,2)
        grid_settings.addWidget(self.entry_k_similarity_search,0,3)

        self.setLayout(grid_settings)

        # connections
        self.entry_num_rows_per_page.valueChanged.connect(self.update_num_rows_per_page)
        self.entry_k_similarity_search.valueChanged.connect(self.signal_k_similaritySearch.emit)

    def update_num_rows_per_page(self,rows):
        self.signal_numImagesPerPage.emit(rows*num_cols) # to change to NUM_COLS
        self.signal_numRowsPerPage.emit(rows)

###########################################################################################
##################################  Data Loader Widget  ###################################
###########################################################################################

class DataLoaderWidget(QFrame):

    def __init__(self, dataHandler, main=None, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.dataHandler = dataHandler
            self.setFrameStyle(QFrame.Panel | QFrame.Raised)
            # create widgets
            self.button_load_model = QPushButton('Load Model')
            self.button_load_images = QPushButton('Load Images')
            self.button_load_annotations = QPushButton('Load Annotations')
            self.button_load_model.setIcon(QIcon('icon/folder.png'))
            self.button_load_images.setIcon(QIcon('icon/folder.png'))
            self.button_load_annotations.setIcon(QIcon('icon/folder.png'))
            self.lineEdit_images = QLineEdit()
            self.lineEdit_images.setText('click the button to load')
            self.lineEdit_images.setReadOnly(True)
            self.lineEdit_annotations = QLineEdit()
            self.lineEdit_annotations.setText('click the button to load')
            self.lineEdit_annotations.setReadOnly(True)
            self.lineEdit_model = QLineEdit()
            self.lineEdit_model.setText('click the button to load')
            self.lineEdit_model.setReadOnly(True)
            # layout
            layout = QGridLayout()
            layout.addWidget(self.button_load_images,1,0)
            layout.addWidget(self.button_load_annotations,2,0)
            layout.addWidget(self.button_load_model,0,0)
            layout.addWidget(self.lineEdit_images,1,1)
            layout.addWidget(self.lineEdit_annotations,2,1)
            layout.addWidget(self.lineEdit_model,0,1)
            self.setLayout(layout)
            # connect
            self.button_load_images.clicked.connect(self.load_images)
            self.button_load_annotations.clicked.connect(self.load_annotations)
            self.button_load_model.clicked.connect(self.load_model)

    def load_images(self):
        dialog = QFileDialog()
        filename, _filter = dialog.getOpenFileName(None,'Open File','.','npy files (*.npy)')
        if filename:
            self.config_filename = filename
            if(os.path.isfile(filename)==True):
                if self.dataHandler.load_images(filename) == 0:
                    self.lineEdit_images.setText(filename)

    def load_annotations(self):
        dialog = QFileDialog()
        filename, _filter = dialog.getOpenFileName(None,'Open File','.','csv files (*.csv)')
        if filename:
            self.config_filename = filename
            if(os.path.isfile(filename)==True):
                if self.dataHandler.load_annotations(filename) == 0:
                    self.lineEdit_annotations.setText(filename)

    def load_model(self):
        dialog = QFileDialog()
        filename, _filter = dialog.getOpenFileName(None,'Open File','.','model (*.pt)')
        if filename:
            self.config_filename = filename
            if(os.path.isfile(filename)==True):
                self.lineEdit_model.setText(filename)
                self.dataHandler.load_model(filename)

###########################################################################################
##########################  Training and Visualization Widget  ############################
###########################################################################################

class TrainingAndVisualizationWidget(QFrame):

    def __init__(self, dataHandler):

        super().__init__()
        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.dataHandler = dataHandler

        self.btn_open_model_training = QPushButton("Open Model Training Dialog")
        self.label_model = QLabel()
        self.label_model.setMinimumWidth(100)
        self.label_model.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.max_points_label = QLabel("Max number of points for UMAP")
        self.entry_max_n_for_umap = QSpinBox()
        self.entry_max_n_for_umap.setMinimum(1000)
        self.entry_max_n_for_umap.setMaximum(1000000)
        self.entry_max_n_for_umap.setSingleStep(1000)
        self.entry_max_n_for_umap.setValue(1000)
        self.btn_generate_umap_visualization = QPushButton("Generate " + dimentionality_reduction + " Visualization")
        
        # Create the layout
        layout = QHBoxLayout()
        layout.addWidget(self.btn_open_model_training)
        # layout.addWidget(QLabel('Model'))
        layout.addWidget(self.label_model)
        layout.addStretch()
        if GENERATE_UMAP_FOR_FULL_DATASET == False:
            layout.addWidget(QLabel('Max n for UMAP'))
            layout.addWidget(self.entry_max_n_for_umap)
        layout.addWidget(self.btn_generate_umap_visualization)
        
        self.setLayout(layout)

        # connections
        self.btn_generate_umap_visualization.clicked.connect(self.generate_UMAP_visualization)

    def generate_UMAP_visualization(self):
        self.dataHandler.generate_UMAP_visualization(self.entry_max_n_for_umap.value())


###########################################################################################
#####################################  Data Handaler  #####################################
###########################################################################################

class DataHandler(QObject):

    signal_populate_page0 = pyqtSignal()
    signal_populate_top_results = pyqtSignal()
    signal_set_total_page_count = pyqtSignal(int)
    signal_sorting_method = pyqtSignal(str)
    signal_annotation_stats = pyqtSignal(np.ndarray)
    signal_predictions = pyqtSignal(np.ndarray,np.ndarray)
    signal_distances = pyqtSignal(np.ndarray)
    signal_UMAP_visualizations = pyqtSignal(np.ndarray,np.ndarray,np.ndarray) # to UMAP scatter plot
    signal_selected_images = pyqtSignal(np.ndarray,np.ndarray,np.ndarray,np.ndarray) # to selected images data handler
    signal_umap_embedding = pyqtSignal(np.ndarray,np.ndarray)

    # for training
    signal_progress = pyqtSignal(int)
    signal_update_loss = pyqtSignal(int,float,float)
    signal_training_complete = pyqtSignal()

    def __init__(self,is_for_similarity_search=False,is_for_selected_images=False):
        QObject.__init__(self)
        self.is_for_similarity_search = is_for_similarity_search
        self.is_for_selected_images = is_for_selected_images
        self.images = None
        self.image_path = None
        self.data_pd = None
        self.data_pd = None # annotation + prediction score + index
        self.embeddings = None
        self.model_loaded = False
        self.images_loaded = False
        self.embeddings_loaded = False
        self.annotations_loaded = False
        self.n_images_per_page = None
        self.spot_idx_sorted = None

        self.k_similar = K_SIMILAR_DEFAULT

        self.reducer = None # UMAP
        self.embeddings_umap = None

        # training
        self.stop_requested = False
        self.signal_training_complete.connect(self.on_training_complete)

        # filter for display
        self.filter_score_min = 0
        self.filter_score_max = 1
        self.filter_label = ANNOTATIONS_DICT.values()

    def load_model(self,path):
        # check whether it's a model or model state_dict
        if torch.cuda.is_available():
            loaded_model = torch.load(path)
        else:
            loaded_model = torch.load(path,map_location=torch.device('cpu'))
        if isinstance(loaded_model, dict):
            self.model = models.ResNet(model=model_spec['model'],n_channels=model_spec['n_channels'],n_filters=model_spec['n_filters'],
                n_classes=model_spec['n_classes'],kernel_size=model_spec['kernel_size'],stride=model_spec['stride'],padding=model_spec['padding'])
            if torch.cuda.is_available():
                self.model.load_state_dict(torch.load(path))
            else:
                self.model.load_state_dict(torch.load(path,map_location=torch.device('cpu')))
        else:
            if torch.cuda.is_available():
                self.model = torch.load(path)
            else:
                self.model = torch.load(path,map_location=torch.device('cpu'))

        self.model_loaded = True
        # if the images are already loaded, run the model
        if self.images_loaded:
            self.run_model()
            self.signal_populate_page0.emit()

    def load_images(self,images):
        # self.images = np.load(path)
        self.images = images
        self.image_path = ''
        
        if self.annotations_loaded:
            if self.images.shape[0] != self.data_pd.shape[0]:
                print('! dimension mismatch, create a new annotation file')
                self.data_pd = pd.DataFrame({'annotation':-1},index=np.arange(self.images.shape[0]))
                self.data_pd.index.name = 'index'
        else:
            self.data_pd = pd.DataFrame({'annotation':-1},index=np.arange(self.images.shape[0]))
            self.data_pd.index.name = 'index'

        self.images_loaded = True
        print('images loaded')
        
        # run the model if the model has been loaded
        if self.model_loaded == True:
            self.run_model()
        else:
            self.data_pd['output'] = -1 # placeholder value
            if self.spot_idx_sorted is None:
                # self.spot_idx_sorted = np.arange(self.images.shape[0]) # only populate the idx if it has not been populated
                self.spot_idx_sorted = self.data_pd[
                    ( self.data_pd['annotation'].isin(self.filter_label) ) &
                    ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                    ].index.to_numpy().astype(int) # apply the filters

        # display the images
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()
        
        return 0

    def load_predictions(self,annotation_pd):

        # annotation_pd = pd.read_csv(path,index_col='index')
        if 'output' in self.data_pd:
            self.data_pd = self.data_pd.drop(columns=['output'])
        self.data_pd = self.data_pd.merge(annotation_pd,left_index=True, right_index=True, how='outer')
        print(self.data_pd)
        # sort the predictions
        self.data_pd = self.data_pd.sort_values('output',ascending=False)
        # self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
        self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ].index.to_numpy().astype(int) # apply the filters
        
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()
        self.signal_sorting_method.emit('Sort by prediction score')

    def run_model(self):
        predictions, features = utils.generate_predictions_and_features(self.model,self.images,batch_size_inference)
        output_pd = pd.DataFrame({'output':predictions[:,0]},index=np.arange(self.images.shape[0]))
        if 'output' in self.data_pd:
            self.data_pd = self.data_pd.drop(columns=['output'])
        self.data_pd = self.data_pd.merge(output_pd,left_index=True,right_index=True)
        
        # sort the predictions
        self.data_pd = self.data_pd.sort_values('output',ascending=False)
        # self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
        self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ].index.to_numpy().astype(int) # apply the filters
        
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()
        self.signal_sorting_method.emit('Sort by prediction score')

        # embeddings
        self.embeddings = features
        self.embeddings_loaded = True
        self.neigh = KNeighborsClassifier(metric=KNN_METRIC)
        self.neigh.fit(self.embeddings, np.zeros(self.embeddings.shape[0]))

        # emit the results for display
        self.signal_predictions.emit(self.data_pd['output'].to_numpy(),self.data_pd['annotation'].to_numpy())

    def add_data(self,images,predictions_df, sort = False, disp_th = None):
    
        self.images = np.concatenate((images, self.images),axis=0)

        predictions_df.index += self.data_pd.shape[0]
        predictions_df['annotation'] = -1
        predictions_df = predictions_df.sort_values('output',ascending=False)
        self.data_pd = pd.concat([predictions_df, self.data_pd])

        print(self.images.shape)
        print(self.data_pd)
        if sort:
            sort_time = time.perf_counter_ns()
            self.data_pd = self.data_pd.sort_values('output',ascending=False)
            sort_time = time.perf_counter_ns()-sort_time
            print("data_pd sorting took: "+str(sort_time/10**6)+" ms")
        if disp_th is not None:
            print("setting display with threshold "+str(disp_th))
            no_spots_to_display = count_consecutive_rows_above_threshold(self.data_pd, 'output',disp_th)
            self.set_number_of_images_per_page(no_spots_to_display)
            print("displaying "+str(no_spots_to_display)+" spots")
        #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
        spot_idx_time = time.perf_counter_ns()
        if True:
            self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ].index.to_numpy().astype(int) # apply the filters
        spot_idx_time = time.perf_counter_ns()-spot_idx_time
        print(self.spot_idx_sorted)
        print("spot_idx_sorted generation took: "+str(spot_idx_time/10**6)+" ms")
        
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()
        self.signal_sorting_method.emit('Sort by prediction score')

    def start_training(self,model_name,n_filters,kernel_size,batch_size,n_epochs,reset_model):

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')

        # prepare the data
        data_annotated_pd = self.data_pd[self.data_pd['annotation'].isin([0, 1])]
        annotations = data_annotated_pd['annotation'].values
        indices = data_annotated_pd.index.to_numpy()
        print(indices)
        print(annotations)
        images = self.images[indices,]

        # if not os.path.exists('training records'):
        #     os.makedirs('training records')
        data_annotated_pd[['annotation']].to_csv(os.path.splitext(self.image_path)[0] + '_annotations_' + timestamp + '.csv')

        # init the model
        if reset_model or self.model_loaded==False:
            print('initialize the model')
            self.model = models.ResNet(model=model_name,n_channels=model_spec['n_channels'],n_filters=n_filters,
                n_classes=model_spec['n_classes'],kernel_size=kernel_size,stride=model_spec['stride'],padding=model_spec['padding'])

        # model_name for saving
        self.model_name = os.path.splitext(self.image_path)[0] + '_' + model_name + '_' + str(n_filters) + '_' + str(kernel_size) + '_' + str(batch_size) + '_' + timestamp

        # start training
        self.stop_requested = False
        self.thread = threading.Thread(target=utils.train_model,args=(self.model,images,annotations,batch_size,n_epochs,self.model_name),kwargs={'caller':self})
        self.thread.start()

    def stop_training(self):
        self.stop_requested = True

    def on_training_complete(self):
        self.run_model()
        self.signal_populate_page0.emit()

    def load_annotations(self,path):
        # load the annotation
        if self.data_pd is not None:
            annotation_pd = pd.read_csv(path,index_col='index')
            self.data_pd = self.data_pd.drop(columns=['annotation'])
            self.data_pd = self.data_pd.merge(annotation_pd,left_index=True, right_index=True, how='outer')
            self.signal_populate_page0.emit() # update the display
        else:
            self.data_pd = pd.read_csv(path,index_col='index')

        # size match check
        if self.images_loaded:
            if self.images.shape[0] != self.data_pd.shape[0]:
                print('! dimension mismatch')
                return 1
        self.annotations_loaded = True

        # update stats
        self.update_annotation_stats()

        # sort the annotations
        #self.data_pd = self.data_pd.sort_values('annotation',ascending=False)
        #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
        if self.spot_idx_sorted is None:
            self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ].index.to_numpy().astype(int) # apply the filters
        self.signal_sorting_method.emit('Sort by labels')
        
        # update the display if images have been loaded already
        if self.images_loaded:
            self.signal_populate_page0.emit()
        
        print('annotations loaded')
        return 0
        
    def set_number_of_images_per_page(self,n):
        self.n_images_per_page = n
        if self.spot_idx_sorted is not None:
            # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
            self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))

    def set_k_similar(self,k):
        self.k_similar = k

    def get_number_of_rows(self):
        if self.images is not None:
            return self.images.shape[0]
        else:
            return 0

    def get_page(self,page_number):
        idx_start = self.n_images_per_page*page_number
        idx_end = min(self.n_images_per_page*(page_number+1),self.images[self.spot_idx_sorted,:].shape[0])
        images = generate_overlay(self.images[self.spot_idx_sorted[idx_start:idx_end],:,:,:])
        texts = []
        image_id = []
        annotations = []
        '''
        for i in range(idx_start,idx_end):
            # texts.append( '[' + str(i) + ']  ' + str(self.data_pd.iloc[i]['index']) + ': ' + "{:.2f}".format(self.data_pd.iloc[i]['output']))
            if self.is_for_similarity_search:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['output']) + '\n{:.1e}'.format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['distance'])) # + '{:.1e}'.format(self.data_pd.iloc[i]['distances'])
                annotations.append(int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['annotation']))
            elif self.is_for_selected_images:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['output']) ) # + '{:.1e}'.format(self.data_pd.iloc[i]['distances'])
                annotations.append(int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['annotation']))
            else:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd.loc[self.spot_idx_sorted[i]]['output']))
                annotations.append(int(self.data_pd.loc[self.spot_idx_sorted[i]]['annotation']))
            image_id.append( self.spot_idx_sorted[i] )
        '''
        for i in range(idx_start,idx_end):
            # texts.append( '[' + str(i) + ']  ' + str(self.data_pd.iloc[i]['index']) + ': ' + "{:.2f}".format(self.data_pd.iloc[i]['output']))
            if self.is_for_similarity_search:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['output']) + '\n{:.1e}'.format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['distance'])) # + '{:.1e}'.format(self.data_pd.iloc[i]['distances'])
                annotations.append(int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['annotation']))
                image_id.append( int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['idx_global']) )
            elif self.is_for_selected_images:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd_local.loc[self.spot_idx_sorted[i]]['output']) ) # + '{:.1e}'.format(self.data_pd.iloc[i]['distances'])
                annotations.append(int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['annotation']))
                image_id.append( int(self.data_pd_local.loc[self.spot_idx_sorted[i]]['idx_global']) )
            else:
                texts.append( '[' + str(i) + ']  : ' + "{:.2f}".format(self.data_pd.loc[self.spot_idx_sorted[i]]['output']))
                annotations.append(int(self.data_pd.loc[self.spot_idx_sorted[i]]['annotation']))
                image_id.append( self.spot_idx_sorted[i] )
        return images, texts, image_id, annotations

    def sort(self,criterion):
        print(criterion)
        if criterion == 'Sort by prediction score':
            self.data_pd = self.data_pd.sort_values('output',ascending=False)
            '''
            self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ].index.to_numpy().astype(int)
            '''
        elif criterion == 'Sort by labels':
            self.data_pd = self.data_pd.sort_values('annotation',ascending=False)
        elif criterion == 'Sort by similarity':
            self.data_pd = self.data_pd.sort_values('distance',ascending=True)
        
        # update the sorted spot idx
        if self.is_for_similarity_search or self.is_for_selected_images:
            # self.spot_idx_sorted = self.data_pd['idx_local'].to_numpy().astype(int)
            self.spot_idx_sorted = self.data_pd[
                    ( self.data_pd['annotation'].isin(self.filter_label) ) &
                    ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                    ]['idx_local'].to_numpy().astype(int) # apply the filters
        else:
            #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
            self.spot_idx_sorted = self.data_pd[
                ( self.data_pd['annotation'].isin(self.filter_label) ) &
                ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                ].index.to_numpy().astype(int) # apply the filters
        self.signal_populate_page0.emit()
        self.signal_sorting_method.emit(criterion)

    def find_similar_images(self,idx):
        self.neigh.set_params(n_neighbors=min(self.k_similar+1,len(self.embeddings)))
        distances, indices = self.neigh.kneighbors(self.embeddings[idx,].reshape(1, -1), return_distance=True)
        distances = distances.squeeze()
        self.signal_distances.emit(distances)
        indices = indices.squeeze()
        images = self.images[indices,]
        scores = self.data_pd.loc[indices]['output'].to_numpy() # use the presorting idx
        annotations = self.data_pd.loc[indices]['annotation'].to_numpy() # use the presorting idx
        # return images[1:,], indices[1:], scores[1:], distances[1:], annotations[1:]
        return images, indices, scores, distances, annotations

    def populate_similarity_search(self,images,indices,scores,distances,annotations):
        self.images = images
        self.data_pd = pd.DataFrame({'idx_global':indices,'idx_local':np.arange(self.images.shape[0]).astype(int),'output':scores, 'distance':distances, 'annotation':annotations}) # idx_local for indexing the spot images
        self.data_pd_local = self.data_pd.copy()
        self.data_pd = self.data_pd.set_index('idx_global')
        self.data_pd_local = self.data_pd_local.set_index('idx_local')
        print('populated data_pd of the similarity search data handler:')
        print(self.data_pd)
        self.images_loaded = True
        # self.spot_idx_sorted = self.data_pd['index'].to_numpy().astype(int)
        # self.spot_idx_sorted = np.arange(self.images.shape[0]).astype(int)
        self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ]['idx_local'].to_numpy().astype(int) # apply the filters
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()

    def prepare_selected_images(self,indices):
        images = self.images[indices,]
        scores = self.data_pd.loc[indices]['output'].to_numpy() # use the presorting idx
        annotations = self.data_pd.loc[indices]['annotation'].to_numpy() # use the presorting idx
        # emit the results
        self.signal_selected_images.emit(images,indices,scores,annotations)

    def populate_selected_images(self,images,indices,scores,annotations):
        self.images = images
        self.data_pd = pd.DataFrame({'idx_global':indices,'idx_local':np.arange(self.images.shape[0]).astype(int),'output':scores, 'annotation':annotations},index=indices) # idx_local for indexing the spot images
        self.data_pd_local = self.data_pd.copy()
        self.data_pd = self.data_pd.set_index('idx_global')
        self.data_pd_local = self.data_pd_local.set_index('idx_local')
        print('populated data_pd of the selected images data handler:')
        print(self.data_pd)
        self.images_loaded = True
        # self.spot_idx_sorted = self.data_pd['index'].to_numpy().astype(int)
        # self.spot_idx_sorted = np.arange(self.images.shape[0]).astype(int)
        self.spot_idx_sorted = self.data_pd[
            ( self.data_pd['annotation'].isin(self.filter_label) ) &
            ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
            ]['idx_local'].to_numpy().astype(int) # apply the filters
        # self.signal_set_total_page_count.emit(int(np.ceil(self.get_number_of_rows()/self.n_images_per_page)))
        self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
        self.signal_populate_page0.emit()

    def update_annotation(self,index,annotation):
        # condition = df['index'].isin(index), df.loc[condition, 'annotation'] = annotation 
        # to-do: support dealing with multiple datasets using multi-level indexing
        self.data_pd.loc[index,'annotation'] = annotation
        if self.is_for_similarity_search or self.is_for_selected_images:
            # index_local = self.data_pd.loc[pd.Index(index),'idx_local'].tolist()
            if isinstance(index, int):  # If selected_rows is an integer
                index = [index]
            elif isinstance(index, tuple):  # If selected_rows is a tuple
                index = list(index)
            index_local = self.data_pd.loc[index,'idx_local'].tolist()
            self.data_pd_local.loc[index_local,'annotation'] = annotation # 20230323 - maybe data_pd_local is not useful
            print(self.data_pd)
        self.update_annotation_stats() # note - can also do it increamentally instead of going through the full df everytime

    def update_annotation_stats(self):
        # get annotation stats
        counts = []
        for label in ANNOTATIONS_REVERSE_DICT.keys():
            counts.append(sum(self.data_pd['annotation']==label))
        self.signal_annotation_stats.emit(np.array(counts))

    def save_annotations(self):
        if self.image_path:
            # remove the prediction score
            if 'output' in self.data_pd.columns:
                self.data_pd = self.data_pd.drop(columns=['output'])
            # save the annotations
            current_time = datetime.now().strftime('%Y-%m-%d_%H-%M')
            self.data_pd.to_csv(os.path.splitext(self.image_path)[0] + '_annotations_' + str(sum(self.data_pd['annotation']!=-1)) + '_' + str(self.data_pd.shape[0])  + '_' + current_time + '.csv')
            # remove the temporary file
            tmp_file = os.path.dirname(self.image_path)+'_tmp.csv'
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def generate_UMAP_visualization(self,n_max):
        if USE_UMAP:
            self.reducer = umap.UMAP(n_components=2)
        else:
            self.reducer = PCA(n_components=2)
        if GENERATE_UMAP_FOR_FULL_DATASET:
            t0 = time.time()
            self.embeddings_umap = self.reducer.fit_transform(self.embeddings)
            print('generating UMAP for ' + str(len(self.embeddings)) + ' data points took ' + str(time.time()-t0) + ' seconds')
            self.signal_UMAP_visualizations.emit(self.embeddings_umap[:,0],self.embeddings_umap[:,1],self.data_pd.sort_index()['annotation'].to_numpy())
        else:
            # sampling
            indices = np.random.choice(len(self.embeddings), min(len(self.embeddings),n_max), replace=False)
            # fit and transform
            t0 = time.time()
            umap_embedding = self.reducer.fit_transform(self.embeddings[indices,])
            print('generating UMAP for ' + str(len(indices)) + ' data points took ' + str(time.time()-t0) + ' seconds')
            # send the result to display
            annotations = self.data_pd.loc[indices]['annotation'].to_numpy() # use the presorting idx
            self.signal_UMAP_visualizations.emit(umap_embedding[:,0],umap_embedding[:,1],annotations)

    def to_umap_embedding(self,index):
        if self.embeddings is not None and self.reducer is not None:
            if GENERATE_UMAP_FOR_FULL_DATASET:
                self.signal_umap_embedding.emit(self.embeddings_umap[index,0],self.embeddings_umap[index,1])
            else:
                # do the transform 
                umap_embeddings = self.reducer.transform(self.embeddings[index,])
                self.signal_umap_embedding.emit(umap_embeddings[:,0],umap_embeddings[:,1])

    def set_filter_score_min(self,score):
        self.filter_score_min = score
        if self.data_pd is not None:
            if self.is_for_similarity_search or self.is_for_selected_images:
                # self.spot_idx_sorted = self.data_pd['idx_local'].to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                        ( self.data_pd['annotation'].isin(self.filter_label) ) &
                        ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                        ]['idx_local'].to_numpy().astype(int) # apply the filters
            else:
                #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                    ( self.data_pd['annotation'].isin(self.filter_label) ) &
                    ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                    ].index.to_numpy().astype(int) # apply the filters
            if self.spot_idx_sorted is not None:
                self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
                self.signal_populate_page0.emit()

    def set_filter_score_max(self,score):
        self.filter_score_max = score
        if self.data_pd is not None:
            if self.is_for_similarity_search or self.is_for_selected_images:
                # self.spot_idx_sorted = self.data_pd['idx_local'].to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                        ( self.data_pd['annotation'].isin(self.filter_label) ) &
                        ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                        ]['idx_local'].to_numpy().astype(int) # apply the filters
            else:
                #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                    ( self.data_pd['annotation'].isin(self.filter_label) ) &
                    ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                    ].index.to_numpy().astype(int) # apply the filters
            if self.spot_idx_sorted is not None:
                self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
                self.signal_populate_page0.emit()

    def set_filter_labels(self,labels):
        self.filter_label = labels
        if self.data_pd is not None:
            if self.is_for_similarity_search or self.is_for_selected_images:
                # self.spot_idx_sorted = self.data_pd['idx_local'].to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                        ( self.data_pd['annotation'].isin(self.filter_label) ) &
                        ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                        ]['idx_local'].to_numpy().astype(int) # apply the filters
            else:
                #self.spot_idx_sorted = self.data_pd.index.to_numpy().astype(int)
                self.spot_idx_sorted = self.data_pd[
                    ( self.data_pd['annotation'].isin(self.filter_label) ) &
                    ( ( self.data_pd['output'].between(self.filter_score_min,self.filter_score_max) ) | ( self.data_pd['output']==-1 ) )
                    ].index.to_numpy().astype(int) # apply the filters
            if self.spot_idx_sorted is not None:
                self.signal_set_total_page_count.emit(int(np.ceil(len(self.spot_idx_sorted)/self.n_images_per_page)))
                self.signal_populate_page0.emit()

###########################################################################################
#####################################  Matplotlib   #######################################
###########################################################################################

class PiePlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        #  create widgets
        self.view = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.view.figure.subplots()

        self.labels = list(ANNOTATIONS_REVERSE_DICT.values())
        self.counts = np.zeros(len(self.labels)) # self.counts = np.zeros(len(self.labels))
        self.counts[0] = 1 # to avoid divide by zero
        self.color = list(COLOR_DICT_PLOT.values())

        #  Create layout
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

        self._update_plot()

    def _update_plot(self):
        self.axes.clear()
        self.axes.pie(self.counts, explode = 0.1*np.ones(len(self.labels)), colors = self.color, shadow=False, startangle=0) # autopct='%1.1f%%', pctdistance=1.2
        self.axes.axis('equal')
        self.axes.legend(self.labels,loc='upper center',bbox_to_anchor=(0.5, 0.075),fancybox=True,ncol=int(len(self.labels)/2))
        self.view.draw()

    def update_plot(self,counts):
        self.counts = counts
        self._update_plot()

class BarPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        #  create widgets
        self.view = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.view.figure.subplots()

        self.labels = list(ANNOTATIONS_REVERSE_DICT.values())
        self.counts = np.zeros(len(self.labels)) # self.counts = np.zeros(len(self.labels))
        self.color = list(COLOR_DICT_PLOT.values())   

        #  Create layout
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

        self._update_plot()

    def _update_plot(self):
        self.axes.clear()
        self.barh = self.axes.barh(self.labels, self.counts, label=self.labels, tick_label=['']*4, color=self.color)
        if max(self.counts)==0:
            self.axes.set_xlim(0, 1)
        else:
            self.axes.autoscale(enable=True, axis='x')
        self.axes.get_xaxis().set_ticks([])
        self.axes.tick_params(left = False, bottom=False)
        # y_pos = np.arange(len(self.labels))
        # self.axes.set_yticks(y_pos, labels=self.labels)
        # self.axes.invert_yaxis()  # labels read top-to-bottom
        self.axes.bar_label(self.barh, fmt='%d')
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)
        legend = self.axes.legend(self.labels,loc='upper center',bbox_to_anchor=(0.5, 0.075),fancybox=True,ncol=int(len(self.labels)/2))
        bbox = legend.get_window_extent()
        # self.view.figure.set_size_inches(1.2*bbox.width/self.view.figure.dpi, self.view.figure.get_size_inches()[1])
        # self.view.setMinimumSize(self.view.sizeHint())
        # self.view.setMinimumSize(self.view.size())       
        self.view.draw()

    def update_plot(self,counts):
        self.counts = counts
        self._update_plot()

class HistogramPlotWidget(QWidget):

    signal_bringToFront = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        #  create widgets
        self.view = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.view.figure.subplots()

        self.score = None
        self.labels = list(ANNOTATIONS_REVERSE_DICT.values())

        #  Create layout
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

        self._update_plot()

    def _update_plot(self):
        if self.score is not None:
            self.axes.clear()
            for label in COLOR_DICT_PLOT.keys():
                x = self.score[self.annotation==label]
                self.axes.hist(x,bins=50,range=(0,1),color=COLOR_DICT_PLOT[label])
            self.view.draw()
            self.signal_bringToFront.emit()

    def update_plot(self,score,annotation):
        self.score = score
        self.annotation = annotation
        self._update_plot()

class StemPlotWidget(QWidget):

    signal_bringToFront = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        #  create widgets
        self.view = FigureCanvas(Figure(figsize=(5, 3)))
        self.axes = self.view.figure.subplots()

        self.values = None

        #  Create layout
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

        self._update_plot()

    def _update_plot(self):
        if self.values is not None:
            self.axes.clear()
            self.axes.stem(self.values)
            self.view.draw()
            self.signal_bringToFront.emit()

    def update_plot(self,values):
        self.values = values
        self._update_plot()


class ScatterPlotWidget(QWidget):

    signal_bringToFront = pyqtSignal()
    signal_selected_points = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        #  create widgets
        self.view = FigureCanvas(Figure(figsize=(5, 3)))
        self.toolbar = NavigationToolbar(self.view,self)
        # self.toolbar.toolitems = [t for t in NavigationToolbar.toolitems if t[0] in ('Home', 'Pan', 'Zoom', 'Save')]
        # self.toolbar.toolitems = [
        #     ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
        #     ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom')
        # ]
        # self.toolbar.update() # these didn't work

        with plt.ioff():
            self.axes = self.view.figure.subplots()

        self.x = None
        self.y = None
        self.annotation = None
        self.selector = None

        self.scatter = None
        self.scatter_overlay = None

        #  Create layout
        vlayout = QVBoxLayout()
        vlayout.addWidget(self.view)
        vlayout.addWidget(self.toolbar)
        self.setLayout(vlayout)

        # self.x = np.random.rand(5000, 1)
        # self.y = np.random.rand(5000, 1)
        # self.annotation = np.array([np.random.choice(list(COLOR_DICT_PLOT.keys())) for _ in range(5000)])
        # self._update_plot()

    def _update_plot(self):
        if self.x is not None:
            # get color
            # c = [COLOR_DICT_PLOT[label] for label in self.annotation.tolist()]
            lookup = np.vectorize(COLOR_DICT_PLOT.get)
            c = lookup(self.annotation)
            self.axes.clear()
            self.scatter = self.axes.scatter(self.x,self.y,c=c,s=SCATTER_SIZE)
            zoom_factory(self.axes)
            self.selector = SelectFromCollection(self.axes,self.scatter,alpha_other=0.1)
            self.selector.set_callback(self.on_select)
            self.view.draw()
            self.signal_bringToFront.emit()

    def update_plot(self,x,y,annotation):
        self.x = x
        self.y = y
        self.annotation = annotation
        self._update_plot()

    def on_select(self,selector):
        selected_points = selector.get_selection()
        # print(selected_points)
        self.signal_selected_points.emit(selected_points)

    def show_points(self,x,y):
        if self.scatter_overlay:
            '''
            try:
                self.scatter_overlay.remove()
            except:
                pass
            '''
            self.scatter_overlay.set_offsets(np.column_stack((x,y)))
        else:
            self.scatter_overlay = self.axes.scatter(x,y,s=SCATTER_SIZE_OVERLAY,c='#ff7f0e')
        self.view.draw_idle()

    def clear_overlay(self):
        if self.scatter_overlay:
            # self.scatter_overlay.remove()
            # self.scatter_overlay.set_offsets(np.array([[]]))
            if self.scatter_overlay:
                self.scatter_overlay.remove()
                self.scatter_overlay = None
                self.view.draw_idle()

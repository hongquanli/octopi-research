
QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

TEMPLATE = app

LIBS += -lgxiapi \

TARGET = GxViewer
TEMPLATE = app

unix:!mac:QMAKE_LFLAGS += -Wl,--rpath=.

INCLUDEPATH += ./include/

SOURCES += main.cpp\
    ExposureGain.cpp \
    GxViewer.cpp \
    ImageImprovement.cpp \
    AcquisitionThread.cpp \
    UserSetControl.cpp \
    Fps.cpp \
    Roi.cpp \
    FrameRateControl.cpp \
    WhiteBalance.cpp \
    Common.cpp

HEADERS += $$files(./include/*.h)

HEADERS  += \
    ExposureGain.h \
    GxViewer.h \
    ImageImprovement.h \
    AcquisitionThread.h \
    UserSetControl.h \
    Fps.h \
    Roi.h \
    FrameRateControl.h \
    Common.h \
    WhiteBalance.h

FORMS    += \
    ExposureGain.ui \
    GxViewer.ui \
    ImageImprovement.ui \
    UserSetControl.ui \
    Roi.ui \
    FrameRateControl.ui \
    WhiteBalance.ui


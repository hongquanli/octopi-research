//--------------------------------------------------------------------------------
/**
\file     Common.h
\brief    Common function declare and define macros of GxViewer

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------

#ifndef COMMON_H
#define COMMON_H

#include <QMessageBox>
#include <QString>
#include <QTimer>
#include <QMessageBox>
#include <QDialog>
#include <QComboBox>
#include <stdio.h>
#include <unistd.h>

#include "GxIAPI.h"
#include "DxImageProc.h"

#define FRAMERATE_INCREMENT     0.1
#define EXPOSURE_INCREMENT      1
#define GAIN_INCREMENT          0.1
#define WHITEBALANCE_DECIMALS   4
#define WHITEBALANCE_INCREMENT  0.0001

/// Release memory allocated
#define RELEASE_ALLOC_MEM(obj)    \
        if (obj != NULL)    \
        {   \
            delete obj;     \
            obj = NULL;     \
        }

/// Release memory(array) allocated
#define RELEASE_ALLOC_ARR(obj) \
        if (obj != NULL)    \
        {   \
            delete[] obj;   \
            obj = NULL;     \
        }

/// Judging current error ,show Error message and return
#define GX_VERIFY(emStatus) \
        if(emStatus != GX_STATUS_SUCCESS) \
        { \
           ShowErrorString(emStatus); \
           return; \
        }

/// Show Error Message
void ShowErrorString(GX_STATUS);

/// Get enum from device and insert UI ComboBox items
GX_STATUS InitComboBox(GX_DEV_HANDLE, QComboBox*, GX_FEATURE_ID);


#endif // COMMON_H

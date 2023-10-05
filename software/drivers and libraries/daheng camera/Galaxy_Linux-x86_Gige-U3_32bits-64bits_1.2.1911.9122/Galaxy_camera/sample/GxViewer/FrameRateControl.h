//--------------------------------------------------------------------------------
/**
\file     FrameRateControl.h
\brief    CFrameRateControl Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef FRAMERATECONTROL_H
#define FRAMERATECONTROL_H

#include "Common.h"

namespace Ui {
    class CFrameRateControl;
}

class CFrameRateControl : public QDialog
{
    Q_OBJECT

public:
    explicit CFrameRateControl(QWidget *parent = 0);
    ~CFrameRateControl();

    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:

    /// Clear Mainwindow items
    void ClearUI();

    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    Ui::CFrameRateControl *ui;

    GX_DEV_HANDLE        m_hDevice;                 ///< Device handle

    double               m_dFrameRate;              ///< Device acquisition frame rate

private slots:

    /// Close this dialog
    void on_FrameRateControl_Close_clicked();

    void on_AcquisitionFrameRateMode_activated(int);

    void on_AcquisitionFrameRateSpinBox_valueChanged(double);
};

#endif // FRAMERATECONTROL_H

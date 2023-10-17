//--------------------------------------------------------------------------------
/**
\file     CRoi.h
\brief    CRoi Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef ROI_H
#define ROI_H

#include "Common.h"

namespace Ui {
    class CRoi;
}

class CRoi : public QDialog
{
    Q_OBJECT

public:
    explicit CRoi(QWidget *parent = 0);
    ~CRoi();

    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:
    /// Update ROI UI Item range
    void ROIRangeUpdate();

    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    Ui::CRoi *ui;

    GX_DEV_HANDLE        m_hDevice;                 ///< Device handle

    int64_t              m_i64WidthInc;             ///< Image width increment
    int64_t              m_i64HeightInc;            ///< Image height increment
    int64_t              m_i64OffsetXInc;           ///< OffsetX increment
    int64_t              m_i64OffsetYInc;           ///< OffsetY increment

private slots:
    /// Close this dialog
    void on_ROISettingClose_clicked();

    void on_WidthSlider_valueChanged(int);

    void on_WidthSpin_valueChanged(int);

    void on_HeightSlider_valueChanged(int);

    void on_HeightSpin_valueChanged(int);

    void on_OffsetXSlider_valueChanged(int);

    void on_OffsetXSpin_valueChanged(int);

    void on_OffsetYSlider_valueChanged(int);

    void on_OffsetYSpin_valueChanged(int);
};

#endif // ROI_H

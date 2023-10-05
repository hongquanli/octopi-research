//--------------------------------------------------------------------------------
/**
\file     WhiteBalance.h
\brief    CWhiteBalance Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef WHITEBALANCE_H
#define WHITEBALANCE_H

#include "Common.h"

namespace Ui {
    class CWhiteBalance;
}

class CWhiteBalance : public QDialog
{
    Q_OBJECT

public:
    explicit CWhiteBalance(QWidget *parent = 0);
    ~CWhiteBalance();

    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:
    /// Clear Mainwindow items
    void ClearUI();

    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    void AWBROIRangeUpdate();

    Ui::CWhiteBalance *ui;

    GX_DEV_HANDLE           m_hDevice;                  ///< Device handle

    int64_t                 m_i64AWBWidthInc;           ///< AWBROI width increment
    int64_t                 m_i64AWBHeightInc;          ///< AWBROI height increment
    int64_t                 m_i64AWBOffsetXInc;         ///< AWBROI offsetx increment
    int64_t                 m_i64AWBOffsetYInc;         ///< AWBROI offesty increment

    QTimer                 *m_pWhiteBalanceTimer;       ///< Auto WhiteBalance refresh timer
private slots:
    /// Click for quit this dialog
    void on_WhiteBalance_Close_clicked();

    void on_BalanceRatioSelector_activated(int);

    void on_BalanceRatioSpin_valueChanged(double);

    void on_WhiteBalanceAuto_activated(int);

    void on_AWBLampHouse_activated(int);

    void on_AWBROIWidthSlider_valueChanged(int);

    void on_AWBROIWidthSpin_valueChanged(int);

    void on_AWBROIHeightSlider_valueChanged(int);

    void on_AWBROIHeightSpin_valueChanged(int);

    void on_AWBROIOffsetXSlider_valueChanged(int);

    void on_AWBROIOffsetXSpin_valueChanged(int);

    void on_AWBROIOffsetYSlider_valueChanged(int);

    void on_AWBROIOffsetYSpin_valueChanged(int);

    void WhiteBalanceRatioUpdate();

};

#endif // WHITEBALANCE_H

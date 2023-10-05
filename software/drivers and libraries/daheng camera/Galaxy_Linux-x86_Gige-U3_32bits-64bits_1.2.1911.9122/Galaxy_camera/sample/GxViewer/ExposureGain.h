//--------------------------------------------------------------------------------
/**
\file     ExposureGain.h
\brief    CExposureGain Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef EXPOSUREGAIN_H
#define EXPOSUREGAIN_H

#include "Common.h"



namespace Ui {
    class CExposureGain;
}

class CExposureGain : public QDialog
{
    Q_OBJECT

public:
    explicit CExposureGain(QWidget *parent = 0);
    ~CExposureGain();

    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:
    /// AAROI UI items range update
    void AAROIRangeUpdate();

    /// AutoExposureTime UI items range update
    void AutoExposureTimeRangeUpdate();

    /// AutoGain UI items range update
    void AutoGainRangeUpdate();

    /// Clear Mainwindow items
    void ClearUI();

    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    Ui::CExposureGain *ui;

    GX_DEV_HANDLE        m_hDevice;                     ///< Device handle

    double               m_dExposureTime;               ///< Exposure Time
    double               m_dAutoExposureTimeMax;        ///< Maximum exposure time when using AutoExporsureTime mode
    double               m_dAutoExposureTimeMin;        ///< Minimum exposure time when using AutoExporsureTime mode
    double               m_dGain;                       ///< Gain
    double               m_dAutoGainMax;                ///< Maximum gain when using AutoGain mode
    double               m_dAutoGainMin;                ///< Minimum gain when using AutoGain mode

    int64_t              m_i64AAROIWidth;               ///< AAROI Width
    int64_t              m_i64AAROIHeight;              ///< AAROI Height
    int64_t              m_i64AAROIOffsetX;             ///< AAROI OffsetX
    int64_t              m_i64AAROIOffsetY;             ///< AAROI OffsetY
    int64_t              m_i64AAWidthInc;               ///< AAROI width increment
    int64_t              m_i64AAHeightInc;              ///< AAROI height increment
    int64_t              m_i64AAOffsetXInc;             ///< AAROI offsetx increment
    int64_t              m_i64AAOffsetYInc;             ///< AAROI offsety increment
    int64_t              m_i64GrayValue;                ///< Expected gray value

    QTimer              *m_pExposureTimer;              ///< Auto Exposure refresh timer
    QTimer              *m_pGainTimer;                  ///< Auto Gain refresh timer

private slots:
    /// Click for quit this dialog
    void on_AA_Close_clicked();

    /// Update Exposure mode and value timeout slot
    void ExposureUpdate();

    /// Update Gain mode and value timeout slot
    void GainUpdate();

    void on_ExposureAuto_activated(int);

    void on_ExposureTimeSpin_valueChanged(double);

    void on_AutoExposureTimeMinSpin_valueChanged(double);

    void on_AutoExposureTimeMaxSpin_valueChanged(double);

    void on_GainAuto_activated(int);

    void on_GainSpin_valueChanged(double);

    void on_AutoGainMinSpin_valueChanged(double);

    void on_AutoGainMaxSpin_valueChanged(double);

    void on_AAROIWidthSlider_valueChanged(int);

    void on_AAROIWidthSpin_valueChanged(int);

    void on_AAROIHeightSlider_valueChanged(int);

    void on_AAROIHeightSpin_valueChanged(int);

    void on_AAROIOffsetXSlider_valueChanged(int);

    void on_AAROIOffsetXSpin_valueChanged(int);

    void on_AAROIOffsetYSlider_valueChanged(int);

    void on_AAROIOffsetYSpin_valueChanged(int);

    void on_ExpectedGrayValueSlider_valueChanged(int);

    void on_ExpectedGrayValueSpin_valueChanged(int);


};

#endif // EXPOSUREGAIN_H

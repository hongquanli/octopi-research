//--------------------------------------------------------------------------------
/**
\file     ImageImprovement.h
\brief    CImageImprovement Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef ImageImprovement_H
#define ImageImprovement_H

#include "Common.h"

namespace Ui {
    class CImageImprovement;
}

class CImageImprovement : public QDialog
{
    Q_OBJECT

public:
    explicit CImageImprovement(QWidget *parent = 0);
    ~CImageImprovement();

    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:
    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    Ui::CImageImprovement *ui;

    GX_DEV_HANDLE       m_hDevice;                  ///< Device handle

    bool                m_bImproveParamInit;        ///< Flag : Image improve parameter initialized or not
    int64_t             m_i64ColorCorrection;       ///< Color correction param
    unsigned char*      m_pGammaLut;                ///< Gamma look up table
    int                 m_nGammaLutLength;          ///< Gamma look up table length
    unsigned char*      m_pContrastLut;             ///< Contrast look up table
    int                 m_nContrastLutLength;       ///< Contrast look up table length

private slots:
    /// Click for quit this dialog
    void on_ImageImprovement_Close_clicked();

    void on_ColorCorrect_clicked(bool);

    void on_GammaCheckBox_clicked(bool);

    void on_ContrastCheckBox_clicked(bool);

    void on_GammaSpin_valueChanged(double);

    void on_ContrastSpin_valueChanged(int);

    void on_ContrastSlider_valueChanged(int);

signals:
    /// Send Color correction param
    void SigSendColorCorrectionParam(int64_t);

    /// Send Gamma LUT
    void SigSendGammaLUT(unsigned char*);

    /// Send Contrast LUT
    void SigSendContrastLUT(unsigned char*);
};

#endif // ImageImprovement_H

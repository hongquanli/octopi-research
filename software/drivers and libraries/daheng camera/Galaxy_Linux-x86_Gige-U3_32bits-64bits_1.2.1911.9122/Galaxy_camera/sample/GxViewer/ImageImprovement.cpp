//--------------------------------------------------------------------------------
/**
\file     ImageImprovement.cpp
\brief    CImageImprovement Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "ImageImprovement.h"
#include "ui_ImageImprovement.h"

//----------------------------------------------------------------------------------
/**
\ Constructor of CImageImprovement
*/
//----------------------------------------------------------------------------------
CImageImprovement::CImageImprovement(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::CImageImprovement),
    m_hDevice(NULL),
    m_bImproveParamInit(false),
    m_i64ColorCorrection(0),
    m_pGammaLut(NULL),
    m_nGammaLutLength(0),
    m_pContrastLut(NULL),
    m_nContrastLutLength(0)
{
    ui->setupUi(this);

    QFont font = this->font();
    font.setPointSize(10);
    this->setFont(font);

    //Avoid Strong focus policy which will exit this dialog by every time pressing "Enter"
    ui->ImageImprovement_Close->setFocusPolicy(Qt::NoFocus);

    // Close when Mainwindow is closed
    this->setAttribute(Qt::WA_QuitOnClose, false);

    // Set all spinbox do not emit the valueChanged() signal while typing.
    QObjectList pobjGroupList = this->children();
        foreach (QObject *pobjGroup, pobjGroupList)
        {
            QObjectList pobjItemList = pobjGroup->children();
            QAbstractSpinBox *pobjSpinbox;
            foreach (QObject *pobjItem, pobjItemList)
            {
                pobjSpinbox = qobject_cast<QAbstractSpinBox*>(pobjItem);
                if (pobjSpinbox)
                {
                    pobjSpinbox->setKeyboardTracking(false);
                }
            }
        }

    ui->GammaSpin->setEnabled(false);
    ui->ContrastSlider->setEnabled(false);
    ui->ContrastSpin->setEnabled(false);
}

//----------------------------------------------------------------------------------
/**
\ Destructor of CImageImprovement
*/
//----------------------------------------------------------------------------------
CImageImprovement::~CImageImprovement()
{
    RELEASE_ALLOC_ARR(m_pContrastLut);
    RELEASE_ALLOC_ARR(m_pGammaLut);

    delete ui;
}

//----------------------------------------------------------------------------------
/**
\ Close this dialog
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_ImageImprovement_Close_clicked()
{
    this->close();
}

//----------------------------------------------------------------------------------
/**
\ Enable all UI Groups
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::EnableUI()
{
    // Release item signals
    QObjectList pobjGroupList = this->children();
        foreach (QObject *pobjGroup, pobjGroupList)
        {
            QObjectList pobjItemList = pobjGroup->children();
            foreach (QObject *pobjItem, pobjItemList)
            {
                pobjItem->blockSignals(false);
            }
        }

    ui->ImageImprovement->setEnabled(true);
}

//----------------------------------------------------------------------------------
/**
\ Disable all UI Groups
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::DisableUI()
{
    // Block item signals
    QObjectList pobjGroupList = this->children();
        foreach (QObject *pobjGroup, pobjGroupList)
        {
            QObjectList pobjItemList = pobjGroup->children();
            foreach (QObject *pobjItem, pobjItemList)
            {
                pobjItem->blockSignals(true);
            }
        }

    ui->ImageImprovement->setEnabled(false);
}

//----------------------------------------------------------------------------------
/**
\ Get device handle from mainwindow, and get param for this dialog
\param[in]      hDeviceHandle   Device handle
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::GetDialogInitParam(GX_DEV_HANDLE hDeviceHandle)
{
    m_hDevice = hDeviceHandle;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    int64_t i64ContrastParam = 0;
    int64_t i64ColorCorrection = 0;
    double dGammaParam = 0;

    // Image improve parameter does not storage in camera, so we need not to initialize them again
    if (m_bImproveParamInit)
    {
        return;
    }

    // Disable all UI items and block signals
    DisableUI();

    bool bContrast = false;
    emStatus = GXIsImplemented(m_hDevice, GX_INT_CONTRAST_PARAM, &bContrast);
    GX_VERIFY(emStatus);
    if (bContrast)
    {
        // Get contrast adjustment parameters
        emStatus = GXGetInt (m_hDevice, GX_INT_CONTRAST_PARAM, &i64ContrastParam);
        GX_VERIFY(emStatus);

        // Contrast value range(Contrast range is fixed)
        const int nContrastMax = 100;
        const int nContrastMin = -50;
        const int nContrastInc = 1;

        // Set range of contrast input
        ui->ContrastSlider->setRange(nContrastMin, nContrastMax);
        ui->ContrastSlider->setSingleStep(nContrastInc);
        ui->ContrastSlider->setPageStep(nContrastInc);
        ui->ContrastSpin->setRange(nContrastMin, nContrastMax);
        ui->ContrastSpin->setSingleStep(nContrastInc);
        ui->ContrastSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                            .arg(nContrastMin)
                                            .arg(nContrastMax)
                                            .arg(nContrastInc));
        ui->ContrastSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                            .arg(nContrastMin)
                                            .arg(nContrastMax)
                                            .arg(nContrastInc));
        ui->ContrastSlider->setValue(i64ContrastParam);
        ui->ContrastSpin->setValue(i64ContrastParam);
    }

    bool bColorCorrection = false;
    emStatus = GXIsImplemented(m_hDevice, GX_INT_COLOR_CORRECTION_PARAM, &bColorCorrection);
    GX_VERIFY(emStatus);
    if (bColorCorrection)
    {
        // Get color correction adjustment parameters
        emStatus = GXGetInt (m_hDevice, GX_INT_COLOR_CORRECTION_PARAM, &i64ColorCorrection);
        GX_VERIFY(emStatus);
    }

    bool bGamma = false;
    emStatus = GXIsImplemented(m_hDevice, GX_FLOAT_GAMMA_PARAM, &bGamma);
    GX_VERIFY(emStatus);
    if (bGamma)
    {
        // Get Gamma parameter
        emStatus = GXGetFloat(m_hDevice, GX_FLOAT_GAMMA_PARAM, &dGammaParam);
        GX_VERIFY(emStatus);

        // Gamma value range(Gamma range is fixed)
        const double dGammaMax = 10.0;
        const double dGammaMin = 0.1;
        const double dGammaInc = 0.1      ;

        // Set range of gamma input
        ui->GammaSpin->setRange(dGammaMin, dGammaMax);
        ui->GammaSpin->setSingleStep(dGammaInc);
        ui->GammaSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                    .arg(dGammaMin, 0, 'f', 1)
                                    .arg(dGammaMax, 0, 'f', 1)
                                    .arg(dGammaInc));
        ui->GammaSpin->setValue(dGammaParam);
    }

    // Set UI Items status
    ui->ContrastCheckBox->setEnabled(bContrast);
    ui->ColorCorrect->setEnabled(bColorCorrection);
    ui->GammaCheckBox->setEnabled(bGamma);

    // Set Improve parameter initialized flag
    m_bImproveParamInit = true;

    // Enable all UI Items and release signals when initialze success
    EnableUI();

    return;
}

//----------------------------------------------------------------------------------
/**
\ Color Correct CheckBox clicked slot
\param[in]      bChecked     CheckBox being checked or not
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_ColorCorrect_clicked(bool bChecked)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    if (bChecked)
    {
        // Get color correction parameter
        emStatus = GXGetInt(m_hDevice, GX_INT_COLOR_CORRECTION_PARAM, &m_i64ColorCorrection);
        if (emStatus != GX_STATUS_SUCCESS)
        {
            ui->ColorCorrect->setChecked(false);
            return;
        }
    }
    else
    {
        // Disable color correction
        m_i64ColorCorrection = 0;
    }

    // Send color correction param
    emit SigSendColorCorrectionParam(m_i64ColorCorrection);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Gamma CheckBox clicked slot
\param[in]      bChecked     CheckBox being checked or not
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_GammaCheckBox_clicked(bool bChecked)
{
    VxInt32 emDxStatus = DX_OK;

    if (bChecked)
    {
        // Get gamma param from SpinBox
        double dGammaParam = ui->GammaSpin->value();

        // If LUT not allocated, allocate memory for LUT
        if (m_pGammaLut == NULL)
        {
            // Get LUT length of Gamma LUT
            emDxStatus = DxGetGammatLut(dGammaParam, NULL, &m_nGammaLutLength);
            if (emDxStatus != DX_OK)
            {
                QMessageBox::about(NULL, "DxGetGammatLUT Error", "Error : Get gamma LUT length failed!");
                ui->GammaCheckBox->setChecked(false);
                ui->GammaSpin->setEnabled(false);
                return;
            }

            try
            {
                m_pGammaLut = new unsigned char[m_nGammaLutLength];
            }
            catch (std::bad_alloc &e)
            {
                QMessageBox::about(NULL, "Allocate memory error", "Cannot allocate memory, please exit this app!");
                RELEASE_ALLOC_MEM(m_pGammaLut);
                return;
            }
        }

        // Get Gamma LUT
        emDxStatus = DxGetGammatLut(dGammaParam, m_pGammaLut, &m_nGammaLutLength);
        if (emDxStatus != DX_OK)
        {
            RELEASE_ALLOC_ARR(m_pGammaLut);
            QMessageBox::about(NULL, "DxGetGammatLUT Error", "Error : Get gamma LUT failed!");
            ui->GammaCheckBox->setChecked(false);
            ui->GammaSpin->setEnabled(false);
            return;
        }

        emit SigSendGammaLUT(m_pGammaLut);
    }
    else
    {
        emit SigSendGammaLUT(NULL);
    }

    ui->GammaSpin->setEnabled(bChecked);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Contrast CheckBox clicked slot
\param[in]      bChecked     CheckBox being checked or not
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_ContrastCheckBox_clicked(bool bChecked)
{
    VxInt32 emDxStatus = DX_OK;

    if (bChecked)
    {
        // Get contrast value from ContrastSpin
        int nContrastParam = ui->ContrastSpin->value();

        // If LUT not allocated, allocate memory for LUT
        if (m_pContrastLut == NULL)
        {
            // Get LUT length of Contrast LUT
            emDxStatus = DxGetContrastLut(nContrastParam, NULL, &m_nContrastLutLength);
            if (emDxStatus != DX_OK)
            {
                RELEASE_ALLOC_ARR(m_pContrastLut);
                QMessageBox::about(NULL, "DxGetContrastLut Error", "Error : Get contrast LUT length failed");
                ui->ContrastCheckBox->setChecked(false);
                ui->ContrastSlider->setEnabled(false);
                ui->ContrastSpin->setEnabled(false);
                return;
            }

            try
            {
                m_pContrastLut = new unsigned char[m_nContrastLutLength];
            }
            catch (std::bad_alloc &e)
            {
                QMessageBox::about(NULL, "Allocate memory error", "Cannot allocate memory, please exit this app!");
                RELEASE_ALLOC_MEM(m_pGammaLut);
                return;
            }
        }

        // Get Contrast LUT
        emDxStatus = DxGetContrastLut(nContrastParam, m_pContrastLut, &m_nContrastLutLength);
        if (emDxStatus != DX_OK)
        {
            RELEASE_ALLOC_ARR(m_pContrastLut);
            QMessageBox::about(NULL, "DxGetContrastLut Error", "Error : Get contrast LUT failed");
            ui->ContrastCheckBox->setChecked(false);
            ui->ContrastSlider->setEnabled(false);
            ui->ContrastSpin->setEnabled(false);
            return;
        }

        emit SigSendContrastLUT(m_pContrastLut);
    }
    else
    {
        emit SigSendContrastLUT(NULL);
    }

    ui->ContrastSlider->setEnabled(bChecked);
    ui->ContrastSpin->setEnabled(bChecked);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Gamma Spin value changed slot
\param[in]      dGamma Gamma user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_GammaSpin_valueChanged(double dGamma)
{
    VxInt32 emDxStatus = DX_OK;

    // Get Gamma LUT
    emDxStatus = DxGetGammatLut(dGamma, m_pGammaLut, &m_nGammaLutLength);
    if (emDxStatus != DX_OK)
    {
        RELEASE_ALLOC_ARR(m_pGammaLut);
        QMessageBox::about(NULL, "DxGetGammatLUT Error", "Error : Get gamma LUT failed!");
        return;
    }

    emit SigSendGammaLUT(m_pGammaLut);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Contrast Slider value changed slot
\param[in]      nContrast   Contrast value from slider
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_ContrastSlider_valueChanged(int nContrast)
{
    VxInt32 emDxStatus = DX_OK;

    // Get Contrast LUT
    emDxStatus = DxGetContrastLut(nContrast, m_pContrastLut, &m_nContrastLutLength);
    if (emDxStatus != DX_OK)
    {
        RELEASE_ALLOC_ARR(m_pContrastLut);
        QMessageBox::about(NULL, "DxGetContrastLut Error", "Error : Get contrast LUT failed");
        return;
    }

    ui->ContrastSpin->setValue(nContrast);

    emit SigSendContrastLUT(m_pContrastLut);

    return;
}


//----------------------------------------------------------------------------------
/**
\ Contrast Spin value changed slot
\param[in]      nContrast   Contrast user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CImageImprovement::on_ContrastSpin_valueChanged(int nContrast)
{
    VxInt32 emDxStatus = DX_OK;

    // Get Contrast LUT
    emDxStatus = DxGetContrastLut(nContrast, m_pContrastLut, &m_nContrastLutLength);
    if (emDxStatus != DX_OK)
    {
        RELEASE_ALLOC_ARR(m_pContrastLut);
        QMessageBox::about(NULL, "DxGetContrastLut Error", "Error : Get contrast LUT failed");
        return;
    }

    ui->ContrastSlider->setValue(nContrast);

    emit SigSendContrastLUT(m_pContrastLut);

    return;
}

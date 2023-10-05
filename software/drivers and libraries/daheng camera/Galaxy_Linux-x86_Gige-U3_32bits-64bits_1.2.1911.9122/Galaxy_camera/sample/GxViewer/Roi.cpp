//--------------------------------------------------------------------------------
/**
\file     Roi.cpp
\brief    CRoi Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "Roi.h"
#include "ui_Roi.h"

//----------------------------------------------------------------------------------
/**
\Constructor of CRoi
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
CRoi::CRoi(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::CRoi),
    m_hDevice(NULL),
    m_i64WidthInc(0),
    m_i64HeightInc(0),
    m_i64OffsetXInc(0),
    m_i64OffsetYInc(0)
{
    ui->setupUi(this);

    QFont font = this->font();
    font.setPointSize(10);
    this->setFont(font);

    //This property holds the way the widget accepts keyboard focus.
    //Avoid other focus policy which will exit this dialog by every time pressing "Enter"
    ui->ROISettingClose->setFocusPolicy(Qt::NoFocus);

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
}

//----------------------------------------------------------------------------------
/**
\Destructor of CRoi
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
CRoi::~CRoi()
{
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
void CRoi::on_ROISettingClose_clicked()
{
    this->close();

    return;
}

//----------------------------------------------------------------------------------
/**
\ Enable all UI Groups
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::EnableUI()
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

    ui->ROISettings->setEnabled(true);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Disable all UI Groups
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::DisableUI()
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

    ui->ROISettings->setEnabled(false);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Update ROI UI Item range
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::ROIRangeUpdate()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    GX_INT_RANGE stIntRange;

    // Get the range of image width (nMax is Maximum, nMin is Minimum, nInc is Step)
    emStatus = GXGetIntRange(m_hDevice, GX_INT_WIDTH, &stIntRange);
    GX_VERIFY(emStatus);

    m_i64WidthInc = stIntRange.nInc;

    ui->WidthSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->WidthSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->WidthSlider->setSingleStep(stIntRange.nInc);
    ui->WidthSlider->setPageStep(0);
    ui->WidthSpin->setSingleStep(stIntRange.nInc);
    ui->WidthSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                              .arg(stIntRange.nMin)
                              .arg(stIntRange.nMax)
                              .arg(stIntRange.nInc));
    ui->WidthSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                .arg(stIntRange.nMin)
                                .arg(stIntRange.nMax)
                                .arg(stIntRange.nInc));

    // Get the range of image height (nMax is Maximum, nMin is Minimum, nInc is Step)
    emStatus = GXGetIntRange(m_hDevice, GX_INT_HEIGHT, &stIntRange);
    GX_VERIFY(emStatus);

    m_i64HeightInc = stIntRange.nInc;

    ui->HeightSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->HeightSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->HeightSlider->setSingleStep(stIntRange.nInc);
    ui->HeightSlider->setPageStep(0);
    ui->HeightSpin->setSingleStep(stIntRange.nInc);
    ui->HeightSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                               .arg(stIntRange.nMin)
                               .arg(stIntRange.nMax)
                               .arg(stIntRange.nInc));
    ui->HeightSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                 .arg(stIntRange.nMin)
                                 .arg(stIntRange.nMax)
                                 .arg(stIntRange.nInc));

    // Get the range of image offsetx (nMax is Maximum, nMin is Minimum, nInc is Step)
    emStatus = GXGetIntRange(m_hDevice, GX_INT_OFFSET_X, &stIntRange);
    GX_VERIFY(emStatus);

    m_i64OffsetXInc = stIntRange.nInc;

    ui->OffsetXSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->OffsetXSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->OffsetXSlider->setSingleStep(stIntRange.nInc);
    ui->OffsetXSlider->setPageStep(0);
    ui->OffsetXSpin->setSingleStep(stIntRange.nInc);
    ui->OffsetXSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                .arg(stIntRange.nMin)
                                .arg(stIntRange.nMax)
                                .arg(stIntRange.nInc));
    ui->OffsetXSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                  .arg(stIntRange.nMin)
                                  .arg(stIntRange.nMax)
                                  .arg(stIntRange.nInc));

    // Get the range of image offsety (nMax is Maximum, nMin is Minimum, nInc is Step)
    emStatus = GXGetIntRange(m_hDevice, GX_INT_OFFSET_Y, &stIntRange);
    GX_VERIFY(emStatus);

    m_i64OffsetYInc = stIntRange.nInc;

    ui->OffsetYSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->OffsetYSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->OffsetYSlider->setSingleStep(stIntRange.nInc);
    ui->OffsetYSlider->setPageStep(0);
    ui->OffsetYSpin->setSingleStep(stIntRange.nInc);
    ui->OffsetYSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                .arg(stIntRange.nMin)
                                .arg(stIntRange.nMax)
                                .arg(stIntRange.nInc));
    ui->OffsetYSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                  .arg(stIntRange.nMin)
                                  .arg(stIntRange.nMax)
                                  .arg(stIntRange.nInc));

    return;
}

//----------------------------------------------------------------------------------
/**
\ Get device handle from mainwindow, and get param for this dialog
\param[in]      hDeviceHandle   Device handle
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::GetDialogInitParam(GX_DEV_HANDLE hDeviceHandle)
{
    // Device handle transfered and storaged
    m_hDevice = hDeviceHandle;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Disable all UI items and block signals
    DisableUI();

    /// ******************************************************************************************** ///
    /// Width, Height, OffsetX, OffsetY part
    /// ******************************************************************************************** ///
    // Get image width
    int64_t i64ImageWidth = 0;
    emStatus = GXGetInt(m_hDevice, GX_INT_WIDTH, &i64ImageWidth);
    GX_VERIFY(emStatus);

    // Get image height
    int64_t i64ImageHeight = 0;
    emStatus = GXGetInt(m_hDevice, GX_INT_HEIGHT, &i64ImageHeight);
    GX_VERIFY(emStatus);

    // Get image offsetx
    int64_t i64ImageOffsetX = 0;
    emStatus = GXGetInt(m_hDevice, GX_INT_OFFSET_X, &i64ImageOffsetX);
    GX_VERIFY(emStatus);

    // Get image offsety
    int64_t i64ImageOffsetY = 0;
    emStatus = GXGetInt(m_hDevice, GX_INT_OFFSET_Y, &i64ImageOffsetY);
    GX_VERIFY(emStatus);

    ROIRangeUpdate();

    // Set value to UI item
    ui->WidthSlider->setValue(i64ImageWidth);
    ui->WidthSpin->setValue(i64ImageWidth);
    ui->HeightSlider->setValue(i64ImageHeight);
    ui->HeightSpin->setValue(i64ImageHeight);
    ui->OffsetXSlider->setValue(i64ImageOffsetX);
    ui->OffsetXSpin->setValue(i64ImageOffsetX);
    ui->OffsetYSlider->setValue(i64ImageOffsetY);
    ui->OffsetYSpin->setValue(i64ImageOffsetY);

    // Enable all UI Items and release signals when initialze success
    EnableUI();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the width slider slot
\param[in]      nWidth  Width value changed
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_WidthSlider_valueChanged(int nWidth)
{
    // slider value may incompatible with the step of parameter, adjust to its multiple
    nWidth = (nWidth / m_i64WidthInc) * m_i64WidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_WIDTH, nWidth);
    GX_VERIFY(emStatus);

    ui->WidthSpin->setValue(nWidth);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the width spin slot
\param[in]      nWidth  Width user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_WidthSpin_valueChanged(int nWidth)
{
    // user input value may incompatible with the step of parameter, adjust to its multiple
    nWidth = (nWidth / m_i64WidthInc) * m_i64WidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_WIDTH, nWidth);
    GX_VERIFY(emStatus);

    ui->WidthSpin->setValue(nWidth);
    ui->WidthSlider->setValue(nWidth);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the height slider slot
\param[in]      nHeight  Height value changed
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_HeightSlider_valueChanged(int nHeight)
{
    // slider value may incompatible with the step of parameter, adjust to its multiple
    nHeight = (nHeight / m_i64HeightInc) * m_i64HeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_HEIGHT, nHeight);
    GX_VERIFY(emStatus);

    ui->HeightSpin->setValue(nHeight);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the height spin slot
\param[in]      nHeight  Height user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_HeightSpin_valueChanged(int nHeight)
{
    // user input value may incompatible with the step of parameter, adjust to its multiple
    nHeight = (nHeight / m_i64HeightInc) * m_i64HeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_HEIGHT, nHeight);
    GX_VERIFY(emStatus);

    ui->HeightSpin->setValue(nHeight);
    ui->HeightSlider->setValue(nHeight);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the offsetx slider slot
\param[in]    nOffsetX  OffsetX value changed
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_OffsetXSlider_valueChanged(int nOffsetX)
{
    // slider value may incompatible with the step of parameter, adjust to its multiple
    nOffsetX = (nOffsetX / m_i64OffsetXInc) * m_i64OffsetXInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_OFFSET_X, nOffsetX);
    GX_VERIFY(emStatus);

    ui->OffsetXSpin->setValue(nOffsetX);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the offsetx spin slot
\param[in]      nOffsetX  OffsetX user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_OffsetXSpin_valueChanged(int nOffsetX)
{
    // user input value may incompatible with the step of parameter, adjust to its multiple
    nOffsetX = (nOffsetX / m_i64OffsetXInc) * m_i64OffsetXInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_OFFSET_X, nOffsetX);
    GX_VERIFY(emStatus);

    ui->OffsetXSpin->setValue(nOffsetX);
    ui->OffsetXSlider->setValue(nOffsetX);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the offsety slider slot
\param[in]      nOffsetY  OffsetY value changed
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_OffsetYSlider_valueChanged(int nOffsetY)
{
    // slider value may incompatible with the step of parameter, adjust to its multiple
    nOffsetY = (nOffsetY / m_i64OffsetYInc) * m_i64OffsetYInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_OFFSET_Y, nOffsetY);
    GX_VERIFY(emStatus);

    ui->OffsetYSpin->setValue(nOffsetY);

    ROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\Change the value of the offsety spin slot
\param[in]      nOffsetY  OffsetY user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CRoi::on_OffsetYSpin_valueChanged(int nOffsetY)
{
    // user input value may incompatible with the step of parameter, adjust to its multiple
    nOffsetY = (nOffsetY / m_i64OffsetYInc) * m_i64OffsetYInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_OFFSET_Y, nOffsetY);
    GX_VERIFY(emStatus);

    ui->OffsetYSpin->setValue(nOffsetY);
    ui->OffsetYSlider->setValue(nOffsetY);

    ROIRangeUpdate();

    return;
}


//--------------------------------------------------------------------------------
/**
\file     WhiteBalance.cpp
\brief    CWhiteBalance Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "WhiteBalance.h"
#include "ui_WhiteBalance.h"

//----------------------------------------------------------------------------------
/**
\Constructor of CWhiteBalance
*/
//----------------------------------------------------------------------------------
CWhiteBalance::CWhiteBalance(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::CWhiteBalance),
    m_hDevice(NULL),
    m_i64AWBWidthInc(0),
    m_i64AWBHeightInc(0),
    m_i64AWBOffsetXInc(0),
    m_i64AWBOffsetYInc(0),
    m_pWhiteBalanceTimer(NULL)
{
    ui->setupUi(this);

    QFont font = this->font();
    font.setPointSize(10);
    this->setFont(font);

    //This property holds the way the widget accepts keyboard focus.
    //Avoid other focus policy which will exit this dialog by every time pressing "Enter"
    ui->WhiteBalance_Close->setFocusPolicy(Qt::NoFocus);

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

    // Setup auto change parameter refresh timer
    m_pWhiteBalanceTimer = new QTimer(this);
    connect(m_pWhiteBalanceTimer, SIGNAL(timeout()), this, SLOT(WhiteBalanceRatioUpdate()));
}

//----------------------------------------------------------------------------------
/**
\Destructor of CWhiteBalance
*/
//----------------------------------------------------------------------------------
CWhiteBalance::~CWhiteBalance()
{
    RELEASE_ALLOC_MEM(m_pWhiteBalanceTimer)

    ClearUI();

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
void CWhiteBalance::on_WhiteBalance_Close_clicked()
{
    this->close();

    return;
}

//----------------------------------------------------------------------------------
/**
\Clear ComboBox Items
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::ClearUI()
{
    // Clear ComboBox items
    ui->BalanceRatioSelector->clear();
    ui->WhiteBalanceAuto->clear();
    ui->AWBLampHouse->clear();

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
void CWhiteBalance::EnableUI()
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

    ui->Balance_White->setEnabled(true);

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
void CWhiteBalance::DisableUI()
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

    ui->Balance_White->setEnabled(false);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Update AWBROI UI Item range
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::AWBROIRangeUpdate()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    GX_INT_RANGE stIntRange;

    // Get the range of AWBROI width
    emStatus = GXGetIntRange(m_hDevice, GX_INT_AWBROI_WIDTH, &stIntRange);
    GX_VERIFY(emStatus);

    // Storage step of this parameter for input correction
    m_i64AWBWidthInc = stIntRange.nInc;

    // Set Range to UI Items
    ui->AWBROIWidthSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIWidthSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIWidthSlider->setSingleStep(stIntRange.nInc);
    ui->AWBROIWidthSlider->setPageStep(0);
    ui->AWBROIWidthSpin->setSingleStep(stIntRange.nInc);
    ui->AWBROIWidthSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                    .arg(stIntRange.nMin)
                                    .arg(stIntRange.nMax)
                                    .arg(stIntRange.nInc));
    ui->AWBROIWidthSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                      .arg(stIntRange.nMin)
                                      .arg(stIntRange.nMax)
                                      .arg(stIntRange.nInc));

    // Get the range of AWBROI height
    emStatus = GXGetIntRange(m_hDevice, GX_INT_AWBROI_HEIGHT, &stIntRange);
    GX_VERIFY(emStatus);

    // Storage step of this parameter for input correction
    m_i64AWBHeightInc = stIntRange.nInc;

    // Set Range to UI Items
    ui->AWBROIHeightSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIHeightSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIHeightSlider->setSingleStep(stIntRange.nInc);
    ui->AWBROIHeightSlider->setPageStep(0);
    ui->AWBROIHeightSpin->setSingleStep(stIntRange.nInc);
    ui->AWBROIHeightSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                     .arg(stIntRange.nMin)
                                     .arg(stIntRange.nMax)
                                     .arg(stIntRange.nInc));
    ui->AWBROIHeightSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                       .arg(stIntRange.nMin)
                                       .arg(stIntRange.nMax)
                                       .arg(stIntRange.nInc));

    // Get the range of AWBROI offsetx
    emStatus = GXGetIntRange(m_hDevice, GX_INT_AWBROI_OFFSETX, &stIntRange);
    GX_VERIFY(emStatus);

    // Storage step of this parameter for input correction
    m_i64AWBOffsetXInc = stIntRange.nInc;

    // Set Range to UI Items
    ui->AWBROIOffsetXSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIOffsetXSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIOffsetXSlider->setSingleStep(stIntRange.nInc);
    ui->AWBROIOffsetXSlider->setPageStep(0);
    ui->AWBROIOffsetXSpin->setSingleStep(stIntRange.nInc);
    ui->AWBROIOffsetXSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                      .arg(stIntRange.nMin)
                                      .arg(stIntRange.nMax)
                                      .arg(stIntRange.nInc));
    ui->AWBROIOffsetXSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                        .arg(stIntRange.nMin)
                                        .arg(stIntRange.nMax)
                                        .arg(stIntRange.nInc));

    // Get the range of AWBROI offsety
    emStatus = GXGetIntRange(m_hDevice, GX_INT_AWBROI_OFFSETY, &stIntRange);
    GX_VERIFY(emStatus);

    // Storage step of this parameter for input correction
    m_i64AWBOffsetYInc = stIntRange.nInc;

    // Set Range to UI Items
    ui->AWBROIOffsetYSlider->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIOffsetYSpin->setRange(stIntRange.nMin, stIntRange.nMax);
    ui->AWBROIOffsetYSlider->setSingleStep(stIntRange.nInc);
    ui->AWBROIOffsetYSlider->setPageStep(0);
    ui->AWBROIOffsetYSpin->setSingleStep(stIntRange.nInc);
    ui->AWBROIOffsetYSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                      .arg(stIntRange.nMin)
                                      .arg(stIntRange.nMax)
                                      .arg(stIntRange.nInc));
    ui->AWBROIOffsetYSlider->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
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
void CWhiteBalance::GetDialogInitParam(GX_DEV_HANDLE hDeviceHandle)
{
    // Device handle transfered and storaged
    m_hDevice = hDeviceHandle;
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Clear Dialog Items
    ClearUI();

    // Disable all UI items and block signals 
    DisableUI();

    // Init balance ratio selector combobox entrys
    emStatus = InitComboBox(m_hDevice, ui->BalanceRatioSelector, GX_ENUM_BALANCE_RATIO_SELECTOR);
    GX_VERIFY(emStatus);

    // Init white balance auto combobox entrys
    emStatus = InitComboBox(m_hDevice, ui->WhiteBalanceAuto, GX_ENUM_BALANCE_WHITE_AUTO);
    GX_VERIFY(emStatus);

    // If auto mode is on, start a timer to refresh new value and disable value edit manually
    if (ui->WhiteBalanceAuto->itemData(ui->WhiteBalanceAuto->currentIndex()).value<int64_t>() != GX_BALANCE_WHITE_AUTO_OFF)
    {
        // Refresh interval 100ms
        const int nAWBRefreshInterval = 100;
        m_pWhiteBalanceTimer->start(nAWBRefreshInterval);
        ui->BalanceRatioSpin->setEnabled(false);
    }
    else
    {
        m_pWhiteBalanceTimer->stop();
        ui->BalanceRatioSpin->setEnabled(true);
    }

    // Init AWB lamp house combobox entrys
    emStatus = InitComboBox(m_hDevice ,ui->AWBLampHouse, GX_ENUM_AWB_LAMP_HOUSE);
    GX_VERIFY(emStatus);

    // Get balance ratio for current channel
    double  dBalanceRatio = 0;
    emStatus = GXGetFloat(m_hDevice, GX_FLOAT_BALANCE_RATIO, &dBalanceRatio);
    GX_VERIFY(emStatus);

    // Get the range of balance ratio
    GX_FLOAT_RANGE stFloatRange;
    emStatus = GXGetFloatRange(m_hDevice, GX_FLOAT_BALANCE_RATIO, &stFloatRange);
    GX_VERIFY(emStatus);

    // Set Range to UI Items
    ui->BalanceRatioSpin->setRange(stFloatRange.dMin, stFloatRange.dMax);
    ui->BalanceRatioSpin->setDecimals(WHITEBALANCE_DECIMALS);
    ui->BalanceRatioSpin->setSingleStep(WHITEBALANCE_INCREMENT);
    ui->BalanceRatioSpin->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                            .arg(stFloatRange.dMin, 0, 'f', 1)
                                            .arg(stFloatRange.dMax, 0, 'f', 1)
                                            .arg(WHITEBALANCE_INCREMENT));

    // Set value to UI Items
    ui->BalanceRatioSpin->setValue(dBalanceRatio);

    int64_t i64AWBROIWidth   = 0;
    int64_t i64AWBROIHeight  = 0;
    int64_t i64AWBROIOffsetX = 0;
    int64_t i64AWBROIOffsetY = 0;

    int64_t emRegionSendMode = GX_REGION_SEND_SINGLE_ROI_MODE;
    bool bRegionMode = false;
    emStatus = GXIsImplemented(m_hDevice, GX_ENUM_REGION_SEND_MODE, &bRegionMode);
    GX_VERIFY(emStatus);

    if (bRegionMode)
    {
        emStatus = GXGetEnum(m_hDevice, GX_ENUM_REGION_SEND_MODE, &emRegionSendMode);
        GX_VERIFY(emStatus);
    }

    // When camera setting as MultiROI, AWBROI param cannot access
    if (emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE)
    {
        // Get AWBROI width
        emStatus = GXGetInt(m_hDevice, GX_INT_AWBROI_WIDTH, &i64AWBROIWidth);
        GX_VERIFY(emStatus);

        // Get AWBROI height
        emStatus = GXGetInt(m_hDevice, GX_INT_AWBROI_HEIGHT, &i64AWBROIHeight);
        GX_VERIFY(emStatus);

        // Get AWBROI offestX
        emStatus = GXGetInt(m_hDevice, GX_INT_AWBROI_OFFSETX, &i64AWBROIOffsetX);
        GX_VERIFY(emStatus);

        // Get AWBROI offsetY
        emStatus = GXGetInt(m_hDevice, GX_INT_AWBROI_OFFSETY, &i64AWBROIOffsetY);
        GX_VERIFY(emStatus);

        AWBROIRangeUpdate();
    }

    ui->AWBROIWidthSlider->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIWidthSpin->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIHeightSlider->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIHeightSpin->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIOffsetXSlider->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIOffsetXSpin->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIOffsetYSlider->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);
    ui->AWBROIOffsetYSpin->setEnabled(emRegionSendMode != GX_REGION_SEND_MULTI_ROI_MODE);

    // Set value to UI Items
    ui->AWBROIWidthSpin->setValue(i64AWBROIWidth);
    ui->AWBROIWidthSlider->setValue(i64AWBROIWidth);
    ui->AWBROIHeightSpin->setValue(i64AWBROIHeight);
    ui->AWBROIHeightSlider->setValue(i64AWBROIHeight);
    ui->AWBROIOffsetXSpin->setValue(i64AWBROIOffsetX);
    ui->AWBROIOffsetXSlider->setValue(i64AWBROIOffsetX);
    ui->AWBROIOffsetYSpin->setValue(i64AWBROIOffsetY);
    ui->AWBROIOffsetYSlider->setValue(i64AWBROIOffsetY);

    // Enable all UI Items and release signals when initialze success
    EnableUI();

    return;
}

//----------------------------------------------------------------------------------
/**
\ Balance white channel changed slot
\param[in]      nIndex        Balance white channel selected
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_BalanceRatioSelector_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    double dBalanceRatio = 0;

    // Set balance ratio channel
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_BALANCE_RATIO_SELECTOR, ui->BalanceRatioSelector->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    // Get current channel balance ratio
    emStatus = GXGetFloat(m_hDevice, GX_FLOAT_BALANCE_RATIO, &dBalanceRatio);
    GX_VERIFY(emStatus);

    ui->BalanceRatioSpin->setValue(dBalanceRatio);

    return;
}

//----------------------------------------------------------------------------------
/**
\ Balance white ratio of current channel changed slot
\param[in]      dBalanceRatio   BalanceRatio user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_BalanceRatioSpin_valueChanged(double dBalanceRatio)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetFloat(m_hDevice, GX_FLOAT_BALANCE_RATIO, dBalanceRatio);
    GX_VERIFY(emStatus);

    // Balance white setting value always corrected by camera, so get it back to UI Item
    emStatus = GXGetFloat(m_hDevice, GX_FLOAT_BALANCE_RATIO, &dBalanceRatio);
    GX_VERIFY(emStatus);

    ui->BalanceRatioSpin->setValue(dBalanceRatio);

    return;
}
//----------------------------------------------------------------------------------
/**
\ Balance white mode changed slot
\param[in]      nIndex        Balance white mode selected
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_WhiteBalanceAuto_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Set balance mode
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_BALANCE_WHITE_AUTO, ui->WhiteBalanceAuto->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    // If auto mode is on, start a timer to refresh new value and disable value edit manually
    if (ui->WhiteBalanceAuto->itemData(nIndex).value<int64_t>() != GX_BALANCE_WHITE_AUTO_OFF)
    {
        // Refresh interval 100ms
        const int nAWBRefreshInterval = 100;
        m_pWhiteBalanceTimer->start(nAWBRefreshInterval);
        ui->BalanceRatioSpin->setEnabled(false);
        ui->BalanceRatioSpin->blockSignals(true);
    }
    else
    {
        m_pWhiteBalanceTimer->stop();
        ui->BalanceRatioSpin->setEnabled(true);
        ui->BalanceRatioSpin->blockSignals(false);
    }

    return;
}

//----------------------------------------------------------------------------------
/**
\ Update WhiteBalanceRatio mode and value timeout slot
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::WhiteBalanceRatioUpdate()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    int64_t i64Entry = GX_BALANCE_WHITE_AUTO_OFF;

    emStatus = GXGetEnum(m_hDevice, GX_ENUM_BALANCE_WHITE_AUTO, &i64Entry);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        m_pWhiteBalanceTimer->stop();
        GX_VERIFY(emStatus);
    }

    // If auto mode is off, stop the timer and enable value edit manually
    if (i64Entry == GX_BALANCE_WHITE_AUTO_OFF)
    {
        ui->WhiteBalanceAuto->setCurrentIndex(ui->WhiteBalanceAuto->findData(qVariantFromValue(i64Entry)));

        ui->BalanceRatioSpin->setEnabled(true);
        ui->BalanceRatioSpin->blockSignals(false);
        m_pWhiteBalanceTimer->stop();
    }
    else
    {
        ui->BalanceRatioSpin->blockSignals(true);
    }

    double dBalanceRatio = 0;
    emStatus = GXGetFloat(m_hDevice, GX_FLOAT_BALANCE_RATIO, &dBalanceRatio);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        m_pWhiteBalanceTimer->stop();
        GX_VERIFY(emStatus);
    }

    ui->BalanceRatioSpin->setValue(dBalanceRatio);

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBLampHouse nIndex changed slot
\param[in]      nIndex        AWBLampHouse selected
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBLampHouse_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Set AWB lamphouse
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_AWB_LAMP_HOUSE, ui->AWBLampHouse->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIWidth Value changed slot
\param[in]      nAWBROIWidth        Changed value from slider
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIWidthSlider_valueChanged(int nAWBROIWidth)
{
    // Param correction
    nAWBROIWidth = (nAWBROIWidth / m_i64AWBWidthInc) * m_i64AWBWidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_WIDTH, nAWBROIWidth);
    GX_VERIFY(emStatus);

    ui->AWBROIWidthSpin->setValue(nAWBROIWidth);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIWidth Value changed slot
\param[in]      nAWBROIWidth    AWBROIWidth user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIWidthSpin_valueChanged(int nAWBROIWidth)
{
    nAWBROIWidth = (nAWBROIWidth / m_i64AWBWidthInc) * m_i64AWBWidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_WIDTH, nAWBROIWidth);
    GX_VERIFY(emStatus);

    ui->AWBROIWidthSpin->setValue(nAWBROIWidth);
    ui->AWBROIWidthSlider->setValue(nAWBROIWidth);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIHeight Value changed slot
\param[in]      nAWBROIHeight        Changed value from slider
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIHeightSlider_valueChanged(int nAWBROIHeight)
{
    nAWBROIHeight = (nAWBROIHeight / m_i64AWBHeightInc) * m_i64AWBHeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_HEIGHT, nAWBROIHeight);
    GX_VERIFY(emStatus);

    ui->AWBROIHeightSpin->setValue(nAWBROIHeight);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIHeight Value changed slot
\param[in]      nAWBROIHeight   AWBROIHeight user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIHeightSpin_valueChanged(int nAWBROIHeight)
{
    nAWBROIHeight = (nAWBROIHeight / m_i64AWBHeightInc) * m_i64AWBHeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_HEIGHT, nAWBROIHeight);
    GX_VERIFY(emStatus);

    ui->AWBROIHeightSpin->setValue(nAWBROIHeight);
    ui->AWBROIHeightSlider->setValue(nAWBROIHeight);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIOffsetX Value changed slot
\param[in]      nAWBROIOffsetX  Changed value from slider
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIOffsetXSlider_valueChanged(int nAWBROIOffsetX)
{
    nAWBROIOffsetX = (nAWBROIOffsetX / m_i64AWBWidthInc) * m_i64AWBWidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_OFFSETX, nAWBROIOffsetX);
    GX_VERIFY(emStatus);

    ui->AWBROIOffsetXSpin->setValue(nAWBROIOffsetX);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIOffsetX Value changed slot
\param[in]      nAWBROIOffsetX  AWBROIOffsetX user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIOffsetXSpin_valueChanged(int nAWBROIOffsetX)
{
    nAWBROIOffsetX = (nAWBROIOffsetX / m_i64AWBWidthInc) * m_i64AWBWidthInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_OFFSETX, nAWBROIOffsetX);
    GX_VERIFY(emStatus);

    ui->AWBROIOffsetXSpin->setValue(nAWBROIOffsetX);
    ui->AWBROIOffsetXSlider->setValue(nAWBROIOffsetX);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIOffsetY Value changed slot
\param[in]      nAWBROIOffsetY  Changed value from slider
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIOffsetYSlider_valueChanged(int nAWBROIOffsetY)
{
    nAWBROIOffsetY = (nAWBROIOffsetY / m_i64AWBHeightInc) * m_i64AWBHeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_OFFSETY, nAWBROIOffsetY);
    GX_VERIFY(emStatus);

    ui->AWBROIOffsetYSpin->setValue(nAWBROIOffsetY);

    AWBROIRangeUpdate();

    return;
}

//----------------------------------------------------------------------------------
/**
\ AWBROIOffsetY Value changed slot
\param[in]      nAWBROIOffsetY  AWBROIOffsetY user input
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CWhiteBalance::on_AWBROIOffsetYSpin_valueChanged(int nAWBROIOffsetY)
{
    nAWBROIOffsetY = (nAWBROIOffsetY / m_i64AWBHeightInc) * m_i64AWBHeightInc;

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetInt(m_hDevice, GX_INT_AWBROI_OFFSETY, nAWBROIOffsetY);
    GX_VERIFY(emStatus);

    ui->AWBROIOffsetYSpin->setValue(nAWBROIOffsetY);
    ui->AWBROIOffsetYSlider->setValue(nAWBROIOffsetY);

    AWBROIRangeUpdate();

    return;
}

//--------------------------------------------------------------------------------
/**
\file     FrameRateControl.cpp
\brief    CFrameRateControl Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "FrameRateControl.h"
#include "ui_FrameRateControl.h"

//----------------------------------------------------------------------------------
/**
\Constructor of CFrameRateControl
*/
//----------------------------------------------------------------------------------
CFrameRateControl::CFrameRateControl(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::CFrameRateControl),
    m_hDevice(NULL),
    m_dFrameRate(0.0)
{
    ui->setupUi(this);

    QFont font = this->font();
    font.setPointSize(10);
    this->setFont(font);

    //This property holds the way the widget accepts keyboard focus.
    //Avoid other focus policy which will exit this dialog by every time pressing "Enter"
    ui->FrameRateControl_Close->setFocusPolicy(Qt::NoFocus);

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
\Destructor of CFrameRateControl
*/
//----------------------------------------------------------------------------------
CFrameRateControl::~CFrameRateControl()
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
void CFrameRateControl::on_FrameRateControl_Close_clicked()
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
void CFrameRateControl::ClearUI()
{
    // Clear ComboBox items
    ui->AcquisitionFrameRateMode->clear();

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
void CFrameRateControl::EnableUI()
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

    ui->FrameRate_Control->setEnabled(true);

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
void CFrameRateControl::DisableUI()
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

    ui->FrameRate_Control->setEnabled(false);

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
void CFrameRateControl::GetDialogInitParam(GX_DEV_HANDLE hDeviceHandle)
{
    // Device handle transfered and storaged
    m_hDevice = hDeviceHandle;

    ClearUI();

    // Disable all UI items and block signals
    DisableUI();

    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    GX_FLOAT_RANGE stFloatRange;
    double dFrameRate = 0.0;

    // Init framerate mode combobox entrys
    emStatus = InitComboBox(m_hDevice, ui->AcquisitionFrameRateMode, GX_ENUM_ACQUISITION_FRAME_RATE_MODE);
    GX_VERIFY(emStatus);

    if (ui->AcquisitionFrameRateMode->itemData(ui->AcquisitionFrameRateMode->currentIndex()).value<int64_t>()
            == GX_ACQUISITION_FRAME_RATE_MODE_ON)
    {
        ui->AcquisitionFrameRateSpinBox->setEnabled(true);
    }
    else
    {
        ui->AcquisitionFrameRateSpinBox->setEnabled(false);
    }

    // Get frame rate
    emStatus = GXGetFloat(m_hDevice, GX_FLOAT_ACQUISITION_FRAME_RATE, &dFrameRate);
    GX_VERIFY(emStatus);

    // Get range from device
    emStatus = GXGetFloatRange(m_hDevice, GX_FLOAT_ACQUISITION_FRAME_RATE, &stFloatRange);
    GX_VERIFY(emStatus);

    // Set range to UI item
    ui->AcquisitionFrameRateSpinBox->setRange(stFloatRange.dMin, stFloatRange.dMax);
    ui->AcquisitionFrameRateSpinBox->setSingleStep(FRAMERATE_INCREMENT);
    ui->AcquisitionFrameRateSpinBox->setToolTip(QString("(Min:%1 Max:%2 Inc:%3)")
                                            .arg(stFloatRange.dMin, 0, 'f', 1)
                                            .arg(stFloatRange.dMax, 0, 'f', 1)
                                            .arg(FRAMERATE_INCREMENT));

    // Set value to UI item
    ui->AcquisitionFrameRateSpinBox->setValue(dFrameRate);

    // Enable all UI Items and release signals when initialze success
    EnableUI();

    return;
}

//----------------------------------------------------------------------------------
/**
\change AcquisitionFrameRateMode slot
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CFrameRateControl::on_AcquisitionFrameRateMode_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // set trigger Mode
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_ACQUISITION_FRAME_RATE_MODE,
                         ui->AcquisitionFrameRateMode->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    ui->AcquisitionFrameRateSpinBox->setEnabled(
                ui->AcquisitionFrameRateMode->itemData(nIndex).value<int64_t>() == GX_ACQUISITION_FRAME_RATE_MODE_ON);

    return;
}

//----------------------------------------------------------------------------------
/**
\change the value of frame rate spinbox slot
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CFrameRateControl::on_AcquisitionFrameRateSpinBox_valueChanged(double dAcquisitionFrameRate)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    emStatus = GXSetFloat(m_hDevice, GX_FLOAT_ACQUISITION_FRAME_RATE, dAcquisitionFrameRate);
    GX_VERIFY(emStatus);

    return;
}


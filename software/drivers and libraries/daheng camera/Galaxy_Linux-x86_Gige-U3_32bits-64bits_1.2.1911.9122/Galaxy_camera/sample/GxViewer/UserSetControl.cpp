//--------------------------------------------------------------------------------
/**
\file     UserSetControl.cpp
\brief    CUserSetControl Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "UserSetControl.h"
#include "ui_UserSetControl.h"

//----------------------------------------------------------------------------------
/**
\Constructor of CUserSetControl
*/
//----------------------------------------------------------------------------------
CUserSetControl::CUserSetControl(QWidget *parent) :
    QDialog(parent),
    ui(new Ui::CUserSetControl),
    m_hDevice(NULL)
{
    ui->setupUi(this);

    QFont font = this->font();
    font.setPointSize(10);
    this->setFont(font);

    //Avoid focus policy which will exit this dialog by pressing "Enter"
    ui->UserSet_Close->setFocusPolicy(Qt::NoFocus);

    // Close when Mainwindow is closed
    this->setAttribute(Qt::WA_QuitOnClose, false);
}

//----------------------------------------------------------------------------------
/**
\Destructor of CUserSetControl
*/
//----------------------------------------------------------------------------------
CUserSetControl::~CUserSetControl()
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
void CUserSetControl::on_UserSet_Close_clicked()
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
void CUserSetControl::ClearUI()
{
    // Clear ComboBox
    ui->UserSetSelector->clear();
    ui->UserSetDefault->clear();

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
void CUserSetControl::EnableUI()
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

    ui->UserSetControl->setEnabled(true);

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
void CUserSetControl::DisableUI()
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

    ui->UserSetControl->setEnabled(false);

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
void CUserSetControl::GetDialogInitParam(GX_DEV_HANDLE hDeviceHandle)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    m_hDevice = hDeviceHandle;

    ClearUI();

    // Disable all UI items and block signals
    DisableUI();

    // Init user set selector combobox entrys
    emStatus = InitComboBox(m_hDevice, ui->UserSetSelector, GX_ENUM_USER_SET_SELECTOR);
    GX_VERIFY(emStatus);

    if (ui->UserSetSelector->itemData(ui->UserSetSelector->currentIndex()).value<int64_t>() != GX_ENUM_USER_SET_SELECTOR_DEFAULT)
    {
        ui->UserSetSave->setEnabled(true);
    }
    else
    {
        ui->UserSetSave->setEnabled(false);
    }

    // Init user set default combobox entrys
    emStatus = InitComboBox(m_hDevice, ui->UserSetDefault, GX_ENUM_USER_SET_DEFAULT);
    GX_VERIFY(emStatus);
    // Enable all UI Items and release signals when initialze success
    EnableUI();

    return;
}

//----------------------------------------------------------------------------------
/**
\ User set selector combobox activated slot
\param[in]      nIndex  ComboBox selected
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CUserSetControl::on_UserSetSelector_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Set choosen item to camera
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_USER_SET_SELECTOR, ui->UserSetSelector->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    // Default UserSet is unchangable, so disable UserSetSave when choosing Default setting
    if (ui->UserSetSelector->itemData(nIndex).value<int64_t>() != GX_ENUM_USER_SET_SELECTOR_DEFAULT)
    {
        ui->UserSetSave->setEnabled(true);
    }
    else
    {
        ui->UserSetSave->setEnabled(false);
    }

    return;
}

//----------------------------------------------------------------------------------
/**
\ Userset load clicked slot
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CUserSetControl::on_UserSetLoad_clicked()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Load choosen userset paramters to camera
    emStatus = GXSendCommand(m_hDevice, GX_COMMAND_USER_SET_LOAD);
    GX_VERIFY(emStatus);

    // Refresh main window when execute userset load
    emit SigRefreshMainWindow();

    return;
}

//----------------------------------------------------------------------------------
/**
\ Userset save clicked slot
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CUserSetControl::on_UserSetSave_clicked()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Save current camera parameters to user set
    emStatus = GXSendCommand(m_hDevice, GX_COMMAND_USER_SET_SAVE);
    GX_VERIFY(emStatus);

    return;
}

//----------------------------------------------------------------------------------
/**
\ User set selector combobox activated slot
\param[in]      nIndex  ComboBox selected
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CUserSetControl::on_UserSetDefault_activated(int nIndex)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Sets the configuration setting to be used as the default startup setting
    emStatus = GXSetEnum(m_hDevice, GX_ENUM_USER_SET_DEFAULT, ui->UserSetDefault->itemData(nIndex).value<int64_t>());
    GX_VERIFY(emStatus);

    return;
}


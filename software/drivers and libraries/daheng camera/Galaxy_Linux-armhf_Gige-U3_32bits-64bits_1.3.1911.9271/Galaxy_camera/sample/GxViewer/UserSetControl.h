//--------------------------------------------------------------------------------
/**
\file     CUserSetControl.h
\brief    CUserSetControl Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef USERSETCONTROL_H
#define USERSETCONTROL_H

#include "Common.h"

namespace Ui {
    class CUserSetControl;
}

class CUserSetControl : public QDialog
{
    Q_OBJECT

public:
    explicit CUserSetControl(QWidget *parent = 0);
    ~CUserSetControl();
    /// Get device handle from mainwindow, and get param for this dialog
    void GetDialogInitParam(GX_DEV_HANDLE);

private:
    /// Clear Mainwindow items
    void ClearUI();

    /// Enable all UI Groups
    void EnableUI();

    /// Disable all UI Groups
    void DisableUI();

    Ui::CUserSetControl *ui;

    GX_DEV_HANDLE       m_hDevice;          ///< Device Handle

signals:
    void SigRefreshMainWindow();

private slots:
    /// Click for quit this dialog
    void on_UserSet_Close_clicked();

    void on_UserSetLoad_clicked();

    void on_UserSetSave_clicked();

    void on_UserSetDefault_activated(int);

    void on_UserSetSelector_activated(int);
};

#endif // USERSETCONTROL_H

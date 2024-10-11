#include "stdafx.h"
#include "demomfc.h"
#include "demomfcDlg.h"

BEGIN_MESSAGE_MAP(CdemomfcApp, CWinApp)
END_MESSAGE_MAP()

CdemomfcApp::CdemomfcApp()
{
}

CdemomfcApp theApp;

BOOL CdemomfcApp::InitInstance()
{
	INITCOMMONCONTROLSEX InitCtrls;
	InitCtrls.dwSize = sizeof(InitCtrls);
	InitCtrls.dwICC = ICC_WIN95_CLASSES;
	InitCommonControlsEx(&InitCtrls);

	CWinApp::InitInstance();
	AfxOleInit();

	SetRegistryKey(_T("demomfc"));

	CdemomfcDlg dlg;
	m_pMainWnd = &dlg;
	dlg.DoModal();

	return FALSE;
}


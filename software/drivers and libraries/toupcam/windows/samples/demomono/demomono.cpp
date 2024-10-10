#include "stdafx.h"
#include "demomono.h"
#include "demomonoDlg.h"

BEGIN_MESSAGE_MAP(CdemomonoApp, CWinApp)
END_MESSAGE_MAP()

CdemomonoApp::CdemomonoApp()
{
}

CdemomonoApp theApp;

BOOL CdemomonoApp::InitInstance()
{
	INITCOMMONCONTROLSEX InitCtrls;
	InitCtrls.dwSize = sizeof(InitCtrls);
	InitCtrls.dwICC = ICC_WIN95_CLASSES;
	InitCommonControlsEx(&InitCtrls);

	CWinApp::InitInstance();
	AfxOleInit();

	SetRegistryKey(_T("demomono"));

	CdemomonoDlg dlg;
	m_pMainWnd = &dlg;
	dlg.DoModal();

	return FALSE;
}


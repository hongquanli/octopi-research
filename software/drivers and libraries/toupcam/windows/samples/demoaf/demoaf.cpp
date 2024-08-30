#include "stdafx.h"
#include "demoaf.h"
#include "demoafDlg.h"

BEGIN_MESSAGE_MAP(CdemoafApp, CWinApp)
END_MESSAGE_MAP()

CdemoafApp theApp;

BOOL CdemoafApp::InitInstance()
{
	INITCOMMONCONTROLSEX InitCtrls;
	InitCtrls.dwSize = sizeof(InitCtrls);
	InitCtrls.dwICC = ICC_WIN95_CLASSES;
	InitCommonControlsEx(&InitCtrls);

	CWinApp::InitInstance();
	AfxOleInit();

	SetRegistryKey(_T("demoaf"));

	CdemoafDlg dlg;
	m_pMainWnd = &dlg;
	dlg.DoModal();

	return FALSE;
}

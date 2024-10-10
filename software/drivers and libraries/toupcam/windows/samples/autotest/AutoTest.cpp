#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "AutoTestDlg.h"

BEGIN_MESSAGE_MAP(CAutoTestApp, CWinApp)
END_MESSAGE_MAP()

CAutoTestApp::CAutoTestApp()
{
}

CAutoTestApp theApp;

BOOL CAutoTestApp::InitInstance()
{
	// InitCommonControlsEx() is required on Windows XP if an application
	// manifest specifies use of ComCtl32.dll version 6 or later to enable
	// visual styles.  Otherwise, any window creation will fail.
	INITCOMMONCONTROLSEX InitCtrls;
	InitCtrls.dwSize = sizeof(InitCtrls);
	// Set this to include all the common control classes you want to use
	// in your application.
	InitCtrls.dwICC = ICC_WIN95_CLASSES;
	InitCommonControlsEx(&InitCtrls);

	AfxOleInit();
	CWinApp::InitInstance();
	AfxEnableControlContainer();
	
	// Activate "Windows Native" visual manager for enabling themes in MFC controls
	CMFCVisualManager::SetDefaultManager(RUNTIME_CLASS(CMFCVisualManagerWindows));

	// Standard initialization
	// If you are not using these features and wish to reduce the size
	// of your final executable, you should remove from the following
	// the specific initialization routines you do not need
	// Change the registry key under which our settings are stored
	SetRegistryKey(_T("AutoTest"));

	g_NopacketTimeout = GetProfileInt(_T("Options"), _T("NopacketTimeout"), g_NopacketTimeout);
	g_NoframeTimeout = GetProfileInt(_T("Options"), _T("NoframeTimeout"), g_NoframeTimeout);
	g_HeartbeatTimeout = GetProfileInt(_T("Options"), _T("HeartbeatTimeout"), g_HeartbeatTimeout);
	g_bReplug = GetProfileInt(_T("Options"), _T("Replug"), g_bReplug ? 1 : 0) ? true : false;
	g_bEnableCheckBlack = GetProfileInt(_T("Options"), _T("CheckBlack"), g_bCheckBlack ? 1 : 0) ? true : false;
	g_bRealtime = GetProfileInt(_T("Options"), _T("Realtime"), g_bRealtime ? 1 : 0) ? true : false;

	CAutoTestDlg dlg;
	m_pMainWnd = &dlg;
	if (dlg.DoModal() == -1)
	{
		TRACE(traceAppMsg, 0, "Warning: dialog creation failed, so application is terminating unexpectedly.\n");
		TRACE(traceAppMsg, 0, "Warning: if you are using MFC controls on the dialog, you cannot #define _AFX_NO_MFC_CONTROLS_IN_DIALOGS.\n");
	}

#if !defined(_AFXDLL) && !defined(_AFX_NO_MFC_CONTROLS_IN_DIALOGS)
	ControlBarCleanUp();
#endif

	// Since the dialog has been closed, return FALSE so that we exit the
	//  application, rather than start the application's message pump.
	return FALSE;
}
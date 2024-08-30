#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CSnapResTestPropertyPage.h"
#include "AutoTestDlg.h"

CSnapResTestPropertyPage::CSnapResTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_SNAP_RES_TEST)
	, m_resCount(0)
{
}

void CSnapResTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_HINT, str);
}

BEGIN_MESSAGE_MAP(CSnapResTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_SNAP_COUNT, &CSnapResTestPropertyPage::OnEnChangeEditSnapCount)
	ON_BN_CLICKED(IDC_BUTTON_START, &CSnapResTestPropertyPage::OnBnClickedButtonStart)
	ON_WM_TIMER()
END_MESSAGE_MAP()

void CSnapResTestPropertyPage::OnEnChangeEditSnapCount()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_SNAP_COUNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_START)->EnableWindow(m_totalCount > 0);
}

void CSnapResTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	if (!g_bSnapFinish)
		return;
	if (m_count >= m_totalCount)
	{
		Stop();
		AfxMessageBox(_T("Snap and resolution test completed."));
		return;
	}
	if (m_snap == 0)
		g_pMainDlg->SendMessage(WM_USER_PREVIEW_CHANGE, m_resCount);
	g_bSnapFinish = false;
	g_snapCount = m_count;
	Toupcam_Snap(g_hcam, m_snap);
	if (++m_snap >= Toupcam_get_StillResolutionNumber(g_hcam))
	{
		m_snap = 0;
		if (++m_resCount >= Toupcam_get_ResolutionNumber(g_hcam))
		{
			m_resCount = 0;
			++m_count;
			UpdateHint();
		}
	}
}

void CSnapResTestPropertyPage::Stop()
{
	KillTimer(1);
	g_bSnapTest = m_bStart = g_bTesting = false;
	g_bSnapFinish = true;
	m_count = 0;
	UpdateHint();
	SetDlgItemText(IDC_BUTTON_START, _T("Start"));
	GetDlgItem(IDC_EDIT_SNAP_COUNT)->EnableWindow(TRUE);
}

void CSnapResTestPropertyPage::OnBnClickedButtonStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		g_snapDir = GetAppTimeDir(_T("SnapResTest"));
		if (!PathIsDirectory((LPCTSTR)g_snapDir))
			SHCreateDirectory(m_hWnd, (LPCTSTR)g_snapDir);

		g_bSnapTest = g_bSnapFinish = m_bStart = g_bTesting = true;
		g_bCheckBlack = false;
		m_count = m_snap = m_resCount = 0;
		SetDlgItemText(IDC_BUTTON_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_SNAP_COUNT)->EnableWindow(FALSE);
		SetTimer(1, 50, nullptr);
	}
}

BOOL CSnapResTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_START)->EnableWindow(FALSE);

	return TRUE;
}

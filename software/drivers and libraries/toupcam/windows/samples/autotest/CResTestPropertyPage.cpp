#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CResTestPropertyPage.h"
#include "AutoTestDlg.h"

CResTestPropertyPage::CResTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_RESOLUTION_TEST)
	, m_resCount(0)
{
}

void CResTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_RESOLUTION_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(CResTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_RESOLUTION_TEST_COUNT, &CResTestPropertyPage::OnEnChangeEditResolutionTestCount)
	ON_BN_CLICKED(IDC_BUTTON_RESOLUTION_TEST_START, &CResTestPropertyPage::OnBnClickedButtonResolutionTestStart)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL CResTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_RESOLUTION_TEST_START)->EnableWindow(FALSE);

	return TRUE;
}

void CResTestPropertyPage::OnEnChangeEditResolutionTestCount()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_RESOLUTION_TEST_COUNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_RESOLUTION_TEST_START)->EnableWindow(m_totalCount > 0);
}

void CResTestPropertyPage::Stop()
{
	KillTimer(1);
	m_bStart = g_bTesting = false;
	SetDlgItemText(IDC_BUTTON_RESOLUTION_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_RESOLUTION_TEST_COUNT)->EnableWindow(TRUE);
	m_count = 0;
	UpdateHint();
}

void CResTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	if (g_bImageSnap)
		return;
	if ((m_count >= m_totalCount) || g_bBlack)
	{
		Stop();
		AfxMessageBox((m_count >= m_totalCount) ? _T("Resolution test completed.") : _T("Image is completely black."));
		return;
	}

	g_snapCount = m_count;
	if (++m_resCount >= Toupcam_get_ResolutionNumber(g_hcam))
	{
		++m_count;
		UpdateHint();
		m_resCount = 0;
	}
	g_pMainDlg->SendMessage(WM_USER_PREVIEW_CHANGE, m_resCount);
	g_bImageSnap = true;
}

void CResTestPropertyPage::OnBnClickedButtonResolutionTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		g_snapDir = GetAppTimeDir(_T("ResTest"));
		if (!PathIsDirectory((LPCTSTR)g_snapDir))
			SHCreateDirectory(m_hWnd, (LPCTSTR)g_snapDir);

		m_bStart = g_bTesting = true;
		g_bCheckBlack = g_bEnableCheckBlack;
		g_bBlack = false;
		m_resCount = 0;
		SetDlgItemText(IDC_BUTTON_RESOLUTION_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_RESOLUTION_TEST_COUNT)->EnableWindow(FALSE);
		SetTimer(1, 2000, nullptr);
	}
}
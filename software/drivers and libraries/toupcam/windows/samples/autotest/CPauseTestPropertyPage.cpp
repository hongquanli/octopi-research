#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CPauseTestPropertyPage.h"

CPauseTestPropertyPage::CPauseTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_PAUSE_TEST)
	, m_interval(1000)
{
}

void CPauseTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count / 2, m_totalCount);
	SetDlgItemText(IDC_STATIC_PAUSE_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(CPauseTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_PAUSE_TEST_CNT, &CPauseTestPropertyPage::OnEnChangeEditPauseTestCount)
	ON_BN_CLICKED(IDC_BUTTON_PAUSE_TEST_START, &CPauseTestPropertyPage::OnBnClickedButtonPauseTestStart)
	ON_EN_CHANGE(IDC_EDIT_INTERVAL, &CPauseTestPropertyPage::OnEnChangeEditInterval)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL CPauseTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_PAUSE_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
	SetDlgItemInt(IDC_EDIT_PAUSE_TEST_CNT, m_totalCount, FALSE);
	SetDlgItemInt(IDC_EDIT_INTERVAL, m_interval, FALSE);
	return TRUE;
}

void CPauseTestPropertyPage::OnEnChangeEditPauseTestCount()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_PAUSE_TEST_CNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_PAUSE_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
}

void CPauseTestPropertyPage::OnEnChangeEditInterval()
{
	m_interval = GetDlgItemInt(IDC_EDIT_INTERVAL);
	GetDlgItem(IDC_BUTTON_PAUSE_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
}

void CPauseTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	++m_count;
	Toupcam_Pause(g_hcam, m_count % 2);
	UpdateHint();
	if (m_count >= m_totalCount * 2)
	{
		Stop();
		AfxMessageBox(_T("Pause test completed."));
	}
}

void CPauseTestPropertyPage::Stop()
{
	Toupcam_Pause(g_hcam, 0);
	m_bStart = g_bTesting = false;
	KillTimer(1);
	SetDlgItemText(IDC_BUTTON_PAUSE_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_PAUSE_TEST_CNT)->EnableWindow(TRUE);
}

void CPauseTestPropertyPage::OnBnClickedButtonPauseTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		m_bStart = g_bTesting = true;
		g_bCheckBlack = false;
		m_count = 0;
		SetDlgItemText(IDC_BUTTON_PAUSE_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_PAUSE_TEST_CNT)->EnableWindow(FALSE);
		SetTimer(1, m_interval, nullptr);
	}
}
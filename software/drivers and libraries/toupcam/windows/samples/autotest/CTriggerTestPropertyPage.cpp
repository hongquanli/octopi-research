#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CTriggerTestPropertyPage.h"
#include "AutoTestDlg.h"

CTriggerTestPropertyPage::CTriggerTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_TRIGGER_TEST)
	, m_interval(1000), m_number(1)
{
}

void CTriggerTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_TRIGGER_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(CTriggerTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_TRIGGER_TEST_TIMES, &CTriggerTestPropertyPage::OnEnChangeEditTriggerTestTimes)
	ON_EN_CHANGE(IDC_EDIT_TRIGGER_TEST_INTERVAL, &CTriggerTestPropertyPage::OnEnChangeEditTriggerTestInterval)
	ON_EN_CHANGE(IDC_EDIT_TRIGGER_TEST_NUMBER, &CTriggerTestPropertyPage::OnEnChangeEditTriggerTestNumber)
	ON_BN_CLICKED(IDC_BUTTON_TRIGGER_TEST_START, &CTriggerTestPropertyPage::OnBnClickedButtonTriggerTestStart)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL CTriggerTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_TRIGGER_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
	SetDlgItemInt(IDC_EDIT_TRIGGER_TEST_TIMES, m_totalCount, FALSE);
	SetDlgItemInt(IDC_EDIT_TRIGGER_TEST_INTERVAL, m_interval, FALSE);
	SetDlgItemInt(IDC_EDIT_TRIGGER_TEST_NUMBER, m_number, FALSE);
	if (g_cur.model && (g_cur.model->flag & TOUPCAM_FLAG_TRIGGER_SINGLE))
		GetDlgItem(IDC_EDIT_TRIGGER_TEST_NUMBER)->EnableWindow(FALSE);

	return TRUE;
}

void CTriggerTestPropertyPage::OnEnChangeEditTriggerTestTimes()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_TRIGGER_TEST_TIMES);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_TRIGGER_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100 && m_number > 0);
}

void CTriggerTestPropertyPage::OnEnChangeEditTriggerTestNumber()
{
	m_number = GetDlgItemInt(IDC_EDIT_TRIGGER_TEST_NUMBER);
	GetDlgItem(IDC_BUTTON_TRIGGER_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100 && m_number > 0);
}

void CTriggerTestPropertyPage::OnEnChangeEditTriggerTestInterval()
{
	m_interval = GetDlgItemInt(IDC_EDIT_TRIGGER_TEST_INTERVAL);
	GetDlgItem(IDC_BUTTON_TRIGGER_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100 && m_number > 0);
}

void CTriggerTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	Toupcam_Trigger(g_hcam, m_number);

	++m_count;
	UpdateHint();
	if (m_count >= m_totalCount)
	{
		Stop();
		AfxMessageBox(_T("Trigger test completed."));
	}
}

void CTriggerTestPropertyPage::Stop()
{
	KillTimer(1);
	m_bStart = g_bTriggerTest = g_bTesting = false;
	SetDlgItemText(IDC_BUTTON_TRIGGER_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_TRIGGER_TEST_TIMES)->EnableWindow(TRUE);
	GetDlgItem(IDC_EDIT_TRIGGER_TEST_INTERVAL)->EnableWindow(TRUE);
	Toupcam_put_Option(g_hcam, TOUPCAM_OPTION_TRIGGER, 0);
}

void CTriggerTestPropertyPage::OnBnClickedButtonTriggerTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		g_snapDir = GetAppTimeDir(_T("TriggerTest"));
		if (!PathIsDirectory((LPCTSTR)g_snapDir))
			SHCreateDirectory(m_hWnd, (LPCTSTR)g_snapDir);

		Toupcam_put_Option(g_hcam, TOUPCAM_OPTION_TRIGGER, 1);
		m_bStart = g_bTriggerTest = g_bTesting = true;
		m_count = 0;
		SetDlgItemText(IDC_BUTTON_TRIGGER_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_TRIGGER_TEST_TIMES)->EnableWindow(FALSE);
		GetDlgItem(IDC_EDIT_TRIGGER_TEST_INTERVAL)->EnableWindow(FALSE);
		SetTimer(1, m_interval, nullptr);
	}
}
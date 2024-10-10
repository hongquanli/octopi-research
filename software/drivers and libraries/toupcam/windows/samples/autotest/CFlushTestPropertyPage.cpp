#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CFlushTestPropertyPage.h"

CFlushTestPropertyPage::CFlushTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_FLUSH_TEST)
	, m_interval(1000)
{
}

void CFlushTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_FLUSH_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(CFlushTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_FLUSH_TEST_CNT, &CFlushTestPropertyPage::OnEnChangeEditFlushTestCount)
	ON_BN_CLICKED(IDC_BUTTON_FLUSH_TEST_START, &CFlushTestPropertyPage::OnBnClickedButtonFlushTestStart)
	ON_EN_CHANGE(IDC_EDIT_INTERVAL, &CFlushTestPropertyPage::OnEnChangeEditInterval)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL CFlushTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	((CComboBox*)GetDlgItem(IDC_COMBO1))->SetCurSel(2);

	UpdateHint();
	GetDlgItem(IDC_BUTTON_FLUSH_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
	SetDlgItemInt(IDC_EDIT_FLUSH_TEST_CNT, m_totalCount, FALSE);
	SetDlgItemInt(IDC_EDIT_INTERVAL, m_interval, FALSE);
	return TRUE;
}

void CFlushTestPropertyPage::OnEnChangeEditFlushTestCount()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_FLUSH_TEST_CNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_FLUSH_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
}

void CFlushTestPropertyPage::OnEnChangeEditInterval()
{
	m_interval = GetDlgItemInt(IDC_EDIT_INTERVAL);
	GetDlgItem(IDC_BUTTON_FLUSH_TEST_START)->EnableWindow(m_totalCount > 0 && m_interval >= 100);
}

void CFlushTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	Toupcam_put_Option(g_hcam, TOUPCAM_OPTION_FLUSH, ((CComboBox*)GetDlgItem(IDC_COMBO1))->GetCurSel() + 1);

	++m_count;
	UpdateHint();
	if (m_count >= m_totalCount)
	{
		Stop();
		AfxMessageBox(_T("Flush test completed."));
	}
}

void CFlushTestPropertyPage::Stop()
{
	m_bStart = g_bTesting = false;
	KillTimer(1);
	SetDlgItemText(IDC_BUTTON_FLUSH_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_FLUSH_TEST_CNT)->EnableWindow(TRUE);
}

void CFlushTestPropertyPage::OnBnClickedButtonFlushTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		m_bStart = g_bTesting = true;
		g_bCheckBlack = false;
		m_count = 0;
		SetDlgItemText(IDC_BUTTON_FLUSH_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_FLUSH_TEST_CNT)->EnableWindow(FALSE);
		SetTimer(1, m_interval, nullptr);
	}
}
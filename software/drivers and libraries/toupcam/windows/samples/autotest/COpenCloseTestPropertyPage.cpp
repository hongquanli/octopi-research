#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "COpenCloseTestPropertyPage.h"
#include "AutoTestDlg.h"

COpenCloseTestPropertyPage::COpenCloseTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_OPEN_CLOSE_TEST)
	, m_initFlag(false)
{
}

void COpenCloseTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_OPEN_CLOSE_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(COpenCloseTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_OPEN_CLOSE_CNT, &COpenCloseTestPropertyPage::OnEnChangeEditOpenCloseCnt)
	ON_BN_CLICKED(IDC_BUTTON_OPEN_CLOSE_TEST_START, &COpenCloseTestPropertyPage::OnBnClickedButtonOpenCloseTestStart)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL COpenCloseTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_OPEN_CLOSE_TEST_START)->EnableWindow(FALSE);

	return TRUE;
}

void COpenCloseTestPropertyPage::OnEnChangeEditOpenCloseCnt()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_OPEN_CLOSE_CNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_OPEN_CLOSE_TEST_START)->EnableWindow(m_totalCount > 0);
}

void COpenCloseTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	if (m_count >= m_totalCount || g_bBlack)
	{
		Stop();
		AfxMessageBox((m_count >= m_totalCount) ? _T("Open/close test completed.") : _T("Image is completely black."));
		return;
	}
	if (m_conModel)
	{
		g_pMainDlg->SendMessage(WM_USER_OPEN_CLOSE);
		g_snapCount = ++m_count;
		m_conModel = false;
		UpdateHint();
	}
	else
	{
		if (!m_initFlag)
			m_initFlag = true;
		else
			g_pMainDlg->SendMessage(WM_USER_OPEN_CLOSE);
		g_bImageSnap = true;
		m_conModel = true;
	}
}

void COpenCloseTestPropertyPage::Stop()
{
	KillTimer(1);
	m_bStart = g_bTesting = false;
	SetDlgItemText(IDC_BUTTON_OPEN_CLOSE_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_OPEN_CLOSE_CNT)->EnableWindow(TRUE);
	m_count = 0;
	UpdateHint();
}

void COpenCloseTestPropertyPage::OnBnClickedButtonOpenCloseTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		g_snapDir = GetAppTimeDir(_T("OpenCloseTest"));
		if (!PathIsDirectory((LPCTSTR)g_snapDir))
			SHCreateDirectory(m_hWnd, (LPCTSTR)g_snapDir);
		m_bStart = g_bTesting = true;
		g_bCheckBlack = g_bEnableCheckBlack;
		m_initFlag = m_conModel = g_bBlack = false;
		m_count = g_snapCount = 0;
		SetDlgItemText(IDC_BUTTON_OPEN_CLOSE_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_OPEN_CLOSE_CNT)->EnableWindow(FALSE);
		SetTimer(1, 2000, nullptr);
	}
}
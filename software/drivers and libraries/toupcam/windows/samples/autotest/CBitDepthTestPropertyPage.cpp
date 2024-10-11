#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CBitDepthTestPropertyPage.h"

CBitDepthTestPropertyPage::CBitDepthTestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_BITDEPTH_TEST)
{
}

void CBitDepthTestPropertyPage::UpdateHint()
{
	CString str;
	str.Format(_T("%d/%d"), m_count, m_totalCount);
	SetDlgItemText(IDC_STATIC_BITDEPTH_TEST_HINT, str);
}

BEGIN_MESSAGE_MAP(CBitDepthTestPropertyPage, CPropertyPage)
	ON_EN_CHANGE(IDC_EDIT_BITDEPTH_TEST_CNT, &CBitDepthTestPropertyPage::OnEnChangeEditBitDepthTestCount)
	ON_BN_CLICKED(IDC_BUTTON_BITDEPTH_TEST_START, &CBitDepthTestPropertyPage::OnBnClickedButtonBitDepthTestStart)
	ON_WM_TIMER()
END_MESSAGE_MAP()

BOOL CBitDepthTestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	UpdateHint();
	GetDlgItem(IDC_BUTTON_BITDEPTH_TEST_START)->EnableWindow(FALSE);
	return TRUE;
}

void CBitDepthTestPropertyPage::OnEnChangeEditBitDepthTestCount()
{
	m_totalCount = GetDlgItemInt(IDC_EDIT_BITDEPTH_TEST_CNT);
	UpdateHint();
	GetDlgItem(IDC_BUTTON_BITDEPTH_TEST_START)->EnableWindow(m_totalCount > 0);
}

void CBitDepthTestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	int bitDepth = 0;
	Toupcam_get_Option(g_hcam, TOUPCAM_OPTION_BITDEPTH, &bitDepth);
	bitDepth = !bitDepth;
	Toupcam_put_Option(g_hcam, TOUPCAM_OPTION_BITDEPTH, bitDepth);

	++m_count;
	UpdateHint();
	if (m_count >= m_totalCount)
	{
		Stop();
		AfxMessageBox(_T("Bitdepth test completed."));
	}
}

void CBitDepthTestPropertyPage::Stop()
{
	m_bStart = g_bTesting = false;
	KillTimer(1);
	SetDlgItemText(IDC_BUTTON_BITDEPTH_TEST_START, _T("Start"));
	GetDlgItem(IDC_EDIT_BITDEPTH_TEST_CNT)->EnableWindow(TRUE);
}

void CBitDepthTestPropertyPage::OnBnClickedButtonBitDepthTestStart()
{
	if (m_bStart)
		Stop();
	else if (OnStart())
	{
		m_bStart = g_bTesting = true;
		g_bCheckBlack = false;
		m_count = 0;
		SetDlgItemText(IDC_BUTTON_BITDEPTH_TEST_START, _T("Stop"));
		GetDlgItem(IDC_EDIT_BITDEPTH_TEST_CNT)->EnableWindow(FALSE);
		SetTimer(1, 1000, nullptr);
	}
}
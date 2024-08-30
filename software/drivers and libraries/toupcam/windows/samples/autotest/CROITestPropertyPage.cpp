#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CROITestPropertyPage.h"

CROITestPropertyPage::CROITestPropertyPage()
	: CTestPropertyPage(IDD_PROPERTY_ROI_TEST)
	, m_invertal(0), m_xWidth(0), m_yHeight(0), m_conModel(false)
{
}

BEGIN_MESSAGE_MAP(CROITestPropertyPage, CPropertyPage)
	ON_BN_CLICKED(IDC_BUTTON_START, &CROITestPropertyPage::OnBnClickedButtonStart)
	ON_EN_CHANGE(IDC_EDIT_INTERVAL, &CROITestPropertyPage::OnEnChangeEditInterval)
	ON_WM_TIMER()
END_MESSAGE_MAP()

void CROITestPropertyPage::Stop()
{
	KillTimer(1);
	g_ROITestCount = 0;
	g_bROITest = g_bROITest_SnapStart = g_bTesting = false;
	
	GetDlgItem(IDC_EDIT_INTERVAL)->EnableWindow(TRUE);
	GetDlgItem(IDC_BUTTON_START)->SetWindowText(_T("Start"));
	((CProgressCtrl*)GetDlgItem(IDC_PROGRESS_ROI_TEST))->SetPos(0);
	Toupcam_put_Roi(g_hcam, 0, 0, 0, 0);
}

void CROITestPropertyPage::OnTimer(UINT_PTR nIDEvent)
{
	if (!g_bROITest_SnapFinish && g_bROITest_SnapStart)
		return;
	if (m_xWidth <= 0)
	{
		Stop();
		AfxMessageBox(_T("ROI test completed."));
		return;
	}
	if (m_conModel)
	{
		g_bROITest_SnapFinish = false;
		g_bROITest_SnapStart = true;
		m_yHeight -= m_invertal;
		if (m_yHeight <= 0)
		{
			int resWidth = 0, resHeight = 0;
			Toupcam_get_Size(g_hcam, &resWidth, &resHeight);
			m_yHeight = resHeight;
			m_xWidth -= m_invertal;
		}
		m_conModel = false;
		((CProgressCtrl*)GetDlgItem(IDC_PROGRESS_ROI_TEST))->SetPos(((CProgressCtrl*)GetDlgItem(IDC_PROGRESS_ROI_TEST))->GetPos() + 1);
	}
	else
	{
		Toupcam_put_Roi(g_hcam, 0, 0, m_xWidth, m_yHeight);
		m_conModel = true;
	}
}

void CROITestPropertyPage::OnBnClickedButtonStart()
{
	if (g_bROITest)
		Stop();
	else if (OnStart())
	{
		g_snapDir = GetAppTimeDir(_T("ROITest"));
		if (!PathIsDirectory((LPCTSTR)g_snapDir))
			SHCreateDirectory(m_hWnd, (LPCTSTR)g_snapDir);

		g_ROITestCount = 0;
		g_bROITest = g_bTesting = true;
		g_bROITest_SnapStart = m_conModel = false;
		GetDlgItem(IDC_BUTTON_START)->SetWindowText(_T("Stop"));
		GetDlgItem(IDC_EDIT_INTERVAL)->EnableWindow(FALSE);
		Toupcam_get_Size(g_hcam, &m_xWidth, &m_yHeight);
		int widthCnt = ceil(m_xWidth / (double)m_invertal);
		int heightCnt = ceil(m_yHeight / (double)m_invertal);
		((CProgressCtrl*)GetDlgItem(IDC_PROGRESS_ROI_TEST))->SetRange(0, widthCnt * heightCnt);
		((CProgressCtrl*)GetDlgItem(IDC_PROGRESS_ROI_TEST))->SetPos(0);
		
		SetTimer(1, 1000, nullptr);
	}
}

BOOL CROITestPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	GetDlgItem(IDC_BUTTON_START)->EnableWindow(FALSE);
	return TRUE;
}

void CROITestPropertyPage::OnEnChangeEditInterval()
{
	m_invertal = GetDlgItemInt(IDC_EDIT_INTERVAL);
	GetDlgItem(IDC_BUTTON_START)->EnableWindow(m_invertal > 0 && (m_invertal % 2 == 0));
}

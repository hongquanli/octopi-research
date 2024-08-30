#include "stdafx.h"
#include "AutoTest.h"
#include "CSettingPropertySheet.h"
#include "CPreviewSnapPropertyPage.h"
#include "CExposureGainPropertyPage.h"
#include "CWhiteBalancePropertyPage.h"
#include "CSamplingPropertyPage.h"
#include "CBitDepthPropertyPage.h"
#include "CFrameRatePropertyPage.h"

CSettingPropertySheet::CSettingPropertySheet(LPCTSTR pszCaption, CWnd* pParentWnd, UINT iSelectPage)
	:CPropertySheet(pszCaption, pParentWnd, iSelectPage)
	, m_pPreviewSnapPropertyPage(new CPreviewSnapPropertyPage())
	, m_pExposureGainPropertyPage(new CExposureGainPropertyPage())
	, m_pWhiteBalancePropertyPage(new CWhiteBalancePropertyPage())
	, m_pSamplingPropertyPage(new CSamplingPropertyPage())
	, m_pBitDepthPropertyPage(new CBitDepthPropertyPage())
	, m_pFrameRatePropertyPage(new CFrameRatePropertyPage())
{
	m_psh.dwFlags &= ~PSH_HASHELP;
	m_psh.dwFlags |= PSH_NOAPPLYNOW;
	AddPage(m_pPreviewSnapPropertyPage);
	AddPage(m_pExposureGainPropertyPage);
	AddPage(m_pWhiteBalancePropertyPage);
	AddPage(m_pSamplingPropertyPage);
	AddPage(m_pBitDepthPropertyPage);
	AddPage(m_pFrameRatePropertyPage);
}

CSettingPropertySheet::~CSettingPropertySheet()
{
	delete m_pPreviewSnapPropertyPage;
	delete m_pExposureGainPropertyPage;
	delete m_pWhiteBalancePropertyPage;
	delete m_pSamplingPropertyPage;
	delete m_pBitDepthPropertyPage;
	delete m_pFrameRatePropertyPage;
}

CExposureGainPropertyPage* CSettingPropertySheet::GetExposureGainPropertyPage() const
{
	return m_pExposureGainPropertyPage;
}

CWhiteBalancePropertyPage* CSettingPropertySheet::GetWhiteBalancePropertyPage() const
{
	return m_pWhiteBalancePropertyPage;
}

BEGIN_MESSAGE_MAP(CSettingPropertySheet, CPropertySheet)
END_MESSAGE_MAP()

BOOL CSettingPropertySheet::OnInitDialog()
{
	BOOL bResult = CPropertySheet::OnInitDialog();

	GetDlgItem(IDOK)->ShowWindow(SW_HIDE);
	GetDlgItem(IDCANCEL)->ShowWindow(SW_HIDE);
	return bResult;
}

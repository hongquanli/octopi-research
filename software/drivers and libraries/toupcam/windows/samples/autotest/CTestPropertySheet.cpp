#include "stdafx.h"
#include "AutoTest.h"
#include "CTestPropertySheet.h"
#include "CSnapResTestPropertyPage.h"
#include "CROITestPropertyPage.h"
#include "CResTestPropertyPage.h"
#include "CSnapTestPropertyPage.h"
#include "CBitDepthTestPropertyPage.h"
#include "CFlushTestPropertyPage.h"
#include "CPauseTestPropertyPage.h"
#include "COpenCloseTestPropertyPage.h"
#include "CTriggerTestPropertyPage.h"

CTestPropertySheet::CTestPropertySheet(LPCTSTR pszCaption, CWnd* pParentWnd, UINT iSelectPage)
	: CPropertySheet(pszCaption, pParentWnd, iSelectPage)
	, m_pSnapResTestPropertyPage(new CSnapResTestPropertyPage())
	, m_pROITestPropertyPage(new CROITestPropertyPage())
	, m_pResTestPropertyPage(new CResTestPropertyPage())
	, m_pSnapTestPropertyPage(new CSnapTestPropertyPage())
	, m_pBitDepthTestPropertyPage(new CBitDepthTestPropertyPage())
	, m_pFlushTestPropertyPage(new CFlushTestPropertyPage())
	, m_pPauseTestPropertyPage(new CPauseTestPropertyPage())
	, m_pOpenCloseTestPropertyPage(new COpenCloseTestPropertyPage())
	, m_pTriggerTestPropertyPage(new CTriggerTestPropertyPage())
{
	m_psh.dwFlags &= ~PSH_HASHELP;
	m_psh.dwFlags |= PSH_NOAPPLYNOW;
	AddPage(m_pOpenCloseTestPropertyPage);
	AddPage(m_pBitDepthTestPropertyPage);
	AddPage(m_pFlushTestPropertyPage);
	AddPage(m_pPauseTestPropertyPage);
	AddPage(m_pTriggerTestPropertyPage);
	AddPage(m_pSnapResTestPropertyPage);
	AddPage(m_pSnapTestPropertyPage);
	AddPage(m_pROITestPropertyPage);
	AddPage(m_pResTestPropertyPage);
}

CTestPropertySheet::~CTestPropertySheet()
{
	delete m_pSnapResTestPropertyPage;
	delete m_pROITestPropertyPage;
	delete m_pResTestPropertyPage;
	delete m_pSnapTestPropertyPage;
	delete m_pBitDepthTestPropertyPage;
	delete m_pFlushTestPropertyPage;
	delete m_pPauseTestPropertyPage;
	delete m_pOpenCloseTestPropertyPage;
	delete m_pTriggerTestPropertyPage;
}

BEGIN_MESSAGE_MAP(CTestPropertySheet, CPropertySheet)
END_MESSAGE_MAP()

BOOL CTestPropertySheet::OnInitDialog()
{
	BOOL bResult = CPropertySheet::OnInitDialog();
	GetDlgItem(IDOK)->ShowWindow(SW_HIDE);
	GetDlgItem(IDCANCEL)->ShowWindow(SW_HIDE);
	return bResult;
}

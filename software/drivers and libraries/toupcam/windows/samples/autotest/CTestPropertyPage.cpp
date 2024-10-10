#include "stdafx.h"
#include "global.h"
#include "CTestPropertyPage.h"

CTestPropertyPage::CTestPropertyPage(UINT nIDTemplate)
	: CPropertyPage(nIDTemplate)
	, m_bStart(false), m_totalCount(10000), m_count(0)
{
}

BOOL CTestPropertyPage::OnQueryCancel()
{
	if (g_bTesting)
	{
		AfxMessageBox(_T("Testing is in progress."));
		return FALSE;
	}
	return TRUE;
}

bool CTestPropertyPage::OnStart()
{
	if (g_bTesting)
	{
		AfxMessageBox(_T("Another testing is in progress."));
		return false;
	}
	return true;
}
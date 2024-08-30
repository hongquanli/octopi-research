#pragma once

class CSnapResTestPropertyPage;
class CROITestPropertyPage;
class CResTestPropertyPage;
class CSnapTestPropertyPage;
class CBitDepthTestPropertyPage;
class CFlushTestPropertyPage;
class CPauseTestPropertyPage;
class COpenCloseTestPropertyPage;
class CTriggerTestPropertyPage;

class CTestPropertySheet : public CPropertySheet
{
	CSnapResTestPropertyPage* m_pSnapResTestPropertyPage;
	CROITestPropertyPage* m_pROITestPropertyPage;
	CResTestPropertyPage* m_pResTestPropertyPage;
	CSnapTestPropertyPage* m_pSnapTestPropertyPage;
	CBitDepthTestPropertyPage* m_pBitDepthTestPropertyPage;
	CFlushTestPropertyPage* m_pFlushTestPropertyPage;
	CPauseTestPropertyPage* m_pPauseTestPropertyPage;
	COpenCloseTestPropertyPage* m_pOpenCloseTestPropertyPage;
	CTriggerTestPropertyPage* m_pTriggerTestPropertyPage;
public:
	CTestPropertySheet(LPCTSTR pszCaption, CWnd* pParentWnd = nullptr, UINT iSelectPage = 0);
	virtual ~CTestPropertySheet();

protected:
	DECLARE_MESSAGE_MAP()

public:
	virtual BOOL OnInitDialog();
};

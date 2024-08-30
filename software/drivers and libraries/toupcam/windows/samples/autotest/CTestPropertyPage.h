#pragma once

class CTestPropertyPage : public CPropertyPage
{
protected:
	bool m_bStart;
	int m_totalCount;
	int m_count;

	CTestPropertyPage(UINT nIDTemplate);
	virtual BOOL OnQueryCancel();

	bool OnStart();
};
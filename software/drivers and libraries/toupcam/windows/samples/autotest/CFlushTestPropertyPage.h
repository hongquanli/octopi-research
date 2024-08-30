#pragma once

#include "CTestPropertyPage.h"

class CFlushTestPropertyPage : public CTestPropertyPage
{
	int m_interval;
public:
	CFlushTestPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_FLUSH_TEST };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnEnChangeEditFlushTestCount();
	afx_msg void OnEnChangeEditInterval();
	afx_msg void OnBnClickedButtonFlushTestStart();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	DECLARE_MESSAGE_MAP()
private:
	void UpdateHint();
	void Stop();
};
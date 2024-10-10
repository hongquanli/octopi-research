#pragma once

#include "CTestPropertyPage.h"

class CPauseTestPropertyPage : public CTestPropertyPage
{
	int m_interval;
public:
	CPauseTestPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_PAUSE_TEST };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnEnChangeEditPauseTestCount();
	afx_msg void OnEnChangeEditInterval();
	afx_msg void OnBnClickedButtonPauseTestStart();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	DECLARE_MESSAGE_MAP()
private:
	void UpdateHint();
	void Stop();
};
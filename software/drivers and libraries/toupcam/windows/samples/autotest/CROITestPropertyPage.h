#pragma once

#include "CTestPropertyPage.h"

class CROITestPropertyPage : public CTestPropertyPage
{
	int m_invertal;
	int m_xWidth, m_yHeight;
	bool m_conModel;
public:
	CROITestPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_ROI_TEST };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnBnClickedButtonStart();
	afx_msg void OnEnChangeEditInterval();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	DECLARE_MESSAGE_MAP()
private:
	void Stop();
};

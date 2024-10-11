#pragma once

#include "CTestPropertyPage.h"

class CSnapTestPropertyPage : public CTestPropertyPage
{
	int m_snap;
public:
	CSnapTestPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_SNAP_TEST };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnEnChangeEditSnapCount();
	afx_msg void OnBnClickedButtonStart();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	DECLARE_MESSAGE_MAP()
private:
	void Stop();
	void UpdateHint();
};

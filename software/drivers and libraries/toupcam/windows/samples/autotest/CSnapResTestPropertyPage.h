#pragma once

#include "CTestPropertyPage.h"

class CSnapResTestPropertyPage : public CTestPropertyPage
{
	int m_snap, m_resCount;
public:
	CSnapResTestPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_SNAP_RES_TEST };
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

#pragma once

class CSamplingPropertyPage : public CPropertyPage
{
public:
	CSamplingPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_SAMPLING };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnBnClickedRadioBin();
	afx_msg void OnBnClickedRadioSkip();
	DECLARE_MESSAGE_MAP()
};

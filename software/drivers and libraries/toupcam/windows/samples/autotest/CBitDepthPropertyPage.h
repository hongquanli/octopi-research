#pragma once

class CBitDepthPropertyPage : public CPropertyPage
{
public:
	CBitDepthPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_BITDEPTH };
#endif

protected:
	virtual BOOL OnInitDialog();
	DECLARE_MESSAGE_MAP()
public:
	afx_msg void OnCbnSelchangeComboBitdepth();
};

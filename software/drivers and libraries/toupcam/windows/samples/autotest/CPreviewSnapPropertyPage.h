#pragma once

class CPreviewSnapPropertyPage : public CPropertyPage
{
public:
	CPreviewSnapPropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_PREVIEW_SNAP };
#endif

protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnCbnSelchangeComboPreview();
	afx_msg void OnBnClickedButtonSnap();
	DECLARE_MESSAGE_MAP()
private:
	void UpdateSnapRes();
};

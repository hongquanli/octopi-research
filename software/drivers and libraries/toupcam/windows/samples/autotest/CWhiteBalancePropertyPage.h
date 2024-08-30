#pragma once

class CWhiteBalancePropertyPage : public CPropertyPage
{
public:
	CWhiteBalancePropertyPage();

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_WHITE_BALANCE };
#endif
	
	void OnWhiteBalance();
protected:
	virtual BOOL OnInitDialog();
	afx_msg void OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar);
	afx_msg void OnBnClickedButtonWhiteBalance();
	DECLARE_MESSAGE_MAP()
private:
	void SetTempValue(int value);
	void SetTintValue(int value);
};

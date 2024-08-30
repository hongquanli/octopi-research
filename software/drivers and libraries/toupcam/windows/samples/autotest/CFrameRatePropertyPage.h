#pragma once

class CFrameRatePropertyPage : public CPropertyPage
{
	CSliderCtrl m_FrameRateSlider;
public:
	CFrameRatePropertyPage();
	
#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_PROPERTY_FRAME_RATE };
#endif

protected:
	virtual void DoDataExchange(CDataExchange* pDX);
	virtual BOOL OnInitDialog();
	afx_msg void OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar);
	DECLARE_MESSAGE_MAP()
};

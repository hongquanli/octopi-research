#pragma once
#include "CRectTrackerEx.h"

#define MY_EXPOTUER_TIME_MAX 500000

typedef struct
{
	USHORT usSize_X;
	USHORT usSize_Y;
	USHORT usOffset_X;
	USHORT usOffset_Y;
}FV_ROI_ST;

class CdemoafDlg : public CDialog
{
	HToupcam			m_hcam;
	void*				m_pImageData;
	BITMAPINFOHEADER	m_header;
	CRectTrackerEx*		m_rectTracker;
	
	FV_ROI_ST m_ClarityROI;
	ToupcamLensInfo m_afLensInfo;

	bool m_bLensCal_Update_Done;
	bool m_bLensStatus_Update_Done;
	const char* m_cFNMax_Previous;
	int m_iNearFM;
	int m_iFarFM;

public:
	CdemoafDlg(CWnd* pParent = NULL);

	enum { IDD = IDD_DEMOAF };

private:
	unsigned m_nFrame, m_nTime, m_nTotalFrame;
	double m_dFV, m_dLum;
	CRect m_RClimit;
	CSliderCtrl m_slider_ap;
	CSliderCtrl m_slider_foc;
	CComboBox	m_combo_aperture;
	USHORT m_revision;

protected:
	virtual BOOL OnInitDialog();
	virtual void DoDataExchange(CDataExchange* pDX);
	DECLARE_MESSAGE_MAP()
public:
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();//snap
	afx_msg void OnBnClickedButton3();//White Balance
	afx_msg void OnCbnSelchangeCombo1();//Resolution
	afx_msg void OnBnClickedCheck1();//Auto Exposure
	afx_msg void OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar);
	afx_msg void OnDestroy();
	afx_msg LRESULT OnMsgCamevent(WPARAM wp, LPARAM lp);
	afx_msg void OnLButtonDown(UINT nFlags, CPoint point);
	afx_msg BOOL OnSetCursor(CWnd* pWnd, UINT nHitTest, UINT message);
	afx_msg void OnBnClickedLenscal();
	afx_msg void OnBnClickedFocusmotorup();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	afx_msg void OnBnClickedFocusmotordown();
	afx_msg void OnExitSizeMove();
	afx_msg void OnCbnSelchangeComboF();
	afx_msg void OnBnClickedRadioManual();
	afx_msg void OnBnClickedRadioAuto();
	afx_msg void OnSize(UINT nType, int cx, int cy);
	afx_msg void OnBnClickedButtonOnepush();
	afx_msg void OnEnSetfocusFocusmotorstep();
private:
	void StartAFLensControll();
	void StartDevice();
	void OnEventError();
	void OnEventDisconnected();
	void OnEventImage();
	void OnEventExpo();
	void UpdateExpoSlidersEnable();
	void UpdateExpoValue();
	void UpdateGainValue();
	void OnEventTempTint();
	void OnEventStillImage();
	CRect GetDrawRect();
	void GetAEAuxRect();
	void SetAEAuxRect();
	void SetClarityRect();
	void SetFrameRateLimit();
	void SetLensStatus();
	CRect SetDisplayLimit(CRect rect);
	void AF_FocusDlg_Init();
	void AF_APDlg_Init();
	void SetFocusFNControl(BOOL bControll);
public:
	afx_msg void OnBnClickedButtonSaveStatus();
	afx_msg void OnBnClickedButtonLoadStatus();
};

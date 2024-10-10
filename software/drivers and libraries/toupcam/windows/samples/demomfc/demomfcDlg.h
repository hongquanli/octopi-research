#pragma once

class CRectTrackerEx : public CRectTracker
{
    CRect m_rectLimit;
public:
    CRectTrackerEx();
    void SetRectLimit(CRect rect);
private:
    virtual void OnChangedRect(const CRect& rectOld);
};

class CdemomfcDlg : public CDialog
{
	HToupcam			m_hcam;
	void*				m_pImageData;
	BITMAPINFOHEADER	m_header;
	CRectTrackerEx*		m_rectTracker;
public:
	CdemomfcDlg(CWnd* pParent = NULL);

	enum { IDD = IDD_DEMOMFC };

protected:
	virtual BOOL OnInitDialog();
	DECLARE_MESSAGE_MAP()
public:
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();
	afx_msg void OnBnClickedButton3();
	afx_msg void OnCbnSelchangeCombo1();
	afx_msg void OnSnapResolution(UINT nID);
	afx_msg void OnBnClickedCheck1();
	afx_msg void OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar);
	afx_msg void OnDestroy();
	afx_msg LRESULT OnMsgCamevent(WPARAM wp, LPARAM lp);
	afx_msg void OnLButtonDown(UINT nFlags, CPoint point);
	afx_msg BOOL OnSetCursor(CWnd* pWnd, UINT nHitTest, UINT message);
private:
	void StartDevice();
	void OnEventError();
	void OnEventDisconnected();
	void OnEventImage();
	void OnEventExpo();
	void OnEventTempTint();
	void OnEventStillImage();
	CRect GetDrawRect();
	void GetAEAuxRect();
	void SetAEAuxRect();
};

#pragma once

class CdemomonoDlg : public CDialog
{
	HToupcam	m_hcam;
	PBYTE		m_pImageData;
	PBYTE		m_pDisplayData;
	int			m_maxBitDepth;
	bool		m_bBitDepth;
public:
	CdemomonoDlg(CWnd* pParent = NULL);

	enum { IDD = IDD_DEMOMONO };
protected:
	virtual BOOL OnInitDialog();
	DECLARE_MESSAGE_MAP()
public:
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();
	afx_msg void OnCbnSelchangeCombo1();
	afx_msg void OnSnapResolution(UINT nID);
	afx_msg void OnBnClickedCheck1();
	afx_msg void OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar);
	afx_msg void OnDestroy();
	afx_msg LRESULT OnMsgCamevent(WPARAM wp, LPARAM lp);
private:
	void StartDevice();
	void OnEventError();
	void OnEventDisconnected();
	void OnEventImage();
	void OnEventStillImage();
	void OnEventExpo();
};

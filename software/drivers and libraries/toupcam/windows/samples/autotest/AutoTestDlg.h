#pragma once

class CSettingPropertySheet;
class CAutoTestDlg : public CDialog
{
	CComboBox m_camList;
	DWORD m_dwHeartbeat;
	BITMAPINFOHEADER m_header;
	void* m_pImageData;
	CSettingPropertySheet* m_pSettingPropertySheet;
public:
	CAutoTestDlg(CWnd* pParent = nullptr);

#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_AUTOTEST_DIALOG };
#endif

protected:
	virtual BOOL OnInitDialog();
	virtual void DoDataExchange(CDataExchange* pDX);
	afx_msg BOOL OnDeviceChange(UINT nEventType, DWORD_PTR dwData);
	afx_msg LRESULT OnMsgCamevent(WPARAM wp, LPARAM lp);
	afx_msg LRESULT OnPreviewResChanged(WPARAM wp, LPARAM lp);
	afx_msg LRESULT OnCloseOpen(WPARAM wp, LPARAM lp);
	afx_msg void OnBnClickedButtonStart();
	afx_msg void OnClose();
	afx_msg void OnBnClickedButtonSetting();
	afx_msg void OnBnClickedButtonTest();
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedOptions();
	afx_msg void OnTimer(UINT_PTR nIDEvent);
	afx_msg LRESULT OnMsgGigehotplug(WPARAM, LPARAM);
	DECLARE_MESSAGE_MAP()
private:
	void EnumCamera();
	void UpdateButtonsState();
	void StartCamera();
	void CloseCamera();
	void OnEventError();
	void OnEventImage();
	void OnEventExpo();
	void OnEventTempTint();
	void OnEventStillImage();
	void UpdateInfo();
};

extern CAutoTestDlg* g_pMainDlg;
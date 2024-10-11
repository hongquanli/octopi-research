#pragma once

class CPreviewSnapPropertyPage;
class CExposureGainPropertyPage;
class CWhiteBalancePropertyPage;
class CSamplingPropertyPage;
class CBitDepthPropertyPage;
class CFrameRatePropertyPage;

class CSettingPropertySheet : public CPropertySheet
{
	CPreviewSnapPropertyPage* m_pPreviewSnapPropertyPage;
	CExposureGainPropertyPage* m_pExposureGainPropertyPage;
	CWhiteBalancePropertyPage* m_pWhiteBalancePropertyPage;
	CSamplingPropertyPage* m_pSamplingPropertyPage;
	CBitDepthPropertyPage* m_pBitDepthPropertyPage;
	CFrameRatePropertyPage* m_pFrameRatePropertyPage;
public:
	CSettingPropertySheet(LPCTSTR pszCaption, CWnd* pParentWnd = nullptr, UINT iSelectPage = 0);
	virtual ~CSettingPropertySheet();

	CExposureGainPropertyPage* GetExposureGainPropertyPage() const;
	CWhiteBalancePropertyPage* GetWhiteBalancePropertyPage() const;

protected:
	DECLARE_MESSAGE_MAP()
public:
	virtual BOOL OnInitDialog();
};

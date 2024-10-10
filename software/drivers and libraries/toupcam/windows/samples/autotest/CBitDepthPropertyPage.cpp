#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CBitDepthPropertyPage.h"

CBitDepthPropertyPage::CBitDepthPropertyPage()
	: CPropertyPage(IDD_PROPERTY_BITDEPTH)
{
}

BEGIN_MESSAGE_MAP(CBitDepthPropertyPage, CPropertyPage)
	ON_CBN_SELCHANGE(IDC_COMBO_BITDEPTH, &CBitDepthPropertyPage::OnCbnSelchangeComboBitdepth)
END_MESSAGE_MAP()

BOOL CBitDepthPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	if (g_hcam)
	{
		int nCur = 0;
		int iFormat = -1;
		int cnt = 0;
		CComboBox* pCombox = (CComboBox*)GetDlgItem(IDC_COMBO_BITDEPTH);
		Toupcam_get_PixelFormatSupport(g_hcam, -1, &cnt);
		for (int i = 0; i < cnt; ++i)
		{
			CString str;
			Toupcam_get_PixelFormatSupport(g_hcam, i, &iFormat);
			const char* name = Toupcam_get_PixelFormatName(iFormat);
			str.Format(L"%S", name);
			pCombox->AddString(str);
		}

		for (int i = 0; i < cnt; ++i)
		{
			int val = -1;
			Toupcam_get_Option(g_hcam, TOUPCAM_OPTION_PIXEL_FORMAT, &iFormat);
			Toupcam_get_PixelFormatSupport(g_hcam, i, &val);
			if (val == iFormat)
				nCur = i;
		}
		pCombox->SetCurSel(nCur);
	}
	return TRUE;
}

void CBitDepthPropertyPage::OnCbnSelchangeComboBitdepth()
{
	int iFormat = -1;
	CComboBox* pCombox = (CComboBox*)GetDlgItem(IDC_COMBO_BITDEPTH);
	int idx = pCombox->GetCurSel();
	Toupcam_get_PixelFormatSupport(g_hcam, idx, &iFormat);
	Toupcam_put_Option(g_hcam, TOUPCAM_OPTION_PIXEL_FORMAT, iFormat);
}

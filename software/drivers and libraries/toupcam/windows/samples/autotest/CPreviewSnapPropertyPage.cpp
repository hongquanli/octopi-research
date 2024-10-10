#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CPreviewSnapPropertyPage.h"
#include "AutoTestDlg.h"

CPreviewSnapPropertyPage::CPreviewSnapPropertyPage()
	: CPropertyPage(IDD_PROPERTY_PREVIEW_SNAP)
{
}

void CPreviewSnapPropertyPage::UpdateSnapRes()
{
	if (g_hcam)
	{
		const int resCnt = Toupcam_get_StillResolutionNumber(g_hcam);
		CComboBox* resList = (CComboBox*)GetDlgItem(IDC_COMBO_SNAP);
		int width = 0, height = 0;
		resList->ResetContent();
		if (resCnt <= 0)
		{
			Toupcam_get_Size(g_hcam, &width, &height);
			CString str;
			str.Format(_T("%d x %d"), width, height);
			resList->AddString(str);
			resList->EnableWindow(FALSE);
		}
		else
		{
			for (int i = 0; i < resCnt; ++i)
			{
				Toupcam_get_StillResolution(g_hcam, i, &width, &height);
				CString str;
				str.Format(_T("%d x %d"), width, height);
				resList->AddString(str);
			}
			resList->EnableWindow(TRUE);
		}
		resList->SetCurSel(0);
	}
}

BEGIN_MESSAGE_MAP(CPreviewSnapPropertyPage, CPropertyPage)
	ON_CBN_SELCHANGE(IDC_COMBO_PREVIEW, &CPreviewSnapPropertyPage::OnCbnSelchangeComboPreview)
	ON_BN_CLICKED(IDC_BUTTON_SNAP, &CPreviewSnapPropertyPage::OnBnClickedButtonSnap)
END_MESSAGE_MAP()

BOOL CPreviewSnapPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	if (g_hcam)
	{
		const int resCnt = Toupcam_get_ResolutionNumber(g_hcam);
		CComboBox* previewResList = (CComboBox*)GetDlgItem(IDC_COMBO_PREVIEW);
		int width = 0, height = 0;
		for (int i = 0; i < resCnt; ++i)
		{
			Toupcam_get_Resolution(g_hcam, i, &width, &height);
			CString str;
			str.Format(_T("%d x %d"), width, height);
			previewResList->AddString(str);
		}
		unsigned resIndex = 0;
		Toupcam_get_eSize(g_hcam, &resIndex);
		previewResList->SetCurSel(resIndex);

		UpdateSnapRes();
	}

	return TRUE;
}

void CPreviewSnapPropertyPage::OnCbnSelchangeComboPreview()
{
	CComboBox* previewResList = (CComboBox*)GetDlgItem(IDC_COMBO_PREVIEW);
	if (previewResList)
		g_pMainDlg->PostMessage(WM_USER_PREVIEW_CHANGE, previewResList->GetCurSel());
	UpdateSnapRes();
}

void CPreviewSnapPropertyPage::OnBnClickedButtonSnap()
{
	const int resCnt = Toupcam_get_StillResolutionNumber(g_hcam);
	if (resCnt <= 0)
		Toupcam_Snap(g_hcam, 0xffffffff);
	else
	{
		CComboBox* resList = (CComboBox*)GetDlgItem(IDC_COMBO_SNAP);
		Toupcam_Snap(g_hcam, resList->GetCurSel());
	}
}

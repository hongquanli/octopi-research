#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CWhiteBalancePropertyPage.h"

CWhiteBalancePropertyPage::CWhiteBalancePropertyPage()
	: CPropertyPage(IDD_PROPERTY_WHITE_BALANCE)
{
}

void CWhiteBalancePropertyPage::OnWhiteBalance()
{
	if (GetSafeHwnd())
	{
		int temp = 0, tint = 0;
		Toupcam_get_TempTint(g_hcam, &temp, &tint);
		SetTempValue(temp);
		SetTintValue(tint);
	}
}

void CWhiteBalancePropertyPage::SetTempValue(int value)
{
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->SetPos(value);
	SetDlgItemInt(IDC_STATIC_TEMP, value);
}

void CWhiteBalancePropertyPage::SetTintValue(int value)
{
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->SetPos(value);
	SetDlgItemInt(IDC_STATIC_TINT, value);
}

BEGIN_MESSAGE_MAP(CWhiteBalancePropertyPage, CPropertyPage)
	ON_WM_HSCROLL()
	ON_BN_CLICKED(IDC_BUTTON_WHITE_BALANCE, &CWhiteBalancePropertyPage::OnBnClickedButtonWhiteBalance)
END_MESSAGE_MAP()

BOOL CWhiteBalancePropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->SetRange(TOUPCAM_TEMP_MIN, TOUPCAM_TEMP_MAX);
	SetTempValue(TOUPCAM_TEMP_DEF);
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->SetRange(TOUPCAM_TINT_MIN, TOUPCAM_TINT_MAX);
	SetTintValue(TOUPCAM_TINT_DEF);

	return TRUE;
}

void CWhiteBalancePropertyPage::OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar)
{
	int curTemp = 0, curTint = 0;
	if (pScrollBar == GetDlgItem(IDC_SLIDER_TEMP))
	{
		Toupcam_get_TempTint(g_hcam, &curTemp, &curTint);
		int temp = ((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->GetPos();
		if (temp != curTemp)
		{
			Toupcam_put_TempTint(g_hcam, temp, curTint);
			SetDlgItemInt(IDC_STATIC_TEMP, temp);
		}
	}
	else if (pScrollBar == GetDlgItem(IDC_SLIDER_TINT))
	{
		Toupcam_get_TempTint(g_hcam, &curTemp, &curTint);
		int tint = ((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->GetPos();
		if (tint != curTint)
		{
			Toupcam_put_TempTint(g_hcam, curTemp, tint);
			SetDlgItemInt(IDC_STATIC_TINT, tint);
		}
	}

	CPropertyPage::OnHScroll(nSBCode, nPos, pScrollBar);
}

void CWhiteBalancePropertyPage::OnBnClickedButtonWhiteBalance()
{
	Toupcam_AwbOnce(g_hcam, nullptr, nullptr);
}

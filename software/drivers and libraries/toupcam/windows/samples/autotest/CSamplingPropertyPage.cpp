#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CSamplingPropertyPage.h"

CSamplingPropertyPage::CSamplingPropertyPage()
	: CPropertyPage(IDD_PROPERTY_SAMPLING)
{
}

BEGIN_MESSAGE_MAP(CSamplingPropertyPage, CPropertyPage)
	ON_BN_CLICKED(IDC_RADIO_BIN, &CSamplingPropertyPage::OnBnClickedRadioBin)
	ON_BN_CLICKED(IDC_RADIO_SKIP, &CSamplingPropertyPage::OnBnClickedRadioSkip)
END_MESSAGE_MAP()

BOOL CSamplingPropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	int bSkip;
	if (E_NOTIMPL == Toupcam_get_Mode(g_hcam, &bSkip))
	{
		GetDlgItem(IDC_RADIO_BIN)->EnableWindow(FALSE);
		GetDlgItem(IDC_RADIO_SKIP)->EnableWindow(FALSE);
	}
	else
	{
		((CButton*)GetDlgItem(IDC_RADIO_BIN))->SetCheck(!bSkip);
		((CButton*)GetDlgItem(IDC_RADIO_SKIP))->SetCheck(bSkip);
	}

	return TRUE;
}

void CSamplingPropertyPage::OnBnClickedRadioBin()
{
	Toupcam_put_Mode(g_hcam, FALSE);
}

void CSamplingPropertyPage::OnBnClickedRadioSkip()
{
	Toupcam_put_Mode(g_hcam, TRUE);
}

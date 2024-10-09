#include <windows.h>
#include <atlbase.h>
#include <atlwin.h>
#include <atlapp.h>
CAppModule _Module;
#include <stdio.h>
#include <stdlib.h>
#include <atlctrls.h>
#include <atlframe.h>
#include <atlcrack.h>
#include <atldlgs.h>
#include <atlstr.h>
#include <atltypes.h>
#include <stdlib.h>
#include "toupcam.h"
#include "dpi.h"
#include "graph.h"
#include <stdexcept>
#include "resource.h"

#define MSG_CAMERA			(WM_APP + 1)
#define TIMER_EPSILON		10
#define TIMER_ID			1
#define TIMER_TEMP			2
#define ROW_MIN				1
#define ROW_MAX				20
#define COL_MIN				1
#define COL_MAX				20
#define AREA_MIN			3
#define AREA_MAX			100
#define TEMP_MIN			0
#define TEMP_MAX			3600

CDPI g_dpi;

static unsigned char GetPixelFormatBitDepth(int val) noexcept
{
	static constexpr unsigned char arr[] = { 8, 10, 12, 14, 16, 8, 8, 8, 8, 8, 12, 8, 12, 11, 16, 16, 16, 16, 16 };
	return arr[val];
}

static bool IsSupportGain(HToupcam h)
{
	unsigned short nMin = 0, nMax = 0;
	Toupcam_get_ExpoAGainRange(h, &nMin, &nMax, nullptr);
	return (nMax > nMin);
}

typedef struct {
	UINT	delayTime;
	UINT	expoTime;
	USHORT	expoGain;
} Expo; /* exposure parameter */

static CString FormatExpoTime(DWORD dwExpoTime)
{
	CString str;
	if (0 == dwExpoTime % 1000)
		str.Format(L"%u", dwExpoTime / 1000);
	else if (0 == dwExpoTime % 100)
		str.Format(L"%u.%u", dwExpoTime / 1000, (dwExpoTime % 1000) / 100);
	else if (0 == dwExpoTime % 10)
		str.Format(L"%u.%02u", dwExpoTime / 1000, (dwExpoTime % 1000) / 10);
	else
		str.Format(L"%u.%03u", dwExpoTime / 1000, dwExpoTime % 1000);
	return str;
}

static CString FormatString(const wchar_t* szFormat, ...)
{
	CString str;
	va_list valist;
	va_start(valist, szFormat);
	str.FormatV(szFormat, valist);
	va_end(valist);
	return str;
}

static bool GetDlgInt(CWindow* pDlg, UINT nID, DWORD& val, DWORD minval, DWORD maxval)
{
	BOOL bTrans = FALSE;
	val = pDlg->GetDlgItemInt(nID, &bTrans, FALSE);
	if (!bTrans)
	{
		pDlg->GotoDlgCtrl(pDlg->GetDlgItem(nID));
		AtlMessageBox(pDlg->m_hWnd, L"Format error.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
		return true;
	}
	if ((val < minval) || (val > maxval))
	{
		pDlg->GotoDlgCtrl(pDlg->GetDlgItem(nID));
		AtlMessageBox(pDlg->m_hWnd, (LPCTSTR)FormatString(L"Out of range [%u, %u].", minval, maxval), (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
		return true;
	}

	return false; // everything ok
}

static bool GetDlgDouble(CWindow* pDlg, UINT nID, double& val)
{
	CString str;
	pDlg->GetDlgItemText(nID, str);
	wchar_t* endptr = nullptr;
	val = wcstod((LPCTSTR)str, &endptr);
	if (endptr && (*endptr))
	{
		pDlg->GotoDlgCtrl(pDlg->GetDlgItem(nID));
		AtlMessageBox(pDlg->m_hWnd, L"Format error.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
		return true;
	}

	return false; // everything ok
}

static bool GetExpoTime(CWindow* pDlg, UINT nID, DWORD& expoTime, DWORD minExpoTime, DWORD maxExpoTime)
{
	CString str;
	pDlg->GetDlgItemText(nID, str);
	wchar_t* endptr = nullptr;
	const double d = wcstod((LPCTSTR)str, &endptr);
	if (endptr && (*endptr))
	{
		pDlg->GotoDlgCtrl(pDlg->GetDlgItem(nID));
		AtlMessageBox(pDlg->m_hWnd, L"Format error.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
		return true;
	}
	expoTime = (DWORD)(d * 1000 + 0.5);
	if ((expoTime < minExpoTime) || (expoTime > maxExpoTime))
	{
		pDlg->GotoDlgCtrl(pDlg->GetDlgItem(nID));
		AtlMessageBox(pDlg->m_hWnd, (LPCTSTR)FormatString(L"Out of range [%s, %s].", (LPCTSTR)FormatExpoTime(minExpoTime), (LPCTSTR)FormatExpoTime(maxExpoTime)), (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
		return true;
	}

	return false; // everything ok
}

class CExposureDlg : public CDialogImpl<CExposureDlg>
{
	friend class CConfigDlg;
	const bool m_bSupportGain;
	const unsigned*			m_expoTimeRange;
	const unsigned short*	m_expoGainRange;
	DWORD	m_expoTime, m_expoGain, m_delayTime;
public:
	enum { IDD = IDD_EXPOSURE };
	CExposureDlg(bool bSupportGain, const unsigned* expoTimeRange, const unsigned short* expoGainRange)
	: m_bSupportGain(bSupportGain), m_expoTimeRange(expoTimeRange), m_expoGainRange(expoGainRange), m_expoTime(0), m_expoGain(TOUPCAM_EXPOGAIN_MIN), m_delayTime(0)
	{
	}

	CExposureDlg(bool bSupportGain, const unsigned* expoTimeRange, const unsigned short* expoGainRange, const Expo& expo)
	: m_bSupportGain(bSupportGain), m_expoTimeRange(expoTimeRange), m_expoGainRange(expoGainRange), m_expoTime(expo.expoTime), m_expoGain(expo.expoGain), m_delayTime(expo.delayTime)
	{
	}

	BEGIN_MSG_MAP(CExposureDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		SetDlgItemText(IDC_STATIC1, (LPCTSTR)FormatString(L"Range: [%s, %s]ms", (LPCTSTR)FormatExpoTime(m_expoTimeRange[0]), (LPCTSTR)FormatExpoTime(m_expoTimeRange[1])));
		if (m_expoTime)
			SetDlgItemText(IDC_EDIT1, (LPCTSTR)FormatExpoTime(m_expoTime));
		
		if (m_bSupportGain)
		{
			SetDlgItemText(IDC_STATIC2, (LPCTSTR)FormatString(L"Range: [%hu, %hu]", m_expoGainRange[0], m_expoGainRange[1]));
			SetDlgItemInt(IDC_EDIT2, m_expoGain, FALSE);
		}
		else
		{
			GetDlgItem(IDC_EDIT2).EnableWindow(FALSE);
		}

		SetDlgItemInt(IDC_EDIT3, m_delayTime, FALSE);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if ((m_bSupportGain && GetDlgInt(this, IDC_EDIT2, m_expoGain, m_expoGainRange[0], m_expoGainRange[1]))
			|| GetDlgInt(this, IDC_EDIT3, m_delayTime, 0, UINT_MAX)
			|| GetExpoTime(this, IDC_EDIT1, m_expoTime, m_expoTimeRange[0], m_expoTimeRange[1]))
			return 0;
		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CConfigDlg : public CDialogImpl<CConfigDlg>
{
	friend class CMainFrame;
	const ToupcamModelV2* m_pModel;
	const bool m_bSupportGain;
	HToupcam	m_hcam;
	DWORD		m_area, m_bin, m_temp, m_scale;
	CRegKey		m_regkey;
	unsigned		m_expoTimeRange[2];
	unsigned short	m_expoGainRange[2];
	std::vector<Expo>	m_vecExpo;
	std::vector<POINT>	m_vecPt;
public:
	enum { IDD = IDD_CONFIG };
	CConfigDlg(HToupcam hcam, const ToupcamModelV2* pModel)
		: m_bSupportGain(IsSupportGain(hcam)), m_hcam(hcam), m_pModel(pModel), m_area(5), m_bin(1), m_temp(0), m_scale(0)
	{
		m_regkey.Create(HKEY_CURRENT_USER, L"Software\\democns");
		m_regkey.QueryDWORDValue(L"area", m_area);

		DWORD dwLength = 0;
		m_regkey.QueryBinaryValue(L"expo", nullptr, &dwLength);
		if (dwLength && (dwLength % sizeof(Expo) == 0))
		{
			m_vecExpo.resize(dwLength / sizeof(Expo));
			m_regkey.QueryBinaryValue(L"expo", &m_vecExpo[0], &dwLength);
		}
		
		Toupcam_get_ExpTimeRange(m_hcam, &m_expoTimeRange[0], &m_expoTimeRange[1], nullptr);
		Toupcam_get_ExpoAGainRange(m_hcam, &m_expoGainRange[0], &m_expoGainRange[1], nullptr);
	}

	BEGIN_MSG_MAP(CMainDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnAdd)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnDelete)
		COMMAND_HANDLER(IDC_COMBO6, CBN_SELCHANGE, OnPixelFormat)
		COMMAND_HANDLER(IDC_RADIO1, BN_CLICKED, OnRadio1)
		COMMAND_HANDLER(IDC_RADIO2, BN_CLICKED, OnRadio2)
		COMMAND_HANDLER(IDC_CHECK3, BN_CLICKED, OnCheck3)
		NOTIFY_HANDLER(IDC_LIST1, LVN_ITEMCHANGED, OnLvnItemchanged)
		NOTIFY_HANDLER(IDC_LIST1, NM_DBLCLK, OnNmDblclk)
	END_MSG_MAP()
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		{
			CComboBox box(GetDlgItem(IDC_COMBO1));
			box.AddString(L"Trigger");
			box.AddString(L"Live");
			DWORD dwValue = 0;
			m_regkey.QueryDWORDValue(L"trigger", dwValue);
			box.SetCurSel(dwValue);
		}
		{
			CComboBox box(GetDlgItem(IDC_COMBO2));
			box.AddString(L"Unsaturated Add");
			box.AddString(L"Saturating Add");
			box.AddString(L"Average");
			DWORD dwValue = 0;
			m_regkey.QueryDWORDValue(L"binmethod", dwValue);
			box.SetCurSel(dwValue);
		}
		{
			CComboBox box(GetDlgItem(IDC_COMBO4));
			box.AddString(L"1");
			box.AddString(L"4");
			box.AddString(L"16");
			box.SetCurSel(0);
		}
		if (Toupcam_get_MaxBitDepth(m_hcam) <= 8)
			GetDlgItem(IDC_COMBO4).EnableWindow(FALSE);
		else
		{
			DWORD dwValue = 0;
			m_regkey.QueryDWORDValue(L"pixelformat", dwValue);

			CComboBox box(GetDlgItem(IDC_COMBO6));
			int num = 0, pixelFormat = 0;
			Toupcam_get_PixelFormatSupport(m_hcam, -1, &num);
			for (int i = 0; i < num; ++i)
			{
				if (SUCCEEDED(Toupcam_get_PixelFormatSupport(m_hcam, (char)i, &pixelFormat)))
				{
					box.SetItemData(box.AddString(CA2W(Toupcam_get_PixelFormatName(pixelFormat))), pixelFormat);
					if (dwValue == pixelFormat)
						box.SetCurSel(box.GetCount() - 1);
				}
			}

			if (box.GetCurSel() < 0)
				box.SetCurSel(0);

			m_regkey.QueryDWORDValue(L"scale", m_scale);
			((CComboBox)GetDlgItem(IDC_COMBO4)).SetCurSel(m_scale);

			pixelFormat = (int)(box.GetItemData(box.GetCurSel()));
			GetDlgItem(IDC_COMBO4).EnableWindow(GetPixelFormatBitDepth(pixelFormat) > 8);
		}
		if (E_NOTIMPL == Toupcam_get_Temperature(m_hcam, nullptr)) // support get the temperature of the sensor
			GetDlgItem(IDC_EDIT5).EnableWindow(FALSE);
		else
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN5));
			ctrl.SetRange(TEMP_MIN, TEMP_MAX);
			m_regkey.QueryDWORDValue(L"temp", m_temp);
			SetDlgItemInt(IDC_EDIT5, m_temp, FALSE);
		}
		CheckDlgButton(IDC_RADIO1, 1);
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN1));
			ctrl.SetRange(ROW_MIN, ROW_MAX);
			DWORD row = 10;
			m_regkey.QueryDWORDValue(L"row", row);
			SetDlgItemInt(IDC_EDIT1, row);
		}
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN2));
			ctrl.SetRange(COL_MIN, COL_MAX);
			DWORD col = 10;
			m_regkey.QueryDWORDValue(L"col", col);
			SetDlgItemInt(IDC_EDIT2, col);
		}
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN3));
			ctrl.SetRange(AREA_MIN, AREA_MAX);
			SetDlgItemInt(IDC_EDIT3, m_area);
		}
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN4));
			ctrl.SetRange(1, 8);
			DWORD dwValue = 1;
			m_regkey.QueryDWORDValue(L"binvalue", dwValue);
			SetDlgItemInt(IDC_EDIT4, dwValue);
		}

		{
			CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
			ctrl.SetExtendedListViewStyle(ctrl.GetExtendedListViewStyle() | LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES);
			ctrl.AddColumn(L"Time(ms)", 0);
			ctrl.AddColumn(L"Gain", 1);
			ctrl.AddColumn(L"Delay(ms)", 2);
			CRect rect;
			ctrl.GetClientRect(&rect);
			const int width = rect.Width() - GetSystemMetrics(SM_CXVSCROLL) - 8;
			ctrl.SetColumnWidth(0, width / 3);
			ctrl.SetColumnWidth(1, width / 3);
			ctrl.SetColumnWidth(2, width / 3);
			for (size_t i = 0; i < m_vecExpo.size(); ++i)
			{
				ctrl.AddItem(i, 0, (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime));
				if (m_bSupportGain)
					ctrl.SetItemText(i, 1, (LPCTSTR)FormatString(L"%hu", m_vecExpo[i].expoGain));
				ctrl.SetItemText(i, 2, (LPCTSTR)FormatString(L"%u", m_vecExpo[i].delayTime));
			}
		}

		{
			CComboBox box(GetDlgItem(IDC_COMBO3));
			if (m_pModel->flag & TOUPCAM_FLAG_FAN)
			{
				box.AddString(L"OFF");
				for (unsigned i = 1; i <= m_pModel->maxfanspeed; ++i)
					box.AddString((LPCTSTR)FormatString(L"%u", i));
				DWORD val = 0;
				m_regkey.QueryDWORDValue(L"fan", val);
				if (val > m_pModel->maxfanspeed)
					val = m_pModel->maxfanspeed;
				box.SetCurSel(val);
			}
			else
			{
				box.EnableWindow(FALSE);
			}
		}

		{
			CComboBox box(GetDlgItem(IDC_COMBO5));
			if (m_pModel->flag & (TOUPCAM_FLAG_CG | TOUPCAM_FLAG_CGHDR))
			{
				DWORD val = 0;
				m_regkey.QueryDWORDValue(L"cg", val);
				if (m_pModel->flag & TOUPCAM_FLAG_GHOPTO)
				{
					box.AddString(L"LCG");
					box.AddString(L"MCG");
					box.AddString(L"HCG");
					if (1 == val)
						box.SetCurSel(2);
					else if (2 == val)
						box.SetCurSel(1);
					else
						box.SetCurSel(0);
				}
				else
				{
					DWORD maxval = 1;
					box.AddString(L"LCG");
					box.AddString(L"HCG");
					if (m_pModel->flag & TOUPCAM_FLAG_CGHDR)
					{
						box.AddString(L"HDR");
						maxval = 2;
					}
					if (val > maxval)
						val = maxval;
					box.SetCurSel(val);
				}
			}
			else
			{
				box.EnableWindow(FALSE);
			}
		}

		if (m_pModel->flag & TOUPCAM_FLAG_TEC_ONOFF)
		{
			DWORD val = 0;
			m_regkey.QueryDWORDValue(L"tec", val);
			CheckDlgButton(IDC_CHECK3, val ? 1 : 0);
			val = 0;
			m_regkey.QueryDWORDValue(L"tectarget", val);
			int tectarget = (int)val;
			{
				int range = 0;
				Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TECTARGET_RANGE, &range);
				const short minr = range & 0xffff, maxr = (range >> 16) & 0xffff;
				if (tectarget < minr)
					tectarget = minr;
				else if (tectarget > maxr)
					tectarget = maxr;
			}
			SetDlgItemText(IDC_EDIT7, (LPCTSTR)FormatString(L"%.1f", tectarget / 10.0));
		}
		else
		{
			GetDlgItem(IDC_EDIT7).EnableWindow(FALSE);
			GetDlgItem(IDC_CHECK3).EnableWindow(FALSE);
		}

		if (m_pModel->flag & TOUPCAM_FLAG_HEAT)
		{
			CUpDownCtrl ctrl(GetDlgItem(IDC_SPIN8));
			DWORD heat = 0, maxheat = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_HEAT_MAX, (int*)&maxheat);
			ctrl.SetRange(0, maxheat);
			m_regkey.QueryDWORDValue(L"heat", heat);
			if (heat > maxheat)
				heat = maxheat;
			SetDlgItemInt(IDC_EDIT8, heat, FALSE);
		}
		else
		{
			GetDlgItem(IDC_EDIT8).EnableWindow(FALSE);
		}

		GetDlgItem(IDC_BUTTON2).EnableWindow(FALSE);
		GetDlgItem(IDOK).EnableWindow(!m_vecExpo.empty());

		if (2 == __argc)  /* launch by command line */
			PostMessage(WM_COMMAND, MAKEWPARAM(IDOK, BN_CLICKED), (LPARAM)(HWND)GetDlgItem(IDOK));
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_vecExpo.empty())
			return 0;

		if (m_pModel->flag & TOUPCAM_FLAG_FAN)
		{
			CComboBox box(GetDlgItem(IDC_COMBO3));
			const int c = box.GetCurSel();
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_FAN, c);
			m_regkey.SetDWORDValue(L"fan", c);
		}

		if (m_pModel->flag & TOUPCAM_FLAG_TEC_ONOFF)
		{
			const int bEnable = IsDlgButtonChecked(IDC_CHECK3) ? 1 : 0;
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TEC, bEnable);
			m_regkey.SetDWORDValue(L"tec", bEnable);
			if (bEnable)
			{
				double d = 0.0;
				if (GetDlgDouble(this, IDC_EDIT7, d))
					return 0;
				const int n = (int)(d * 10.0);
				{
					int range = 0;
					Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TECTARGET_RANGE, &range);
					const short minr = range & 0xffff, maxr = (range >> 16) & 0xffff;
					if ((n < minr) || (n > maxr))
					{
						AtlMessageBox(m_hWnd, (LPCTSTR)FormatString(L"Tec target out of range [%.1f, %.1f].", minr / 10.0, maxr / 10.0), (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
						return 0;
					}
				}
				Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TECTARGET, n);
				m_regkey.SetDWORDValue(L"tectarget", (DWORD)n);
			}
		}

		if (m_pModel->flag & TOUPCAM_FLAG_HEAT)
		{
			DWORD heat = 0, maxheat = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_HEAT_MAX, (int*)&maxheat);
			if (GetDlgInt(this, IDC_EDIT8, heat, 0, maxheat))
				return 0;
			
			m_regkey.SetDWORDValue(L"heat", heat);
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_HEAT, heat);
		}

		if (m_pModel->flag & (TOUPCAM_FLAG_CG | TOUPCAM_FLAG_CGHDR))
		{
			CComboBox box(GetDlgItem(IDC_COMBO5));
			int c = box.GetCurSel();
			if (m_pModel->flag & TOUPCAM_FLAG_GHOPTO)
			{
				if (1 == c)
					c = 2;
				else if (2 == c)
					c = 1;
			}
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_CG, c);
			m_regkey.SetDWORDValue(L"cg", c);
		}

		for (size_t i = 0; i < m_vecExpo.size(); ++i)
		{
			if ((m_vecExpo[i].expoTime < m_expoTimeRange[0]) || (m_vecExpo[i].expoTime > m_expoTimeRange[1]))
			{
				AtlMessageBox(m_hWnd, (LPCTSTR)FormatString(L"Exposure time out of range [%s, %s].", (LPCTSTR)FormatExpoTime(m_expoTimeRange[0]), (LPCTSTR)FormatExpoTime(m_expoTimeRange[1])), (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
				return 0;
			}
			if (m_bSupportGain)
			{
				if ((m_vecExpo[i].expoGain < m_expoGainRange[0]) || (m_vecExpo[i].expoGain > m_expoGainRange[1]))
				{
					AtlMessageBox(m_hWnd, (LPCTSTR)FormatString(L"Exposure gain out of range [%hu, %hu].", m_expoGainRange[0], m_expoGainRange[1]), (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
					return 0;
				}
			}
		}
				
		DWORD row = 10, col = 10;
		if (IsDlgButtonChecked(IDC_RADIO1))
		{
			if (GetDlgInt(this, IDC_EDIT1, row, ROW_MIN, ROW_MAX) || GetDlgInt(this, IDC_EDIT2, col, COL_MIN, COL_MAX))
				return 0;
			m_regkey.SetDWORDValue(L"row", row);
			m_regkey.SetDWORDValue(L"col", col);
		}
		else if (m_vecPt.empty())
		{
			AtlMessageBox(m_hWnd, L"Empty csv file.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			return 0;
		}

		if (GetDlgInt(this, IDC_EDIT3, m_area, AREA_MIN, AREA_MAX) || GetDlgInt(this, IDC_EDIT4, m_bin, 1, 8))
			return 0;
		if (m_area % 2 == 0)
		{
			GotoDlgCtrl(GetDlgItem(IDC_EDIT3));
			AtlMessageBox(m_hWnd, L"Area must be odd number.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			return 0;
		}
		if (E_NOTIMPL != Toupcam_get_Temperature(m_hcam, nullptr))
		{
			if (GetDlgInt(this, IDC_EDIT5, m_temp, TEMP_MIN, TEMP_MAX))
				return 0;
			m_regkey.SetDWORDValue(L"temp", m_temp);
		}

		if (m_bin > 1)
		{
			CComboBox box(GetDlgItem(IDC_COMBO2));
			m_regkey.SetDWORDValue(L"binmethod", box.GetCurSel());
			switch (box.GetCurSel())
			{
			case 1:
				break;
			case 2:
				m_bin |= 0x80;
				break;
			default:
				m_bin |= 0x40;
				break;
			}
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_BINNING, m_bin);
		}
		{
			const unsigned r = m_area / 2;
			int width = 0, height = 0;
			Toupcam_get_FinalSize(m_hcam, &width, &height);
			if (IsDlgButtonChecked(IDC_RADIO1))
			{
				m_vecPt.resize(row * col);
				const int divx = width / col, divy = height / row;
				for (int i = 0; i < row; ++i)
				{
					for (int j = 0; j < col; ++j)
					{
						m_vecPt[i * row + j].x = (divx * j * 2 + divx) / 2;
						m_vecPt[i * row + j].y = (divy * i * 2 + divy) / 2;
					}
				}
			}
			for (size_t i = 0; i < m_vecPt.size(); ++i)
			{
				if ((m_vecPt[i].x + r >= width) || (m_vecPt[i].x <= r)
					|| (m_vecPt[i].y + r >= height) || (m_vecPt[i].y <= r))
				{
					AtlMessageBox(m_hWnd, L"Image size overflow.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
					return 0;
				}
			}
		}

		m_regkey.SetDWORDValue(L"area", m_area);
		m_regkey.SetBinaryValue(L"expo", &m_vecExpo[0], sizeof(Expo) * m_vecExpo.size());
		m_regkey.SetDWORDValue(L"binvalue", m_bin);

		if (Toupcam_get_MaxBitDepth(m_hcam) > 8)
		{
			CComboBox box(GetDlgItem(IDC_COMBO6));
			int val = (int)(box.GetItemData(box.GetCurSel()));
			m_regkey.SetDWORDValue(L"pixelformat", val);
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_PIXEL_FORMAT, val);
			if (GetPixelFormatBitDepth(val) > 8)
			{
				m_scale = ((CComboBox)GetDlgItem(IDC_COMBO4)).GetCurSel();
				m_regkey.SetDWORDValue(L"scale", m_scale);
			}
		}
		{
			CComboBox box(GetDlgItem(IDC_COMBO1));
			m_regkey.SetDWORDValue(L"trigger", box.GetCurSel());
			if (0 == box.GetCurSel())
				Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, 1);
		}

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}

	LRESULT OnAdd(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CExposureDlg dlg(m_bSupportGain, m_expoTimeRange, m_expoGainRange);
		if (IDOK == dlg.DoModal())
		{
			const Expo expo = { dlg.m_delayTime, dlg.m_expoTime, dlg.m_expoGain };
			m_vecExpo.push_back(expo);

			CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
			
			ctrl.AddItem(m_vecExpo.size() - 1, 0, (LPCTSTR)FormatExpoTime(expo.expoTime));
			if (m_bSupportGain)
				ctrl.SetItemText(m_vecExpo.size() - 1, 1, (LPCTSTR)FormatString(L"%hu", expo.expoGain));
			ctrl.SetItemText(m_vecExpo.size() - 1, 2, (LPCTSTR)FormatString(L"%u", expo.delayTime));

			GetDlgItem(IDOK).EnableWindow(!m_vecExpo.empty());
		}

		return 0;
	}

	LRESULT OnNmDblclk(int /*idCtrl*/, LPNMHDR pnmh, BOOL& /*bHandled*/)
	{
		NMITEMACTIVATE* pNMITEMACTIVATE = (NMITEMACTIVATE*)pnmh;
		if (pNMITEMACTIVATE->iItem >= 0)
		{
			CExposureDlg dlg(m_bSupportGain, m_expoTimeRange, m_expoGainRange, m_vecExpo[pNMITEMACTIVATE->iItem]);
			if (IDOK == dlg.DoModal())
			{
				ATLASSERT(pNMITEMACTIVATE->iItem < m_vecExpo.size());
				m_vecExpo[pNMITEMACTIVATE->iItem].expoTime = dlg.m_expoTime;
				m_vecExpo[pNMITEMACTIVATE->iItem].expoGain = dlg.m_expoGain;
				m_vecExpo[pNMITEMACTIVATE->iItem].delayTime = dlg.m_delayTime;

				CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
				ctrl.SetItemText(pNMITEMACTIVATE->iItem, 0, (LPCTSTR)FormatExpoTime(dlg.m_expoTime));
				if (m_bSupportGain)
					ctrl.SetItemText(pNMITEMACTIVATE->iItem, 1, (LPCTSTR)FormatString(L"%hu", dlg.m_expoGain));
				ctrl.SetItemText(pNMITEMACTIVATE->iItem, 2, (LPCTSTR)FormatString(L"%u", dlg.m_delayTime));
			}
		}
		return 0;
	}

	LRESULT OnDelete(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		const int idx = ctrl.GetSelectedIndex();
		if (idx >= 0)
		{
			ctrl.DeleteItem(idx);
			m_vecExpo.erase(m_vecExpo.begin() + idx);

			GetDlgItem(IDOK).EnableWindow(!m_vecExpo.empty());
		}
		return 0;
	}

	LRESULT OnLvnItemchanged(int /*idCtrl*/, LPNMHDR /*pnmh*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		GetDlgItem(IDC_BUTTON2).EnableWindow(ctrl.GetSelectedIndex() >= 0);
		return 0;
	}

	LRESULT OnPixelFormat(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CComboBox box(GetDlgItem(IDC_COMBO6));
		int val = (int)(box.GetItemData(box.GetCurSel()));
		GetDlgItem(IDC_COMBO4).EnableWindow(GetPixelFormatBitDepth(val) > 8);
		return 0;
	}

	LRESULT OnCheck3(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		GetDlgItem(IDC_EDIT7).EnableWindow(IsDlgButtonChecked(IDC_CHECK3) ? 1 : 0);
		return 0;
	}

	LRESULT OnRadio1(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		GetDlgItem(IDC_EDIT1).EnableWindow(TRUE);
		GetDlgItem(IDC_EDIT2).EnableWindow(TRUE);
		return 0;
	}

	LRESULT OnRadio2(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		GetDlgItem(IDC_EDIT1).EnableWindow(FALSE);
		GetDlgItem(IDC_EDIT2).EnableWindow(FALSE);

		/*
		CSV file format:
			241^234,258^218,276^201,200^243,...
			287^160,159^254,176^237,194^221,...
			280^136,297^119,135^247,153^231,...
			...
		*/
		CFileDialog dlg(TRUE, _T("csv"), nullptr, OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT, L"CSV Files (*.csv)\0*.csv\0All Files (*.*)\0*.*\0\0", m_hWnd);
		if (IDOK == dlg.DoModal())
		{
			SetDlgItemText(IDC_EDIT6, dlg.m_szFileName);
			FILE* fp = _tfopen(dlg.m_szFileName, L"rt");
			if (nullptr == fp)
				AtlMessageBox(m_hWnd, _T("Failed to open file."));
			else
			{
				bool bok = false;
				char cstr[4096], *t;
				std::vector<POINT> vecPt;
				try {
					POINT pt;
					while (fgets(cstr, _countof(cstr), fp))
					{
						t = strtok(cstr, ", \t\r\n");
						while (t)
						{
							if (2 != sscanf(t, "%u^%u", &pt.x, &pt.y))
								throw std::runtime_error("");
							vecPt.push_back(pt);
							t = strtok(nullptr, ", \t\r\n");
						}
					}
					bok = true;
				}
				catch (const std::runtime_error&) {
				}
				
				fclose(fp);
				if (vecPt.size() && bok)
					m_vecPt.swap(vecPt);
				else
					AtlMessageBox(m_hWnd, _T("Bad file format."));
			}
		}
		return 0;
	}
};

class COffsetDlg : public CDialogImpl<COffsetDlg>
{
	friend class CSettingsDlg;
	int m_val;
public:
	enum { IDD = IDD_OFFSET };
	COffsetDlg(int val)
	: m_val(val)
	{
	}

	BEGIN_MSG_MAP(CMainDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		SetDlgItemInt(IDC_EDIT1, m_val);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		BOOL bTrans = FALSE;
		m_val = GetDlgItemInt(IDC_EDIT1, &bTrans, TRUE);
		if (!bTrans)
		{
			GotoDlgCtrl(GetDlgItem(IDC_EDIT1));
			AtlMessageBox(m_hWnd, L"Format error.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			return true;
		}

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CSettingsDlg : public CDialogImpl<CSettingsDlg>
{
	const std::vector<POINT>& m_vecPt;
	std::vector<BYTE>& m_vecVisible;
	std::vector<int>& m_vecOffset;
public:
	enum { IDD = IDD_SETTINGS };
	CSettingsDlg(const std::vector<POINT>& vecPt, std::vector<BYTE>& vecVisible, std::vector<int>& vecOffset)
	: m_vecPt(vecPt), m_vecVisible(vecVisible), m_vecOffset(vecOffset)
	{
	}

	BEGIN_MSG_MAP(CMainDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnOffset)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnUnselectAll)
		COMMAND_HANDLER(IDC_BUTTON3, BN_CLICKED, OnAutoOffset)
		NOTIFY_HANDLER(IDC_LIST1, LVN_ITEMCHANGED, OnLvnItemchanged)
		NOTIFY_HANDLER(IDC_LIST1, NM_DBLCLK, OnNmDblclk)
	END_MSG_MAP()
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		ctrl.SetExtendedListViewStyle(ctrl.GetExtendedListViewStyle() | LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES | LVS_EX_CHECKBOXES);
		ctrl.AddColumn(L"Zone", 0);
		ctrl.AddColumn(L"Offset", 1);
		CRect rect;
		ctrl.GetClientRect(&rect);
		const int width = rect.Width() - GetSystemMetrics(SM_CXVSCROLL) - 8;
		ctrl.SetColumnWidth(0, width * 2 / 3);
		ctrl.SetColumnWidth(1, width / 3);
		for (int i = 0; i < (int)m_vecPt.size(); ++i)
		{
			ctrl.AddItem(i, 0, (LPCTSTR)FormatString(L"(%d, %d)", m_vecPt[i].x, m_vecPt[i].y));
			ctrl.SetItemText(i, 1, (LPCTSTR)FormatString(L"%d", m_vecOffset[i]));
			ctrl.SetCheckState(i, m_vecVisible[i]);
		}

		OnCheckState();
		GetDlgItem(IDC_BUTTON1).EnableWindow(FALSE);
		return TRUE;
	}

	LRESULT OnUnselectAll(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		for (int i = 0; i < (int)m_vecPt.size(); ++i)
			ctrl.SetCheckState(i, FALSE);
		GetDlgItem(IDOK).EnableWindow(FALSE);
		GetDlgItem(IDC_BUTTON3).EnableWindow(FALSE);
		return 0;
	}

	LRESULT OnOffset(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		OffsetDlg(ctrl.GetSelectedIndex());
		return 0;
	}

	LRESULT OnAutoOffset(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		COffsetDlg dlg(0);
		if (IDOK == dlg.DoModal())
		{
			CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
			for (int i = 0, j = 0; i < (int)m_vecPt.size(); ++i)
			{
				if (ctrl.GetCheckState(i))
				{
					m_vecOffset[i] = dlg.m_val * (j++);
					ctrl.SetItemText(i, 1, (LPCTSTR)FormatString(L"%d", m_vecOffset[i]));
				}
			}
		}
		return 0;
	}

	LRESULT OnNmDblclk(int /*idCtrl*/, LPNMHDR pnmh, BOOL& /*bHandled*/)
	{
		OffsetDlg(((NMITEMACTIVATE*)pnmh)->iItem);
		return 0;
	}

	LRESULT OnLvnItemchanged(int /*idCtrl*/, LPNMHDR /*pnmh*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		GetDlgItem(IDC_BUTTON1).EnableWindow(ctrl.GetSelectedIndex() >= 0);
		OnCheckState();
		return 0;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		for (int i = 0; i < (int)m_vecPt.size(); ++i)
			m_vecVisible[i] = ctrl.GetCheckState(i) ? true : false;

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
private:
	void OffsetDlg(const int idx)
	{
		if (idx >= 0)
		{
			ATLASSERT(idx < m_vecPt.size());
			COffsetDlg dlg(m_vecOffset[idx]);
			if (IDOK == dlg.DoModal())
			{
				m_vecOffset[idx] = dlg.m_val;

				CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
				ctrl.SetItemText(idx, 1, (LPCTSTR)FormatString(L"%d", m_vecOffset[idx]));
			}
		}
	}

	void OnCheckState()
	{
		CListViewCtrl ctrl(GetDlgItem(IDC_LIST1));
		bool bHasSelect = false;
		for (int i = 0; i < (int)m_vecPt.size(); ++i)
		{
			if (ctrl.GetCheckState(i))
			{
				bHasSelect = true;
				break;
			}
		}
		GetDlgItem(IDOK).EnableWindow(bHasSelect);
		GetDlgItem(IDC_BUTTON3).EnableWindow(bHasSelect);
	}
};

class CVideoView : public CWindowImpl<CVideoView>
{
	unsigned char m_nBitDepth, m_header[sizeof(BITMAPINFOHEADER) + sizeof(RGBQUAD) * 256];
	unsigned m_nBayer;
	PBITMAPINFOHEADER m_pInfoHeader;
	PBYTE m_pRgbData;

	BEGIN_MSG_MAP(CVideoView)
		MESSAGE_HANDLER(WM_PAINT, OnWmPaint)
		MESSAGE_HANDLER(WM_ERASEBKGND, OnEraseBkgnd)
	END_MSG_MAP()
	static ATL::CWndClassInfo& GetWndClassInfo()
	{
		static ATL::CWndClassInfo wc =
		{
			{ sizeof(WNDCLASSEX), CS_HREDRAW | CS_VREDRAW, StartWindowProc,
			  0, 0, NULL, NULL, NULL, (HBRUSH)NULL_BRUSH, NULL, NULL, NULL },
			NULL, NULL, IDC_ARROW, TRUE, 0, L""
		};
		return wc;
	}
public:
	CVideoView()
		: m_pRgbData(nullptr), m_nBayer(0), m_nBitDepth(0), m_pInfoHeader((PBITMAPINFOHEADER)m_header)
	{
		memset(m_header, 0, sizeof(m_header));
		m_pInfoHeader->biSize = sizeof(BITMAPINFOHEADER);
		m_pInfoHeader->biBitCount = 8;
		m_pInfoHeader->biPlanes = 1;
		
		RGBQUAD* p = (RGBQUAD*)(m_header + m_pInfoHeader->biSize);
		for (int i = 0; i < 256; ++i)
			p[i].rgbRed = p[i].rgbGreen = p[i].rgbBlue = (BYTE)i;
	}

	virtual ~CVideoView()
	{
		if (m_pRgbData)
		{
			free(m_pRgbData);
			m_pRgbData = nullptr;
		}
	}

	void Init(LONG w, LONG h, unsigned nBayer, unsigned char nBitDepth)
	{
		m_nBayer = nBayer;
		m_nBitDepth = nBitDepth;
		m_pInfoHeader->biWidth = w;
		m_pInfoHeader->biHeight = h;
		m_pInfoHeader->biSizeImage = TDIBWIDTHBYTES(w * m_pInfoHeader->biBitCount) * h;
		if (m_pRgbData)
		{
			free(m_pRgbData);
			m_pRgbData = nullptr;
		}
		m_pRgbData = (PBYTE)malloc(m_pInfoHeader->biSizeImage);
		memset(m_pRgbData, 0, m_pInfoHeader->biSizeImage);
	}

	void SetData(void* pRawData)
	{
		const LONG nWidthLength = TDIBWIDTHBYTES(m_pInfoHeader->biWidth * m_pInfoHeader->biBitCount);
		if (8 == m_nBitDepth)
		{
			for (LONG i = 0; i < m_pInfoHeader->biHeight; ++i)
				memcpy(m_pRgbData + nWidthLength * i, ((PBYTE)pRawData) + m_pInfoHeader->biWidth * i, nWidthLength);
		}
		else
		{
			for (LONG j, i = 0; i < m_pInfoHeader->biHeight; ++i)
			{
				PBYTE pLine = m_pRgbData + nWidthLength * i;
				PUSHORT pSrc = (PUSHORT)(((PBYTE)pRawData) + m_pInfoHeader->biWidth * i * 2);
				for (j = 0; j < m_pInfoHeader->biWidth; ++j)
					pLine[j] = (BYTE)(pSrc[j] >> m_nBitDepth - 8);
			}
		}
		Invalidate(FALSE);
	}
private:
	LRESULT OnEraseBkgnd(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled) { return 1; }
	LRESULT OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
	{
		CPaintDC dc(m_hWnd);

		CRect rc, newrc;
		GetClientRect(&rc);
		if (m_pRgbData)
		{
			const double dx = ((double)rc.Width()) / m_pInfoHeader->biWidth;
			const double dy = ((double)rc.Height()) / m_pInfoHeader->biHeight;
			const double dxy = __min(dx, dy);
			const LONG neww = (LONG)(dxy * m_pInfoHeader->biWidth);
			const LONG newh = (LONG)(dxy * m_pInfoHeader->biHeight);
			if (rc.Width() > neww)
			{
				newrc.SetRect(rc.left, rc.top, (rc.Width() - neww) / 2, rc.bottom);
				dc.FillRect(&newrc, GetSysColor(COLOR_BTNFACE));
				newrc.SetRect(neww + (rc.Width() - neww) / 2, rc.top, rc.right, rc.bottom);
				dc.FillRect(&newrc, GetSysColor(COLOR_BTNFACE));
			}
			if (rc.Height() > newh)
			{
				newrc.SetRect(rc.left, rc.top, rc.right, (rc.Height() - newh) / 2);
				dc.FillRect(&newrc, GetSysColor(COLOR_BTNFACE));
				newrc.SetRect(rc.left, newh + (rc.Height() - newh) / 2, rc.right, rc.bottom);
				dc.FillRect(&newrc, GetSysColor(COLOR_BTNFACE));
			}
			const int m = dc.SetStretchBltMode(COLORONCOLOR);
			StretchDIBits(dc, (rc.Width() - neww) / 2, (rc.Height() - newh) / 2, neww, newh, 0, 0, m_pInfoHeader->biWidth, m_pInfoHeader->biHeight, m_pRgbData, (BITMAPINFO*)m_header, DIB_RGB_COLORS, SRCCOPY);
			dc.SetStretchBltMode(m);
		}
		else
		{
			dc.FillSolidRect(&rc, GetSysColor(COLOR_BTNFACE));
		}

		return 0;
	}
};

class CMainFrame : public CFrameWindowImpl<CMainFrame>, public CUpdateUI<CMainFrame>, public CIdleHandler
{
	const ToupcamModelV2*	m_pModel;
	HToupcam		m_hcam;
	void*			m_pRawData;
	int				m_ymax, m_scale;
	unsigned		m_area, m_bitdepth;
	DWORD			m_tickLast;
	bool			m_bTriggerMode, m_bWantTigger, m_bTemperature, m_bSupportGain;
	CVideoView		m_view;
	CTabCtrl		m_tabCtrl;
	CGraph			m_tempGraph; //temperature
	CGraph*			m_curGraph;
	CWindow*		m_curWnd;
	int				m_idxExpo;
	std::vector<CGraph>	m_vecGraph;
	std::vector<Expo>	m_vecExpo;
	std::vector<POINT>	m_vecPt;
public:
	CMainFrame()
	: m_hcam(nullptr), m_pModel(nullptr), m_pRawData(nullptr), m_curGraph(nullptr), m_curWnd(nullptr), m_idxExpo(-1)
	, m_bTriggerMode(false), m_bWantTigger(false), m_bTemperature(false), m_bSupportGain(true), m_ymax(0), m_bitdepth(0), m_scale(1), m_area(5)
	, m_tempGraph(true)
	{
	}

	BEGIN_MSG_MAP(CMainFrame)
		MSG_WM_CREATE(OnCreate)
		MSG_WM_TIMER(OnTimer)
		MESSAGE_HANDLER(WM_DESTROY, OnWmDestroy)
		MESSAGE_HANDLER(MSG_CAMERA, OnMsgCamera)
		COMMAND_ID_HANDLER(ID_BESTFIT, OnBestfit)
		COMMAND_ID_HANDLER(ID_ZOOMIN_X, OnZoominX)
		COMMAND_ID_HANDLER(ID_ZOOMOUT_X, OnZoomoutX)
		COMMAND_ID_HANDLER(ID_ZOOMIN_Y, OnZoominY)
		COMMAND_ID_HANDLER(ID_ZOOMOUT_Y, OnZoomoutY)
		COMMAND_ID_HANDLER(ID_ZOOM_X_MAX, OnZoomXMax)
		COMMAND_ID_HANDLER(ID_ZOOM_Y_MAX, OnZoomYMax)
		COMMAND_ID_HANDLER(ID_COPY, OnCopy)
		COMMAND_ID_HANDLER(ID_CSV, OnCsv)
		COMMAND_ID_HANDLER(ID_START, OnStart)
		COMMAND_ID_HANDLER(ID_STOP, OnStop)
		COMMAND_ID_HANDLER(ID_SETTINGS, OnSettings)
		COMMAND_ID_HANDLER(ID_OPEN, OnOpen)
		COMMAND_ID_HANDLER(ID_SAVE, OnSave)
		NOTIFY_CODE_HANDLER(TTN_GETDISPINFOW, OnToolTipText)
		NOTIFY_HANDLER(1, TCN_SELCHANGE, OnTcnSelChange)
		CHAIN_MSG_MAP(CUpdateUI<CMainFrame>)
		CHAIN_MSG_MAP(CFrameWindowImpl<CMainFrame>)
	END_MSG_MAP()

	DECLARE_FRAME_WND_CLASS(NULL, IDR_MAIN);

	BEGIN_UPDATE_UI_MAP(CMainFrame)
		UPDATE_ELEMENT(ID_BESTFIT, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOMIN_X, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOMOUT_X, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOMIN_Y, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOMOUT_Y, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOM_X_MAX, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_ZOOM_Y_MAX, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_CSV, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_SETTINGS, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_START, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_STOP, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_OPEN, UPDUI_TOOLBAR)
		UPDATE_ELEMENT(ID_SAVE, UPDUI_TOOLBAR)
	END_UPDATE_UI_MAP()
public:
	virtual BOOL OnIdle()
	{
		UIEnable(ID_START, nullptr == m_hcam);
		UIEnable(ID_STOP, m_hcam ? TRUE : FALSE);
		UIEnable(ID_BESTFIT, m_curGraph && (m_curGraph->dataNum() > 0));
		UIEnable(ID_ZOOMIN_X, m_curGraph && (m_curGraph->CanZoomIn(true)));
		UIEnable(ID_ZOOMOUT_X, m_curGraph && (m_curGraph->CanZoomOut(true)));
		UIEnable(ID_ZOOMIN_Y, m_curGraph && (m_curGraph->CanZoomIn(false)));
		UIEnable(ID_ZOOMOUT_Y, m_curGraph && (m_curGraph->CanZoomOut(false)));
		UIEnable(ID_ZOOM_X_MAX, m_curGraph && (m_curGraph->CanZoomIn(true)));
		UIEnable(ID_ZOOM_Y_MAX, m_curGraph && (m_curGraph->CanZoomIn(false)));
		UIEnable(ID_CSV, m_vecGraph.size() && (m_vecGraph[0].dataNum() > 0));
		UIEnable(ID_OPEN, m_hcam ? FALSE : TRUE);
		UIEnable(ID_SAVE, m_vecGraph.size() && (m_vecGraph[0].dataNum() > 0));
		UIUpdateToolBar();
		return FALSE;
	}

	int OnCreate(LPCREATESTRUCT /*lpCreateStruct*/)
	{
		CreateSimpleToolBar(IDR_TOOLBAR);
		UIAddToolBar(m_hWndToolBar);
		m_hWndClient = m_tabCtrl.Create(m_hWnd, nullptr, nullptr, WS_CHILD | WS_VISIBLE, 0, 1);
		m_tempGraph.Create(m_tabCtrl.m_hWnd, nullptr, nullptr, WS_CHILD);
		m_view.Create(m_tabCtrl.m_hWnd, nullptr, nullptr, WS_CHILD);
		CenterWindow(GetParent());

		CMessageLoop* pLoop = _Module.GetMessageLoop();
		pLoop->AddIdleHandler(this);

		if (2 == __argc)  /* launch by command line */
			PostMessage(WM_COMMAND, ID_START, 0);
		
		SetWindowText(L"Consistency Test");
		return TRUE;
	}

	LRESULT OnWmDestroy(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
	{
		CloseCamera();
		CFrameWindowImpl<CMainFrame>::OnDestroy(uMsg, wParam, lParam, bHandled);
		return 0;
	}

	LRESULT OnToolTipText(int idCtrl, LPNMHDR pnmh, BOOL& /*bHandled*/)
	{
		LPNMTTDISPINFOW pDispInfo = (LPNMTTDISPINFOW)pnmh;
		if (idCtrl && !(pDispInfo->uFlags & TTF_IDISHWND))
		{
			static constexpr struct {
				int id;
				const wchar_t* str;
			} arr[] = {
				{ ID_BESTFIT, L"Best fit" },
				{ ID_ZOOMIN_X, L"X Zoom in" },
				{ ID_ZOOMOUT_X, L"X Zoom out" },
				{ ID_ZOOMIN_Y, L"Y Zoom in" },
				{ ID_ZOOMOUT_Y, L"Y Zoom out" },
				{ ID_ZOOM_X_MAX, L"X Zoom in maximum" },
				{ ID_ZOOM_Y_MAX, L"Y Zoom in maximum" },
				{ ID_COPY, L"Copy to clipboard" },
				{ ID_CSV, L"Export data to csv file" },
				{ ID_START, L"Start" },
				{ ID_STOP, L"Stop" },
				{ ID_SETTINGS, L"Settings" },
				{ ID_OPEN, L"Open file" },
				{ ID_SAVE, L"Save file" }
			};
			for (size_t i = 0; i < _countof(arr); ++i)
			{
				if (idCtrl == arr[i].id)
				{
					wcscpy(pDispInfo->szText, arr[i].str);
					pDispInfo->uFlags |= TTF_DI_SETITEM;
					break;
				}
			}
		}

		return 0;
	}

	LRESULT OnSettings(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_vecGraph.size())
		{
			std::vector<BYTE> vecVisible(m_vecPt.size());
			std::vector<int> vecOffset(m_vecPt.size());
			m_vecGraph[0].Get(vecVisible, vecOffset);
			CSettingsDlg dlg(m_vecPt, vecVisible, vecOffset);
			if (IDOK == dlg.DoModal())
			{
				for (size_t i = 0; i < m_vecGraph.size(); ++i)
					m_vecGraph[i].Set(vecVisible, vecOffset);
			}
		}
		return 0;
	}

	LRESULT OnBestfit(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->Zoom11();
		return 0;
	}

	LRESULT OnZoominX(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomIn(true);
		return 0;
	}

	LRESULT OnZoomoutX(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomOut(true);
		return 0;
	}

	LRESULT OnZoominY(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomIn(false);
		return 0;
	}

	LRESULT OnZoomoutY(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomOut(false);
		return 0;
	}

	LRESULT OnZoomXMax(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomMax(true);
		return 0;
	}

	LRESULT OnZoomYMax(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
			m_curGraph->ZoomMax(false);
		return 0;
	}

	LRESULT OnOpen(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (nullptr == m_hcam)
		{
			CFileDialog dlg(TRUE, _T("cns"), nullptr, OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT, L"CNS Files (*.cns)\0*.cns\0All Files (*.*)\0*.*\0\0", m_hWnd);
			if (IDOK == dlg.DoModal())
			{
				bool bok = false;
				int	ymax, scale;
				unsigned area, bitdepth;
				std::vector<BYTE> vb;
				std::vector<int> voffset, vTemperature;
				std::vector<Expo> vecExpo;
				std::vector<POINT> vecPt;
				std::vector<std::vector<Data>> vv;

				FILE* fp = _tfopen(dlg.m_szFileName, L"rb");
				if (fp)
				{
					try {
						if (!CheckMagic(fp))
							throw std::runtime_error("");

						BYTE bTemperature;
						if (!ReadValue(fp, area) || !ReadValue(fp, bitdepth)
							|| !ReadValue(fp, ymax) || !ReadValue(fp, scale) || !ReadValue(fp, bTemperature))
							throw std::runtime_error("");
						
						{
							int n = 0;
							if (!ReadValue(fp, n) || (n <= 0))
								throw std::runtime_error("");
							vecPt.resize(n);
							if (sizeof(POINT) * n != fread(&vecPt[0], 1, sizeof(POINT) * n, fp))
								throw std::runtime_error("");
						}
						{
							int n = 0;
							if (!ReadValue(fp, n) || (n <= 0))
								throw std::runtime_error("");
							vecExpo.resize(n);
							if (sizeof(Expo) * n != fread(&vecExpo[0], 1, sizeof(Expo) * n, fp))
								throw std::runtime_error("");
						}
						
						vb.resize(vecPt.size());
						if (vecPt.size() != fread(&vb[0], 1, vecPt.size(), fp))
							throw std::runtime_error("");
						voffset.resize(vecPt.size());
						if (sizeof(int) * vecPt.size() != fread(&voffset[0], 1, sizeof(int) * vecPt.size(), fp))
							throw std::runtime_error("");

						vv.resize(vecExpo.size());
						for (int i = 0; i < vecExpo.size(); ++i)
						{
							int datasize;
							if (!ReadValue(fp, datasize) || (datasize <= 0))
								throw std::runtime_error("");
							vv[i].resize(vecPt.size());
							for (int j = 0; j < (int)vecPt.size(); ++j)
							{
								vv[i][j].y.resize(datasize);
								if (datasize * sizeof(int) != fread(&vv[i][j].y[0], 1, sizeof(int) * datasize, fp))
									throw std::runtime_error("");
							}
						}

						if (bTemperature)
						{
							int n = 0;
							if (!ReadValue(fp, n) || (n <= 0))
								throw std::runtime_error("");
							vTemperature.resize(n);
							if (sizeof(int) * n != fread(&vTemperature[0], 1, sizeof(int) * n, fp))
								throw std::runtime_error("");
						}

						if (!CheckMagic(fp))
							throw std::runtime_error("");

						bok = true;
					}
					catch (const std::runtime_error&) {
					}
					
					fclose(fp);
					if (!bok)
						AtlMessageBox(m_hWnd, L"Open file failed.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
					else
					{
						while (m_tabCtrl.GetItemCount())
							m_tabCtrl.DeleteItem(0);
						for (size_t i = 0; i < m_vecGraph.size(); ++i)
							m_vecGraph[i].DestroyWindow();
						m_vecGraph.clear();

						m_ymax = ymax;
						m_scale = scale;
						m_area = area;
						m_bitdepth = bitdepth;
						m_vecExpo.swap(vecExpo);
						m_vecPt.swap(vecPt);
			
						m_tempGraph.Init(0, 0);
						m_vecGraph.resize(m_vecExpo.size());
						for (size_t i = 0; i < m_vecExpo.size(); ++i)
						{
							m_vecGraph[i].Create(m_tabCtrl.m_hWnd, nullptr, nullptr, WS_CHILD | (i ? 0 : WS_VISIBLE));
							m_vecGraph[i].Init(m_vecPt.size(), m_ymax);
							m_vecGraph[i].SetData(vv[i]);
							m_vecGraph[i].Set(vb, voffset);
							if (m_bSupportGain)
								m_tabCtrl.AddItem((LPCTSTR)FormatString(L"%sms, %hu", (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime), m_vecExpo[i].expoGain));
							else
								m_tabCtrl.AddItem((LPCTSTR)FormatString(L"%sms", (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime)));
						}
						m_curGraph = &m_vecGraph[0];
						m_curWnd = m_curGraph;
						if (vTemperature.empty())
							m_bTemperature = false;
						else
						{
							m_tabCtrl.AddItem(L"Temperature");
							m_bTemperature = true;
						}
						UpdateLayout();
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnSave(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_vecGraph.size() && (m_vecGraph[0].dataNum() > 0))
		{
			CFileDialog dlg(FALSE, _T("cns"), nullptr, OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT, L"CNS Files (*.cns)\0*.cns\0All Files (*.*)\0*.*\0\0", m_hWnd);
			if (IDOK == dlg.DoModal())
			{
				FILE* fp = _tfopen(dlg.m_szFileName, L"wb");
				if (fp)
				{
					BYTE bTemperature = (m_bTemperature && (m_tempGraph.dataNum() > 0)) ? 1 : 0;
					fwrite("@CNS", 1, 4, fp);
					fwrite(&m_area, 1, sizeof(m_area), fp);
					fwrite(&m_bitdepth, 1, sizeof(m_bitdepth), fp);
					fwrite(&m_ymax, 1, sizeof(m_ymax), fp);
					fwrite(&m_scale, 1, sizeof(m_scale), fp);
					fwrite(&bTemperature, 1, sizeof(bTemperature), fp);
					
					{
						int n = (int)m_vecPt.size();
						fwrite(&n, 1, sizeof(n), fp);
						fwrite(&m_vecPt[0], 1, sizeof(POINT) * m_vecPt.size(), fp);
					}
					{
						int n = (int)m_vecExpo.size();
						fwrite(&n, 1, sizeof(n), fp);
						fwrite(&m_vecExpo[0], 1, sizeof(Expo) * m_vecExpo.size(), fp);
					}

					for (int i = 0; i < m_vecExpo.size(); ++i)
					{
						const std::vector<Data>& v = m_vecGraph[i].GetData();
						if (0 == i)
						{
							std::vector<BYTE> vb(m_vecPt.size());
							std::vector<int> voffset(m_vecPt.size());
							for (size_t j = 0; j < m_vecPt.size(); ++j)
							{
								vb[j] = v[j].visible;
								voffset[j] = v[j].offset;
							}
							fwrite(&vb[0], 1, m_vecPt.size(), fp);
							fwrite(&voffset[0], 1, m_vecPt.size() * sizeof(int), fp);
						}
						
						int n = v[0].y.size();
						fwrite(&n, 1, sizeof(n), fp);
						for (size_t j = 0; j < m_vecPt.size(); ++j)
							fwrite(&v[j].y[0], 1, sizeof(int) * v[j].y.size(), fp);
					}

					if (bTemperature)
					{
						const std::vector<Data>& v = m_tempGraph.GetData();
						int n = (int)v[0].y.size();
						fwrite(&n, 1, sizeof(n), fp);
						fwrite(&v[0].y[0], 1, sizeof(int) * v[0].y.size(), fp);
					}

					fwrite("@CNS", 1, 4, fp);
					fclose(fp);
				}
			}
		}
		return 0;
	}

	LRESULT OnCopy(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph)
		{
			PBYTE pdib = m_curGraph->GetBitmap();
			if (pdib)
			{
				if (OpenClipboard())
				{
					EmptyClipboard();
					const PBITMAPINFOHEADER h = (const PBITMAPINFOHEADER)pdib;
					const DWORD dwLen = h->biSize + TDIBWIDTHBYTES(h->biWidth * h->biBitCount) * h->biHeight;
					HANDLE hCopy = GlobalAlloc(GMEM_MOVEABLE, dwLen);
					if (hCopy)
					{
						void* pCopy = GlobalLock(hCopy);
						if (nullptr == pCopy)
							GlobalFree(hCopy);
						else
						{
							memcpy(pCopy, h, dwLen);
							GlobalUnlock(hCopy);

							SetClipboardData(CF_DIB, hCopy);
							CloseClipboard();
						}
					}
				}

				free(pdib);
			}
		}
		return 0;
	}

	LRESULT OnCsv(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (m_curGraph && (m_curGraph->dataNum() > 0))
		{
			CFileDialog dlg(FALSE);
			if (IDOK == dlg.DoModal())
			{
				wchar_t str[MAX_PATH];
				for (int i = 0; i < m_vecExpo.size(); ++i)
				{
					if (m_bSupportGain)
						swprintf(str, L"%s-%sms-%u.csv", dlg.m_szFileName, (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime), m_vecExpo[i].expoGain);
					else
						swprintf(str, L"%s-%sms.csv", dlg.m_szFileName, (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime));
					m_vecGraph[i].OnCsv(str);
				}
				if (m_bTemperature && (m_tempGraph.dataNum() > 0))
				{
					swprintf(str, L"%s-Temperature.csv", dlg.m_szFileName);
					m_tempGraph.OnCsv(str);
				}
			}
		}
		return 0;
	}
	
	LRESULT OnStop(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CloseCamera();
		return 0;
	}

	LRESULT OnStart(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (nullptr == m_hcam)
		{
			if (2 == __argc) /* launch by command line */
				OpenCamera(__wargv[1]);
			else
			{
				ToupcamDeviceV2 arr[TOUPCAM_MAX];
				const unsigned num = Toupcam_EnumV2(arr);
				if (num <= 0)
					AtlMessageBox(m_hWnd, L"No camera found.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
				else if (1 == num)
					OpenCamera(arr[0].id);
				else
				{
					CPoint pt;
					GetCursorPos(&pt);
					CMenu menu;
					menu.CreatePopupMenu();
					for (unsigned i = 0; i < num; ++i)
						menu.AppendMenu(MF_STRING, ID_CAMERA00 + i, arr[i].displayname);
					const int ret = menu.TrackPopupMenu(TPM_RIGHTALIGN | TPM_RETURNCMD, pt.x, pt.y, m_hWnd);
					if (ret >= ID_CAMERA00)
					{
						ATLASSERT(ret - ID_CAMERA00 < num);
						OpenCamera(arr[ret - ID_CAMERA00].id);
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnMsgCamera(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		switch (wParam)
		{
		case TOUPCAM_EVENT_ERROR:
			CloseCamera();
			AtlMessageBox(m_hWnd, L"Generic error.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			break;
		case TOUPCAM_EVENT_DISCONNECTED:
			CloseCamera();
			AtlMessageBox(m_hWnd, L"Camera disconnect.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			break;
		case TOUPCAM_EVENT_IMAGE:
			OnEventImage();
			break;
		default:
			break;
		}
		return 0;
	}

	void OnTimer(UINT_PTR nIDEvent)
	{
		switch (nIDEvent)
		{
		case TIMER_ID:
			if (m_bWantTigger && (GetTickCount() - m_tickLast >= m_vecExpo[m_idxExpo].delayTime + TIMER_EPSILON))
			{
				m_bWantTigger = false;
				Toupcam_Trigger(m_hcam, 1);
			}
			break;
		case TIMER_TEMP:
			if (m_bTemperature)
			{
				short temp = 0;
				if (SUCCEEDED(Toupcam_get_Temperature(m_hcam, &temp)))
				{
					int val = temp;
					m_tempGraph.AddData(&val);
				}
			}
			break;
		default:
			break;
		}
	}

	LRESULT OnTcnSelChange(int /*idCtrl*/, LPNMHDR /*pnmh*/, BOOL& /*bHandled*/)
	{
		const int idx = m_tabCtrl.GetCurSel();
		CWindow* newWnd = nullptr;
		if ((idx >= 0) && (idx < m_vecGraph.size()))
			newWnd = &m_vecGraph[idx];
		else if (nullptr == m_hcam)
		{
			if (m_bTemperature && (idx + 1 == m_tabCtrl.GetItemCount()))
				newWnd = &m_tempGraph;
		}
		else
		{
			if (idx + 1 == m_tabCtrl.GetItemCount())
				newWnd = &m_view;
			else if (m_bTemperature && (idx + 2 == m_tabCtrl.GetItemCount()))
				newWnd = &m_tempGraph;
		}
		if (newWnd && (m_curWnd != newWnd))
		{
			if (m_curWnd)
				m_curWnd->ShowWindow(SW_HIDE);
			m_curWnd = newWnd;
			if ((idx >= 0) && (idx < m_vecGraph.size()))
				m_curGraph = &m_vecGraph[idx];
			else if (newWnd == &m_tempGraph)
				m_curGraph = &m_tempGraph;
			else
				m_curGraph = nullptr;
			m_curWnd->ShowWindow(SW_SHOW);
			UpdateLayout();
		}
		return 0;
	}

	void UpdateLayout(BOOL bResizeBars = TRUE)
	{
		CFrameWindowImpl<CMainFrame>::UpdateLayout(bResizeBars);
		
		CRect rect;
		m_tabCtrl.GetClientRect(&rect);
		m_tabCtrl.AdjustRect(FALSE, &rect);
		for (size_t i = 0; i < m_vecExpo.size(); ++i)
			m_vecGraph[i].MoveWindow(&rect);
		m_tempGraph.MoveWindow(&rect);
		m_view.MoveWindow(&rect);
	}
private:
	void OpenCamera(const wchar_t* camId)
	{
		m_hcam = Toupcam_Open(camId);
		if (nullptr == m_hcam)
		{
			AtlMessageBox(m_hWnd, L"Open camera failed.", (LPCTSTR)nullptr, MB_OK | MB_ICONWARNING);
			return;
		}

		m_bSupportGain = IsSupportGain(m_hcam);
		m_pModel = Toupcam_query_Model(m_hcam);
		Toupcam_put_eSize(m_hcam, 0); // always use the maximum resolution
		Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_RAW, 1);
		Toupcam_put_HZ(m_hcam, 2);
		Toupcam_put_AutoExpoEnable(m_hcam, 0); // always disable auto exposure

		CConfigDlg dlg(m_hcam, m_pModel);
		if (IDOK != dlg.DoModal())
			CloseCamera();
		else
		{
			while (m_tabCtrl.GetItemCount())
				m_tabCtrl.DeleteItem(0);
			for (size_t i = 0; i < m_vecGraph.size(); ++i)
				m_vecGraph[i].DestroyWindow();
			m_vecGraph.clear();

			m_area = dlg.m_area;
			m_vecExpo = dlg.m_vecExpo;
			m_vecPt = dlg.m_vecPt;
			m_scale = 1;

			unsigned nFourCC;
			Toupcam_get_RawFormat(m_hcam, &nFourCC, &m_bitdepth);
			m_ymax = 1 << m_bitdepth;
			if (dlg.m_bin & 0x40)
				m_ymax *= (dlg.m_bin & 0xf) * (dlg.m_bin & 0xf);
			if (m_bitdepth > 8)
			{
				switch (dlg.m_scale)
				{
				case 1:
					m_scale = 4;
					break;
				case 2:
					m_scale = 16;
					break;
				default:
					break;
				}
				m_ymax *= m_scale;
				if (m_ymax > 65536)
					m_ymax = 65536;
			}
			
			int w = 0, h = 0;
			Toupcam_get_FinalSize(m_hcam, &w, &h);
			m_pRawData = malloc(w * h * ((m_bitdepth > 8) ? 2 : 1));

			m_tempGraph.Init(0, 0);
			m_view.Init(w, h, nFourCC, m_bitdepth);
			m_view.ShowWindow(SW_HIDE);
			m_vecGraph.resize(m_vecExpo.size());
			for (size_t i = 0; i < m_vecExpo.size(); ++i)
			{
				m_vecGraph[i].Create(m_tabCtrl.m_hWnd, nullptr, nullptr, WS_CHILD | (i ? 0 : WS_VISIBLE));
				m_vecGraph[i].Init(m_vecPt.size(), m_ymax);
				if (m_bSupportGain)
					m_tabCtrl.AddItem((LPCTSTR)FormatString(L"%sms, %hu", (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime), m_vecExpo[i].expoGain));
				else
					m_tabCtrl.AddItem((LPCTSTR)FormatString(L"%sms", (LPCTSTR)FormatExpoTime(m_vecExpo[i].expoTime)));
			}
			m_curGraph = &m_vecGraph[0];
			m_curWnd = m_curGraph;
			if ((E_NOTIMPL != Toupcam_get_Temperature(m_hcam, nullptr)) && dlg.m_temp)
			{
				m_tabCtrl.AddItem(L"Temperature");
				SetTimer(TIMER_TEMP, dlg.m_temp * 1000, nullptr);
				m_bTemperature = true;
			}
			else
			{
				m_bTemperature = false;
			}
			m_tabCtrl.AddItem(L"Video");

			int val = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, &val);
			m_bTriggerMode = (val != 0);
			
			m_idxExpo = 0;
			Toupcam_put_ExpoTime(m_hcam, m_vecExpo[m_idxExpo].expoTime);
			if (m_bSupportGain)
				Toupcam_put_ExpoAGain(m_hcam, m_vecExpo[m_idxExpo].expoGain);
			Toupcam_StartPullModeWithWndMsg(m_hcam, m_hWnd, MSG_CAMERA);
			if (m_bTriggerMode)
			{
				Toupcam_Trigger(m_hcam, 1);
				m_bWantTigger = false;
			}
			SetTimer(TIMER_ID, TIMER_EPSILON, nullptr);
			m_tickLast = GetTickCount();

			SetWindowText((LPCTSTR)FormatString(L"Consistency Test: [%s]", m_pModel->name));
			UpdateLayout();
		}
	}

	void CloseCamera()
	{
		if (m_hcam)
		{
			Toupcam_Close(m_hcam);
			m_hcam = nullptr;
		}
		if (m_pRawData)
		{
			free(m_pRawData);
			m_pRawData = nullptr;
		}
		KillTimer(TIMER_ID);
		KillTimer(TIMER_TEMP);
	}

	template<typename T>
	void GetData(int* arr, const T* pData, const ToupcamFrameInfoV4& info)
	{
		const int r = m_area / 2;
		for (int i = 0; i < (int)m_vecPt.size(); ++i)
		{
			long long sum = 0;
			for (int y = m_vecPt[i].y - r; y < m_vecPt[i].y + r; ++y)
			{
				const T* p = pData + info.v3.width * (info.v3.height - 1 - y);
				for (int x = m_vecPt[i].x - r; x < m_vecPt[i].x + r; ++x)
					sum += p[x];
			}
			arr[i] = sum * m_scale / (m_area * m_area);
		}
	}

	void OnEventImage()
	{
		const DWORD dwTick = GetTickCount();
		bool bAdd = false;
		ToupcamFrameInfoV4 info = { 0 };
		const HRESULT hr = Toupcam_PullImageV4(m_hcam, m_pRawData, 0, 0, 0, &info);
		if (SUCCEEDED(hr))
		{
			if (m_bTriggerMode)
				bAdd = true;
			else if (dwTick - m_tickLast >= m_vecExpo[m_idxExpo].delayTime + TIMER_EPSILON)
				bAdd = true;
			if (bAdd)
			{
				int* arr = (int*)alloca(sizeof(int) * m_vecPt.size());
				if (m_bitdepth > 8)
					GetData(arr, (const PUSHORT)m_pRawData, info);
				else
					GetData(arr, (const PBYTE)m_pRawData, info);
				m_vecGraph[m_idxExpo].AddData(arr);
			}
			m_view.SetData(m_pRawData);
		}

		if (bAdd)
		{
			m_tickLast = dwTick;

			if (m_vecExpo.size() > 1)
			{
				m_idxExpo = (++m_idxExpo) % m_vecExpo.size();
				Toupcam_put_ExpoTime(m_hcam, m_vecExpo[m_idxExpo].expoTime);
				if (m_bSupportGain)
					Toupcam_put_ExpoAGain(m_hcam, m_vecExpo[m_idxExpo].expoGain);
			}
			if (m_bTriggerMode)
			{
				if (0 == m_vecExpo[m_idxExpo].delayTime)
					Toupcam_Trigger(m_hcam, 1);
				else
					m_bWantTigger = true;
			}
		}
	}

	static bool CheckMagic(FILE* fp)
	{
		char magic[5] = { 0 };
		if (4 == fread(magic, 1, 4, fp))
		{
			if (memcmp(magic, "@CNS", 4) == 0)
				return true;
		}
		return false;
	}

	template<typename T>
	static bool ReadValue(FILE* fp, T& val)
	{
		if (sizeof(val) == fread(&val, 1, sizeof(val), fp))
			return true;
		return false;
	}
};

static int Run()
{
	CMessageLoop theLoop;
	_Module.AddMessageLoop(&theLoop);

	g_curHand1 = AtlLoadCursor(IDC_HAND1);
	g_curHand2 = AtlLoadCursor(IDC_HAND2);
	g_curMove = AtlLoadCursor(IDC_MOVE);
	g_curArrow = LoadCursor(nullptr, MAKEINTRESOURCE(IDC_ARROW));

	CMainFrame frmMain;
	if (frmMain.CreateEx() == nullptr)
		return 0;
	Toupcam_GigeEnable(nullptr, nullptr);
	frmMain.ShowWindow(SW_SHOWMAXIMIZED);

	int nRet = theLoop.Run();
	_Module.RemoveMessageLoop();
	return nRet;
}

int WINAPI _tWinMain(HINSTANCE hInstance, HINSTANCE /*hPrevInstance*/, LPTSTR /*pCmdLine*/, int /*nCmdShow*/)
{
	if ((2 == __argc) && (0 == wcscmp(__wargv[1], L"all")))
	{
		wchar_t strPath[MAX_PATH + 1] = { 0 };
		if (GetModuleFileName(nullptr, strPath, MAX_PATH))
		{
			ToupcamDeviceV2 arr[TOUPCAM_MAX];
			const unsigned num = Toupcam_EnumV2(arr);
			for (unsigned i = 0; i < num; ++i)
				ShellExecuteW(nullptr, L"open", strPath, arr[i].id, nullptr, SW_SHOWMAXIMIZED);
		}
		return 0;
	}

	INITCOMMONCONTROLSEX iccx;
	iccx.dwSize = sizeof(iccx);
	iccx.dwICC = ICC_COOL_CLASSES | ICC_BAR_CLASSES;
	InitCommonControlsEx(&iccx);
	OleInitialize(nullptr);
	_Module.Init(nullptr, hInstance);
	int nRet = Run();
	_Module.Term();
	return nRet;
}

#if defined _M_IX86
#pragma comment(linker, "/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='x86' publicKeyToken='6595b64144ccf1df' language='*'\"")
#elif defined _M_X64
#pragma comment(linker, "/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='amd64' publicKeyToken='6595b64144ccf1df' language='*'\"")
#endif
#include <windows.h>
#include <atlbase.h>
#include <atlwin.h>
#include <atlapp.h>
CAppModule _Module;
#include <shlobj.h>
#include <shlwapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <atlctrls.h>
#include <atlframe.h>
#include <atlcrack.h>
#include <atldlgs.h>
#include <atlstr.h>
#include "toupcam.h"
#include "resource.h"
#include <sstream>
#include <iomanip>
#include <InitGuid.h>
#include <wincodec.h>
#include <wmsdkidl.h>
#include <Dbt.h>

#define MSG_CAMEVENT			(WM_APP + 1)
#define MSG_CAMENUM				(WM_APP + 2)

class CMainFrame;

static BOOL SaveImageBmp(const wchar_t* strFilename, const void* pData, const BITMAPINFOHEADER* pHeader)
{
	FILE* fp = _wfopen(strFilename, L"wb");
	if (fp)
	{
		BITMAPFILEHEADER fheader = { 0 };
		fheader.bfType = 0x4d42;
		fheader.bfSize = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER) + pHeader->biSizeImage;
		fheader.bfOffBits = (DWORD)(sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER));
		fwrite(&fheader, sizeof(fheader), 1, fp);
		fwrite(pHeader, 1, sizeof(BITMAPINFOHEADER), fp);
		fwrite(pData, 1, pHeader->biSizeImage, fp);
		fclose(fp);
		return TRUE;
	}
	return FALSE;
}

/* https://docs.microsoft.com/en-us/windows/desktop/wic/-wic-lh */
static BOOL SaveImageByWIC(const wchar_t* strFilename, const void* pData, const BITMAPINFOHEADER* pHeader)
{
	GUID guidContainerFormat;
	if (PathMatchSpec(strFilename, L"*.jpg"))
		guidContainerFormat = GUID_ContainerFormatJpeg;
	else if (PathMatchSpec(strFilename, L"*.png"))
		guidContainerFormat = GUID_ContainerFormatPng;
	else
		return FALSE;

	CComPtr<IWICImagingFactory> spIWICImagingFactory;
	HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, NULL, CLSCTX_INPROC_SERVER, __uuidof(IWICImagingFactory), (LPVOID*)&spIWICImagingFactory);
	if (FAILED(hr))
		return FALSE;

	CComPtr<IWICBitmapEncoder> spIWICBitmapEncoder;
	hr = spIWICImagingFactory->CreateEncoder(guidContainerFormat, NULL, &spIWICBitmapEncoder);
	if (FAILED(hr))
		return FALSE;

	CComPtr<IWICStream> spIWICStream;
	spIWICImagingFactory->CreateStream(&spIWICStream);
	if (FAILED(hr))
		return FALSE;

	hr = spIWICStream->InitializeFromFilename(strFilename, GENERIC_WRITE);
	if (FAILED(hr))
		return FALSE;

	hr = spIWICBitmapEncoder->Initialize(spIWICStream, WICBitmapEncoderNoCache);
	if (FAILED(hr))
		return FALSE;

	CComPtr<IWICBitmapFrameEncode> spIWICBitmapFrameEncode;
	CComPtr<IPropertyBag2> spIPropertyBag2;
	hr = spIWICBitmapEncoder->CreateNewFrame(&spIWICBitmapFrameEncode, &spIPropertyBag2);
	if (FAILED(hr))
		return FALSE;

	if (GUID_ContainerFormatJpeg == guidContainerFormat)
	{
		PROPBAG2 option = { 0 };
		option.pstrName = L"ImageQuality"; /* jpg quality, you can change this setting */
		CComVariant varValue(0.75f);
		spIPropertyBag2->Write(1, &option, &varValue);
	}
	hr = spIWICBitmapFrameEncode->Initialize(spIPropertyBag2);
	if (FAILED(hr))
		return FALSE;

	hr = spIWICBitmapFrameEncode->SetSize(pHeader->biWidth, pHeader->biHeight);
	if (FAILED(hr))
		return FALSE;

	WICPixelFormatGUID formatGUID = GUID_WICPixelFormat24bppBGR;
	hr = spIWICBitmapFrameEncode->SetPixelFormat(&formatGUID);
	if (FAILED(hr))
		return FALSE;

	const LONG nWidthBytes = TDIBWIDTHBYTES(pHeader->biWidth * pHeader->biBitCount);
	for (LONG i = 0; i < pHeader->biHeight; ++i)
	{
		hr = spIWICBitmapFrameEncode->WritePixels(1, nWidthBytes, nWidthBytes, ((BYTE*)pData) + nWidthBytes * (pHeader->biHeight - i - 1));
		if (FAILED(hr))
			return FALSE;
	}

	hr = spIWICBitmapFrameEncode->Commit();
	if (FAILED(hr))
		return FALSE;
	hr = spIWICBitmapEncoder->Commit();
	if (FAILED(hr))
		return FALSE;
	
	return TRUE;
}

class CExposureTimeDlg : public CDialogImpl<CExposureTimeDlg>
{
	HToupcam	m_hcam;

	BEGIN_MSG_MAP(CExposureTimeDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_EXPOSURETIME };
	CExposureTimeDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CString str;
		GetDlgItemText(IDC_EDIT1, str);

		wchar_t* endptr = NULL;
		const double d = _tcstod(str.GetString(), &endptr);
		if (endptr && *endptr)
		{
			GotoDlgCtrl(GetDlgItem(IDC_EDIT1));
			AtlMessageBox(m_hWnd, L"Bad format.");
			return 0;
		}

		const unsigned nTime = (unsigned)(d * 1000);
		unsigned nMin = 0, nMax = 0, nDef = 0;
		if (SUCCEEDED(Toupcam_get_ExpTimeRange(m_hcam, &nMin, &nMax, &nDef)))
		{
			if ((nTime < nMin) || (nTime >= nMax))
			{
				GotoDlgCtrl(GetDlgItem(IDC_EDIT1));
				AtlMessageBox(m_hWnd, L"Out of range.");
				return 0;
			}
		}

		Toupcam_put_ExpoTime(m_hcam, nTime);
		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CSpeedDlg : public CDialogImpl<CSpeedDlg>
{
	HToupcam	m_hcam;

	BEGIN_MSG_MAP(CSpeedDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_SPEED };
	CSpeedDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		CTrackBarCtrl ctrl(GetDlgItem(IDC_SLIDER1));
		ctrl.SetRangeMin(0);
		ctrl.SetRangeMax(Toupcam_get_MaxSpeed(m_hcam));

		unsigned short nSpeed = 0;
		if (SUCCEEDED(Toupcam_get_Speed(m_hcam, &nSpeed)))
			ctrl.SetPos(nSpeed);

		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CTrackBarCtrl ctrl(GetDlgItem(IDC_SLIDER1));
		Toupcam_put_Speed(m_hcam, ctrl.GetPos());

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CMaxAEDlg : public CDialogImpl<CMaxAEDlg>
{
	HToupcam	m_hcam;
	BEGIN_MSG_MAP(CMaxAEDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_MAXAE };
	CMaxAEDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		SetDlgItemInt(IDC_EDIT1, 350000);
		SetDlgItemInt(IDC_EDIT2, 500);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		BOOL bTran1 = FALSE, bTran2 = FALSE;
		const UINT nTime = GetDlgItemInt(IDC_EDIT1, &bTran1, FALSE);
		const UINT nGain = GetDlgItemInt(IDC_EDIT2, &bTran2, FALSE);
		if (bTran1 && bTran2)
			Toupcam_put_MaxAutoExpoTimeAGain(m_hcam, nTime, nGain);
		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CLedDlg : public CDialogImpl<CLedDlg>
{
	HToupcam	m_hcam;
	BEGIN_MSG_MAP(CLedDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnButton1)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnButton2)
		COMMAND_HANDLER(IDC_BUTTON3, BN_CLICKED, OnButton3)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_LED };
	CLedDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		return TRUE;
	}

	LRESULT OnButton1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		const UINT nIndex = GetDlgItemInt(IDC_EDIT1);
		Toupcam_put_LEDState(m_hcam, nIndex, 1, 0);
		return 0;
	}

	LRESULT OnButton2(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		const UINT nIndex = GetDlgItemInt(IDC_EDIT1);
		const UINT nPeriod = GetDlgItemInt(IDC_EDIT2);
		Toupcam_put_LEDState(m_hcam, nIndex, 2, nPeriod);
		return 0;
	}

	LRESULT OnButton3(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		const UINT nIndex = GetDlgItemInt(IDC_EDIT1);
		Toupcam_put_LEDState(m_hcam, nIndex, 0, 0);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

static wchar_t* PixelFormatHdrName(int val)
{
	switch (val)
	{
	case TOUPCAM_PIXELFORMAT_HDR8HL:
		return L"HDR8HL";
	case TOUPCAM_PIXELFORMAT_HDR10HL:
		return L"HDR10HL";
	case TOUPCAM_PIXELFORMAT_HDR11HL:
		return L"HDR11HL";
	case TOUPCAM_PIXELFORMAT_HDR12HL:
		return L"HDR12HL";
	case TOUPCAM_PIXELFORMAT_HDR14HL:
		return L"HDR14HL";
	default:
		return nullptr;
	}
}

class CPixelFormatDlg : public CDialogImpl<CPixelFormatDlg>
{
	const ToupcamDeviceV2&	m_tdev;
	HToupcam				m_hcam;

	BEGIN_MSG_MAP(CPixelFormatDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
		COMMAND_HANDLER(IDC_COMBO1, CBN_SELCHANGE, OnSelchange1)
	END_MSG_MAP()
public:
	enum { IDD = IDD_PIXELFORMAT };

	CPixelFormatDlg(const ToupcamDeviceV2& tdev, HToupcam hcam)
	: m_tdev(tdev), m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		CComboBox cbox(GetDlgItem(IDC_COMBO1));
		{
			int num = 0, pixelFormat = 0;
			if (SUCCEEDED(Toupcam_get_PixelFormatSupport(m_hcam, -1, &num)) && (num > 0))
			{
				for (int i = 0; i < num; ++i)
				{
					if (SUCCEEDED(Toupcam_get_PixelFormatSupport(m_hcam, (char)i, &pixelFormat)))
						cbox.SetItemData(cbox.AddString(CA2W(Toupcam_get_PixelFormatName(pixelFormat))), pixelFormat);
				}
			}
		}

		{
			int val = 0, num = cbox.GetCount();
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_PIXEL_FORMAT, &val);
			for (int i = 0; i < num; ++i)
			{
				if (cbox.GetItemData(i) == val)
				{
					cbox.SetCurSel(i);
					break;
				}
			}
		}
		return TRUE;
	}

	LRESULT OnSelchange1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CComboBox cbox(GetDlgItem(IDC_COMBO1));
		Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_PIXEL_FORMAT, cbox.GetItemData(cbox.GetCurSel()));
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CRoiDlg : public CDialogImpl<CRoiDlg>
{
	friend class CMainFrame;
	unsigned xOffset_;
	unsigned yOffset_;
	unsigned xWidth_;
	unsigned yHeight_;

	BEGIN_MSG_MAP(CRoiDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_ROI };
	CRoiDlg()
	: xOffset_(0), yOffset_(0), xWidth_(0), yHeight_(0)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		SetDlgItemInt(IDC_EDIT1, xOffset_);
		SetDlgItemInt(IDC_EDIT2, yOffset_);
		SetDlgItemInt(IDC_EDIT3, xWidth_);
		SetDlgItemInt(IDC_EDIT4, yHeight_);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		xOffset_ = GetDlgItemInt(IDC_EDIT1);
		yOffset_ = GetDlgItemInt(IDC_EDIT2);
		xWidth_ = GetDlgItemInt(IDC_EDIT3);
		yHeight_ = GetDlgItemInt(IDC_EDIT4);

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CTriggerNumberDlg : public CDialogImpl<CTriggerNumberDlg>
{
	friend class CMainFrame;
	unsigned short number_;

	BEGIN_MSG_MAP(CTriggerNumberDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDC_CHECK1, BN_CLICKED, OnClickCheck1)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_TRIGGERNUMBER };
	CTriggerNumberDlg() : number_(1)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		if (0xffff == number_)
		{
			CheckDlgButton(IDC_CHECK1, 1);
			GetDlgItem(IDC_EDIT1).EnableWindow(FALSE);
		}
		SetDlgItemInt(IDC_EDIT1, number_);
		return TRUE;
	}

	LRESULT OnClickCheck1(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		GetDlgItem(IDC_EDIT1).EnableWindow(!IsDlgButtonChecked(IDC_CHECK1));
		return 0;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		if (IsDlgButtonChecked(IDC_CHECK1))
			number_ = 0xffff;
		else
		{
			number_ = GetDlgItemInt(IDC_EDIT1);
			if ((0 == number_) || (number_ >= SHRT_MAX))
			{
				AtlMessageBox(m_hWnd, L"Invalid number");
				return 0;
			}
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

class CTECTargetDlg : public CDialogImpl<CTECTargetDlg>
{
	HToupcam	m_hcam;

	BEGIN_MSG_MAP(CTECTargetDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_TECTARGET };
	CTECTargetDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		int val = 0;
		Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TECTARGET, &val);

		wchar_t str[256];
		swprintf(str, L"%d.%d", val / 10, val % 10);
		SetDlgItemText(IDC_EDIT1, str);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CString str;
		GetDlgItemText(IDC_EDIT1, str);
		wchar_t* endptr;
		const double d = _tcstod((LPCTSTR)str, &endptr);
		Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TECTARGET, (int)(d * 10));

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CSnapnDlg : public CDialogImpl<CSnapnDlg>
{
	friend class CMainFrame;
	unsigned m_nNum;

	BEGIN_MSG_MAP(CSnapnDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_SNAPN };
	CSnapnDlg() : m_nNum(3)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		SetDlgItemInt(IDC_EDIT1, m_nNum);
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		BOOL bTrans;
		m_nNum = GetDlgItemInt(IDC_EDIT1, &bTrans, FALSE);
		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CEEPROMDlg : public CDialogImpl<CEEPROMDlg>
{
	HToupcam	m_hcam;

	BEGIN_MSG_MAP(CEEPROMDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnButton1)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnButton2)
		COMMAND_HANDLER(IDC_BUTTON3, BN_CLICKED, OnButton3)
		COMMAND_HANDLER(IDC_BUTTON4, BN_CLICKED, OnButton4)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_EEPROM };
	CEEPROMDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		SetDlgItemText(IDC_EDIT1, L"0x0000");
		SetDlgItemText(IDC_EDIT2, L"0x2000");
		return TRUE;
	}

	LRESULT OnButton1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
				HRESULT hr = Toupcam_read_EEPROM(m_hcam, uAddr, tmpBuffer, uLength);
				if (FAILED(hr))
					AtlMessageBox(m_hWnd, L"Failed to read EEPROM.");
				else if (0 == hr)
					AtlMessageBox(m_hWnd, L"Read 0 byte.");
				else if (hr > 0)
				{
					std::wstringstream wstr;
					wstr << L"EEPROM: length = " << hr << L", data = ";
					for (int i = 0; i < hr; ++i)
						wstr << std::hex << std::setw(2) << std::setfill((wchar_t)'0') << tmpBuffer[i] << L" ";
					AtlMessageBox(m_hWnd, wstr.str().c_str());
				}
			}
		}
		return 0;
	}

	LRESULT OnButton2(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 }, strData[1024] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)) && GetDlgItemText(IDC_EDIT3, strData, _countof(strData)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul((LPCTSTR)strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul((LPCTSTR)strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
				memset(tmpBuffer, 0, uLength);
				for (size_t i = 0; i < uLength * 2; i += 2)
				{
					if ('\0' == strData[i])
						break;
					if (strData[i] >= '0' && strData[i] <= '9')
						tmpBuffer[i / 2] = (strData[i] - '0') << 4;
					else if (strData[i] >= 'a' && strData[i] <= 'f')
						tmpBuffer[i / 2] = (strData[i] - 'a' + 10) << 4;
					else if (strData[i] >= 'A' && strData[i] <= 'F')
						tmpBuffer[i / 2] = (strData[i] - 'A' + 10) << 4;
					if (strData[i + 1] >= '0' && strData[i + 1] <= '9')
						tmpBuffer[i / 2] |= (strData[i + 1] - '0');
					else if (strData[i + 1] >= 'a' && strData[i + 1] <= 'f')
						tmpBuffer[i / 2] |= (strData[i + 1] - 'a' + 10);
					else if (strData[i + 1] >= 'A' && strData[i + 1] <= 'F')
						tmpBuffer[i / 2] |= (strData[i + 1] - 'A' + 10);
				}
				const HRESULT hr = Toupcam_write_EEPROM(m_hcam, uAddr, tmpBuffer, uLength);
				wchar_t strMessage[256];
				swprintf(strMessage, L"Write EEPROM, length = %u, result = 0x%08x", uLength, hr);
				AtlMessageBox(m_hWnd, strMessage);
			}
		}
		return 0;
	}

	LRESULT OnButton3(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpWriteBuffer = (unsigned char*)alloca(uLength);
				unsigned char* tmpReadBuffer = (unsigned char*)alloca(uLength);
				srand(GetTickCount());
				for (unsigned i = 0; i < uLength; ++i)
					tmpWriteBuffer[i] = (unsigned char)rand();
				const HRESULT hrWrite = Toupcam_write_EEPROM(m_hcam, uAddr, tmpWriteBuffer, uLength);
				const HRESULT hrRead = Toupcam_read_EEPROM(m_hcam, uAddr, tmpReadBuffer, uLength);
				if ((hrWrite == uLength) && (hrRead == uLength))
				{
					if (0 == memcmp(tmpWriteBuffer, tmpReadBuffer, uLength))
					{
						AtlMessageBox(m_hWnd, L"Test OK");
						return 0;
					}
				}

				wchar_t strText[256];
				swprintf(strText, L"Test failed, hrWrite = 0x%08x, hrRead = 0x%08x", hrWrite, hrRead);
				AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
			}
		}
		return 0;
	}

	LRESULT OnButton4(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpWriteBuffer = (unsigned char*)alloca(uLength);
				memset(tmpWriteBuffer, 0xff, uLength);
				const HRESULT hr = Toupcam_write_EEPROM(m_hcam, uAddr, tmpWriteBuffer, uLength);
				if (hr == uLength)
				{
					AtlMessageBox(m_hWnd, L"Erase OK");
					return 0;
				}

				AtlMessageBox(m_hWnd, L"Erase failed");
			}
		}
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CWaitDlg : public CDialogImpl<CWaitDlg>
{
	HToupcam	m_hcam;
	DWORD		m_tick;

	BEGIN_MSG_MAP(CWaitDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		MESSAGE_HANDLER(WM_TIMER, OnWmTimer)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_WAIT };
	CWaitDlg(HToupcam hcam)
	: m_hcam(hcam), m_tick(GetTickCount())
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		SetTimer(1, 200, NULL);

		return TRUE;
	}

	LRESULT OnWmTimer(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		if (1 == wParam)
		{
			if (S_OK == Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_STATUS, 0, 0, NULL))
				EndDialog(IDOK);
			else
				SetDlgItemInt(IDC_STATIC1, GetTickCount() - m_tick, FALSE);
		}
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CFlashDlg : public CDialogImpl<CFlashDlg>
{
	HToupcam	m_hcam;
	int m_totalSize, m_eBlock, m_rwBlock;

	BEGIN_MSG_MAP(CFlashDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnButton1)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnButton2)
		COMMAND_HANDLER(IDC_BUTTON3, BN_CLICKED, OnButton3)
		COMMAND_HANDLER(IDC_BUTTON4, BN_CLICKED, OnButton4)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_FLASH };
	CFlashDlg(HToupcam hcam)
	: m_hcam(hcam)
	, m_totalSize(Toupcam_rwc_Flash(hcam, TOUPCAM_FLASH_SIZE, 0, 0, NULL))
	, m_eBlock(Toupcam_rwc_Flash(hcam, TOUPCAM_FLASH_EBLOCK, 0, 0, NULL))
	, m_rwBlock(Toupcam_rwc_Flash(hcam, TOUPCAM_FLASH_RWBLOCK, 0, 0, NULL))
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		SetDlgItemText(IDC_EDIT1, L"0x0000");
		SetDlgItemText(IDC_EDIT2, L"0x400");

		wchar_t strText[256];
		swprintf(strText, L"%u (0x%08x)", m_totalSize, m_totalSize);
		SetDlgItemText(IDC_STATIC1, strText);
		swprintf(strText, L"%u (0x%08x)", m_eBlock, m_eBlock);
		SetDlgItemText(IDC_STATIC2, strText);
		swprintf(strText, L"%u (0x%08x)", m_rwBlock, m_rwBlock);
		SetDlgItemText(IDC_STATIC3, strText);
		return TRUE;
	}

	LRESULT OnButton1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				if ((uAddr % m_rwBlock) || (uLength % m_rwBlock))
					AtlMessageBox(m_hWnd, L"Address and length must be an integer multiple of read write block.");
				else
				{
					unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
					HRESULT hr = Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_READ, uAddr, uLength, tmpBuffer);
					if (FAILED(hr))
					{
						wchar_t strText[256];
						swprintf(strText, L"Read failed, hr = 0x%08x", hr);
						AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
					}
					else if (0 == hr)
						AtlMessageBox(m_hWnd, L"Read 0 byte.");
					else if (hr > 0)
					{
						std::wstringstream wstr;
						wstr << L"Flash: length = " << hr << L", data = ";
						for (int i = 0; i < hr; ++i)
							wstr << std::hex << std::setw(2) << std::setfill((wchar_t)'0') << tmpBuffer[i] << L" ";
						AtlMessageBox(m_hWnd, wstr.str().c_str());
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnButton2(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 }, strData[1024] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)) && GetDlgItemText(IDC_EDIT3, strData, _countof(strData)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul((LPCTSTR)strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul((LPCTSTR)strLength, &endptr, 16);
			if (uLength)
			{
				if ((uAddr % m_rwBlock) || (uLength % m_rwBlock))
					AtlMessageBox(m_hWnd, L"Address and length must be an integer multiple of read write block.");
				else
				{
					unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
					memset(tmpBuffer, 0, uLength);
					for (size_t i = 0; i < uLength * 2; i += 2)
					{
						if ('\0' == strData[i])
							break;
						if (strData[i] >= '0' && strData[i] <= '9')
							tmpBuffer[i / 2] = (strData[i] - '0') << 4;
						else if (strData[i] >= 'a' && strData[i] <= 'f')
							tmpBuffer[i / 2] = (strData[i] - 'a' + 10) << 4;
						else if (strData[i] >= 'A' && strData[i] <= 'F')
							tmpBuffer[i / 2] = (strData[i] - 'A' + 10) << 4;
						if (strData[i + 1] >= '0' && strData[i + 1] <= '9')
							tmpBuffer[i / 2] |= (strData[i + 1] - '0');
						else if (strData[i + 1] >= 'a' && strData[i + 1] <= 'f')
							tmpBuffer[i / 2] |= (strData[i + 1] - 'a' + 10);
						else if (strData[i + 1] >= 'A' && strData[i + 1] <= 'F')
							tmpBuffer[i / 2] |= (strData[i + 1] - 'A' + 10);
					}
					const HRESULT hr = Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_WRITE, uAddr, uLength, tmpBuffer);
					if (FAILED(hr))
					{
						wchar_t strText[256];
						swprintf(strText, L"Write failed, hr = 0x%08x", hr);
						AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
					}
					else
					{
						CWaitDlg dlg(m_hcam);
						dlg.DoModal();
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnButton3(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 }, strText[256];
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				if ((uAddr % m_rwBlock) || (uLength % m_rwBlock))
					AtlMessageBox(m_hWnd, L"Address and length must be an integer multiple of read write block.");
				else
				{
					unsigned char* tmpWriteBuffer = (unsigned char*)alloca(uLength);
					unsigned char* tmpReadBuffer = (unsigned char*)alloca(uLength);
					srand(GetTickCount());
					for (unsigned i = 0; i < uLength; ++i)
						tmpWriteBuffer[i] = (unsigned char)rand();
					HRESULT hr = Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_WRITE, uAddr, uLength, tmpWriteBuffer);
					if (FAILED(hr))
					{
						swprintf(strText, L"Write failed, hr = 0x%08x", hr);
						AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
					}
					else
					{
						CWaitDlg dlg(m_hcam);
						if (IDOK == dlg.DoModal())
						{
							hr = Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_READ, uAddr, uLength, tmpReadBuffer);
							if (FAILED(hr))
							{
								swprintf(strText, L"Read failed, hr = 0x%08x", hr);
								AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
							}
							else if (hr != uLength)
							{
								swprintf(strText, L"Read partial, %u byte(s)", hr);
								AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
							}
							else if (0 == memcmp(tmpWriteBuffer, tmpReadBuffer, uLength))
								AtlMessageBox(m_hWnd, L"Test OK");
							else
							{
								AtlMessageBox(m_hWnd, L"Test failed");
							}
						}
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnButton4(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strAddr[64] = { 0 }, strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT1, strAddr, _countof(strAddr)) && GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uAddr = _tcstoul(strAddr, &endptr, 16);
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				if ((uAddr % m_eBlock) || (uLength % m_eBlock))
					AtlMessageBox(m_hWnd, L"Address and length must be an integer multiple of erase block.");
				else
				{
					const HRESULT hr = Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_ERASE, uAddr, uLength, NULL);
					if (FAILED(hr))
					{
						wchar_t strText[256];
						swprintf(strText, L"Erase failed, hr = 0x%08x", hr);
						AtlMessageBox(m_hWnd, strText, MB_OK | MB_ICONERROR);
					}
					else
					{
						CWaitDlg dlg(m_hcam);
						dlg.DoModal();
					}
				}
			}
		}
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CUARTDlg : public CDialogImpl<CUARTDlg>
{
	HToupcam	m_hcam;
	BEGIN_MSG_MAP(CUARTDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDC_BUTTON1, BN_CLICKED, OnButton1)
		COMMAND_HANDLER(IDC_BUTTON2, BN_CLICKED, OnButton2)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
	END_MSG_MAP()
public:
	enum { IDD = IDD_UART };
	CUARTDlg(HToupcam hcam)
		: m_hcam(hcam)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());
		return TRUE;
	}

	LRESULT OnButton1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strLength[64] = { 0 };
		if (GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)))
		{
			wchar_t* endptr = NULL;
			const unsigned uLength = _tcstoul(strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
				HRESULT hr = Toupcam_read_UART(m_hcam, tmpBuffer, uLength);
				if (FAILED(hr))
					AtlMessageBox(m_hWnd, L"Failed to read UART.");
				else if (0 == hr)
					AtlMessageBox(m_hWnd, L"Read UART, 0 byte.");
				else if (hr > 0)
				{
					std::wstringstream wstr;
					wstr << L"UART: length = " << hr << L", data = ";
					for (int i = 0; i < hr; ++i)
						wstr << std::hex << std::setw(2) << std::setfill((wchar_t)'0') << tmpBuffer[i] << L" ";
					AtlMessageBox(m_hWnd, wstr.str().c_str());
				}
			}
		}
		return 0;
	}

	LRESULT OnButton2(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		wchar_t strLength[64] = { 0 }, strData[1024] = { 0 };
		if (GetDlgItemText(IDC_EDIT2, strLength, _countof(strLength)) && GetDlgItemText(IDC_EDIT3, strData, _countof(strData)))
		{
			wchar_t* endptr = NULL;
			unsigned uLength = _tcstoul((LPCTSTR)strLength, &endptr, 16);
			if (uLength)
			{
				unsigned char* tmpBuffer = (unsigned char*)alloca(uLength);
				memset(tmpBuffer, 0, uLength);
				for (size_t i = 0; i < _countof(strData); i += 2)
				{
					if ('\0' == strData[0])
						break;
					if (strData[i] >= '0' && strData[i] <= '9')
						tmpBuffer[i / 2] = (strData[i] - '0') << 4;
					else if (strData[i] >= 'a' && strData[i] <= 'f')
						tmpBuffer[i / 2] = (strData[i] - 'a' + 10) << 4;
					else if (strData[i] >= 'A' && strData[i] <= 'F')
						tmpBuffer[i / 2] = (strData[i] - 'A' + 10) << 4;
					if (strData[i + 1] >= '0' && strData[i + 1] <= '9')
						tmpBuffer[i / 2] |= (strData[i + 1] - '0');
					else if (strData[i + 1] >= 'a' && strData[i + 1] <= 'f')
						tmpBuffer[i / 2] |= (strData[i + 1] - 'a' + 10);
					else if (strData[i + 1] >= 'A' && strData[i + 1] <= 'F')
						tmpBuffer[i / 2] |= (strData[i + 1] - 'A' + 10);
				}
				HRESULT hr = Toupcam_write_UART(m_hcam, tmpBuffer, uLength);
				wchar_t strMessage[256];
				swprintf(strMessage, L"Write UART, length = %u, result = 0x%08x", uLength, hr);
				AtlMessageBox(m_hWnd, strMessage);
			}
		}
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CIocontrolDlg : public CDialogImpl<CIocontrolDlg>
{
	HToupcam				m_hcam;
	const ToupcamDeviceV2&	m_tdev;

	BEGIN_MSG_MAP(CIocontrolDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_HANDLER(IDCANCEL, BN_CLICKED, OnCancel)
		COMMAND_HANDLER(IDOK, BN_CLICKED, OnOK)
		COMMAND_HANDLER(IDC_COUNTERRESET, BN_CLICKED, OnCounterReset)
		COMMAND_HANDLER(IDC_IOINDEX, CBN_SELENDOK, OnSelchange1)
		COMMAND_HANDLER(IDC_GPIODIR, CBN_SELENDOK, OnSelchange2)
	END_MSG_MAP()
public:
	enum { IDD = IDD_IOCONTROL };
	CIocontrolDlg(HToupcam hcam, const ToupcamDeviceV2& tdev)
	: m_hcam(hcam), m_tdev(tdev)
	{
	}
private:
	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		{
			CComboBox box(GetDlgItem(IDC_IOINDEX));
			box.AddString(L"Isolated input");
			box.AddString(L"Isolated output");
			box.AddString(L"GPIO0");
			box.AddString(L"GPIO1");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_GPIODIR));
			box.AddString(L"Input");
			box.AddString(L"Output");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_IOFORMAT));
			box.AddString(L"Not connected");
			box.AddString(L"Tri-state");
			box.AddString(L"TTL");
			box.AddString(L"LVDS");
			box.AddString(L"RS422");
			box.AddString(L"Opto-coupled");
			box.SetCurSel(5);
		}
		{
			CComboBox box(GetDlgItem(IDC_OUTPUTINVERTER));
			box.AddString(L"No");
			box.AddString(L"Yes");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_INPUTACTIVATION));
			box.AddString(L"Rising edge");
			box.AddString(L"Falling edge");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_TRIGGERSOURCE));
			box.AddString(L"Isolated input");
			box.AddString(L"GPIO0");
			box.AddString(L"GPIO1");
			box.AddString(L"Counter");
			box.AddString(L"PWM");
			box.AddString(L"Software");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_COUNTERSOURCE));
			box.AddString(L"Isolated input");
			box.AddString(L"GPIO0");
			box.AddString(L"GPIO1");
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_PWMSOURCE));
			box.AddString(_T("Isolated input"));
			box.AddString(_T("GPIO0"));
			box.AddString(_T("GPIO1"));
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_OUTPUTMODE));
			box.AddString(_T("Frame Trigger Wait"));
			box.AddString(_T("Exposure Active"));
			box.AddString(_T("Strobe"));
			box.AddString(_T("User Output"));
			box.SetCurSel(0);
		}
		{
			CComboBox box(GetDlgItem(IDC_STROBEDELAYMODE));
			box.AddString(_T("pre-delay"));
			box.AddString(_T("delay"));
			box.SetCurSel(1);
		}
		SetDlgItemInt(IDC_DEBOUNCE_TIME, 0, TRUE);
		SetDlgItemInt(IDC_TRIGGER_DELAY, 0, TRUE);
		SetDlgItemInt(IDC_COUNTER_VALUE, 0, TRUE);
		SetDlgItemInt(IDC_STROBE_DELAY_TIME, 0, TRUE);
		SetDlgItemInt(IDC_STROBE_DURATION, 0, TRUE);
		SetDlgItemInt(IDC_USER_VALUE, 0, TRUE);
		GetDlgItem(IDC_GPIODIR).EnableWindow(FALSE);
		GetDlgItem(IDC_IOFORMAT).EnableWindow(FALSE);
		GetDlgItem(IDC_TRIGGER_DELAY).EnableWindow(TRUE);
		GetDlgItem(IDC_DEBOUNCE_TIME).EnableWindow(TRUE);
		GetDlgItem(IDC_OUTPUTINVERTER).EnableWindow(FALSE);
		GetDlgItem(IDC_OUTPUTMODE).EnableWindow(FALSE);
		return TRUE;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}

	LRESULT OnCounterReset(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_RESETCOUNTER, 0, NULL);
		return 0;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		unsigned index = 0;
		{
			CComboBox box(GetDlgItem(IDC_IOINDEX));
			index = box.GetCurSel();
		}
		{
			CComboBox box(GetDlgItem(IDC_GPIODIR));
			if (0 == box.GetCurSel())
				Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_GPIODIR, 0x00, NULL);
			else
				Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_GPIODIR, 0x01, NULL);
		}
		{
			CComboBox box(GetDlgItem(IDC_OUTPUTINVERTER));
			Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER, box.GetCurSel(), NULL);
		}
		{
			CComboBox box(GetDlgItem(IDC_INPUTACTIVATION));
			Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_INPUTACTIVATION, box.GetCurSel(), NULL);
		}
		{
			CString str;
			GetDlgItemText(IDC_STROBE_DURATION, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_STROBEDURATION, val, NULL);
			}
		}
		{
			CString str;
			GetDlgItemText(IDC_DEBOUNCE_TIME, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_DEBOUNCERTIME, val, NULL);
			}
		}
		{
			CString str;
			GetDlgItemText(IDC_COUNTER_VALUE, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_COUNTERVALUE, val, NULL);
			}
		}
		{
			CComboBox box(GetDlgItem(IDC_OUTPUTMODE));
			Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_OUTPUTMODE, box.GetCurSel(), NULL);
		}
		{
			CString str;
			GetDlgItemText(IDC_USER_VALUE, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_USERVALUE, val, NULL);
			}
		}
		{
			CComboBox box(GetDlgItem(IDC_STROBEDELAYMODE));
			Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_STROBEDELAYMODE, box.GetCurSel(), NULL);
		}
		{
			CString str;
			GetDlgItemText(IDC_STROBE_DELAY_TIME, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_STROBEDELAYTIME, val, NULL);
			}
		}
		{
			CString str;
			GetDlgItemText(IDC_TRIGGER_DELAY, str);
			str.Trim();
			if (!str.IsEmpty())
			{
				const int val = _ttoi((LPCTSTR)str);
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_TRIGGERDELAY, val, NULL);
			}
		}
		{
			CComboBox box(GetDlgItem(IDC_PWMSOURCE));
			Toupcam_IoControl(m_hcam, index, TOUPCAM_IOCONTROLTYPE_SET_PWMSOURCE, box.GetCurSel(), NULL);
		}
		return 0;
	}

	LRESULT OnSelchange1(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CComboBox cbox(GetDlgItem(IDC_IOINDEX));
		int nSel = cbox.GetCurSel();
		if (nSel == 2 || nSel == 3)
			GetDlgItem(IDC_GPIODIR).EnableWindow(TRUE);
		else
			GetDlgItem(IDC_GPIODIR).EnableWindow(FALSE);
		return 0;
	}

	LRESULT OnSelchange2(WORD /*wNotifyCode*/, WORD /*wID*/, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CComboBox cbox(GetDlgItem(IDC_GPIODIR));
		int nSel = cbox.GetCurSel();
		if (nSel == 0)
		{
			GetDlgItem(IDC_TRIGGER_DELAY).EnableWindow(TRUE);
			GetDlgItem(IDC_DEBOUNCE_TIME).EnableWindow(TRUE);
			GetDlgItem(IDC_OUTPUTINVERTER).EnableWindow(FALSE);
			GetDlgItem(IDC_OUTPUTMODE).EnableWindow(FALSE);
		}
		else
		{
			GetDlgItem(IDC_OUTPUTINVERTER).EnableWindow(TRUE);
			GetDlgItem(IDC_OUTPUTMODE).EnableWindow(TRUE);
			GetDlgItem(IDC_TRIGGER_DELAY).EnableWindow(FALSE);
			GetDlgItem(IDC_DEBOUNCE_TIME).EnableWindow(FALSE);
		}
		return 0;
	}
};

class CMainView : public CWindowImpl<CMainView>
{
	CMainFrame*	m_pMainFrame;
	LONG		m_nOldWidth, m_nOldHeight;

	BEGIN_MSG_MAP(CMainView)
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
	CMainView(CMainFrame* pMainFrame)
	: m_pMainFrame(pMainFrame), m_nOldWidth(0), m_nOldHeight(0)
	{
	}
private:
	LRESULT OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnEraseBkgnd(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
	{
		return 1;
	}
};

class CWmvRecord
{
	const LONG				m_lFrameWidth, m_lFrameHeight;
	CComPtr<IWMWriter>		m_spIWMWriter;
public:
	CWmvRecord(LONG lFrameWidth, LONG lFrameHeight)
	: m_lFrameWidth(lFrameWidth), m_lFrameHeight(lFrameHeight)
	{
	}

	BOOL StartRecord(const wchar_t* strFilename, DWORD dwBitrate)
	{
		CComPtr<IWMProfileManager> spIWMProfileManager;
		HRESULT hr = WMCreateProfileManager(&spIWMProfileManager);
		if (FAILED(hr))
			return FALSE;

		CComPtr<IWMCodecInfo> spIWMCodecInfo;
		hr = spIWMProfileManager->QueryInterface(__uuidof(IWMCodecInfo), (void**)&spIWMCodecInfo);
		if (FAILED(hr))
			return FALSE;

		DWORD cCodecs = 0;
        hr = spIWMCodecInfo->GetCodecInfoCount(WMMEDIATYPE_Video, &cCodecs);
		if (FAILED(hr))
			return FALSE;

		CComPtr<IWMStreamConfig> spIWMStreamConfig;
        //
        // Search from the last codec because the last codec usually
        // is the newest codec.
        //
        for (int i = cCodecs - 1; i >= 0; i--)
        {
            DWORD cFormats;
            hr = spIWMCodecInfo->GetCodecFormatCount(WMMEDIATYPE_Video, i, &cFormats);
			if (FAILED(hr))
				break;

            for (DWORD j = 0; j < cFormats; j++)
			{
                hr = spIWMCodecInfo->GetCodecFormat(WMMEDIATYPE_Video, i, j, &spIWMStreamConfig);
				if (FAILED(hr))
					break;

				hr = ConfigureInput(spIWMStreamConfig, dwBitrate);
				if (SUCCEEDED(hr))
					break;
				spIWMStreamConfig = NULL;
			}
			if (spIWMStreamConfig)
				break;
		}
		if (spIWMStreamConfig == NULL)
			return FALSE;

		CComPtr<IWMProfile> spIWMProfile;
		hr = spIWMProfileManager->CreateEmptyProfile(WMT_VER_8_0, &spIWMProfile);
		if (FAILED(hr))
			return FALSE;

		{
			CComPtr<IWMStreamConfig> spIWMStreamConfig2;
			hr = spIWMProfile->CreateNewStream(WMMEDIATYPE_Video, &spIWMStreamConfig2);
			if (FAILED(hr))
				return FALSE;

			WORD wStreamNum = 1;
			hr = spIWMStreamConfig2->GetStreamNumber(&wStreamNum);
			if (FAILED(hr))
				return FALSE;
			
			hr = spIWMStreamConfig->SetStreamNumber(wStreamNum);
			if (FAILED(hr))
				return FALSE;
		}
		spIWMStreamConfig->SetBitrate(dwBitrate);

		hr = spIWMProfile->AddStream(spIWMStreamConfig);
		if (FAILED(hr))
			return FALSE;

		hr = WMCreateWriter(NULL, &m_spIWMWriter);
		if (FAILED(hr))
			return FALSE;

		hr = m_spIWMWriter->SetProfile(spIWMProfile);
		if (FAILED(hr))
			return FALSE;

		hr = SetInputProps();
		if (FAILED(hr))
			return FALSE;

		hr = m_spIWMWriter->SetOutputFilename(strFilename);
		if (FAILED(hr))
			return FALSE;

		hr = m_spIWMWriter->BeginWriting();
		if (FAILED(hr))
			return FALSE;

		{
			CComPtr<IWMWriterAdvanced> spIWMWriterAdvanced;
			m_spIWMWriter->QueryInterface(__uuidof(IWMWriterAdvanced), (void**)&spIWMWriterAdvanced);
			if (spIWMWriterAdvanced)
				spIWMWriterAdvanced->SetLiveSource(TRUE);
		}

		return TRUE;
	}

	void StopRecord()
	{
		if (m_spIWMWriter)
		{
			m_spIWMWriter->Flush();
			m_spIWMWriter->EndWriting();
			m_spIWMWriter = NULL;
		}
	}

	BOOL WriteSample(const void* pData)
	{
		CComPtr<INSSBuffer> spINSSBuffer;
		if (SUCCEEDED(m_spIWMWriter->AllocateSample(TDIBWIDTHBYTES(m_lFrameWidth * 24) * m_lFrameHeight, &spINSSBuffer)))
		{
			BYTE* pBuffer = NULL;
			if (SUCCEEDED(spINSSBuffer->GetBuffer(&pBuffer)))
			{
				memcpy(pBuffer, pData, TDIBWIDTHBYTES(m_lFrameWidth * 24) * m_lFrameHeight);
				spINSSBuffer->SetLength(TDIBWIDTHBYTES(m_lFrameWidth * 24) * m_lFrameHeight);
				QWORD cnsSampleTime = GetTickCount();
				m_spIWMWriter->WriteSample(0, cnsSampleTime * 1000 * 10, 0, spINSSBuffer);
				return TRUE;
			}
		}

		return FALSE;
	}

private:
	HRESULT SetInputProps()
	{
		DWORD dwForamts = 0;
		HRESULT hr = m_spIWMWriter->GetInputFormatCount(0, &dwForamts);
		if (FAILED(hr))
			return hr;

		for (DWORD i = 0; i < dwForamts; ++i)
		{
			CComPtr<IWMInputMediaProps> spIWMInputMediaProps;
			hr = m_spIWMWriter->GetInputFormat(0, i, &spIWMInputMediaProps);
			if (FAILED(hr))
				return hr;

			DWORD cbSize = 0;
			hr = spIWMInputMediaProps->GetMediaType(NULL, &cbSize);
			if (FAILED(hr))
				return hr;

			WM_MEDIA_TYPE* pMediaType = (WM_MEDIA_TYPE*)alloca(cbSize);
			hr = spIWMInputMediaProps->GetMediaType(pMediaType, &cbSize);
			if (FAILED(hr))
				return hr;

			if (pMediaType->subtype == WMMEDIASUBTYPE_RGB24)
			{
				hr = spIWMInputMediaProps->SetMediaType(pMediaType);
				if (FAILED(hr))
					return hr;

				return m_spIWMWriter->SetInputProps(0, spIWMInputMediaProps);
			}
		}

		return E_FAIL;
	}

	HRESULT ConfigureInput(CComPtr<IWMStreamConfig>& spIWMStreamConfig, DWORD dwBitRate)
	{
		CComPtr<IWMVideoMediaProps> spIWMVideoMediaProps;
		HRESULT hr = spIWMStreamConfig->QueryInterface(__uuidof(IWMVideoMediaProps), (void**)&spIWMVideoMediaProps);
		if (FAILED(hr))
			return hr;

		DWORD cbMT = 0;
		hr = spIWMVideoMediaProps->GetMediaType(NULL, &cbMT);
		if (FAILED(hr))
			return hr;

		// Allocate memory for the media type structure.
		WM_MEDIA_TYPE* pType = (WM_MEDIA_TYPE*)alloca(cbMT);
		// Get the media type structure.
		hr = spIWMVideoMediaProps->GetMediaType(pType, &cbMT);
		if (FAILED(hr) || (pType->formattype != WMFORMAT_VideoInfo) || (NULL == pType->pbFormat))
			return E_FAIL;
		
		bool bFound = false;
		// First set pointers to the video structures.
		WMVIDEOINFOHEADER* pVidHdr = (WMVIDEOINFOHEADER*)pType->pbFormat;
		{
			static const DWORD FourCC[] = {
				MAKEFOURCC('W', 'M', 'V', '3'),
				MAKEFOURCC('W', 'M', 'V', '2'),
				MAKEFOURCC('W', 'M', 'V', '1')
			};
			for (size_t i = 0; i < _countof(FourCC); ++i)
			{
				if (FourCC[i] == pVidHdr->bmiHeader.biCompression)
				{
					bFound = true;
					break;
				}
			}
		}
		if (!bFound)
			return E_FAIL;

		pVidHdr->dwBitRate = dwBitRate;
		pVidHdr->rcSource.right = m_lFrameWidth;
		pVidHdr->rcSource.bottom = m_lFrameHeight;
		pVidHdr->rcTarget.right = m_lFrameWidth;
		pVidHdr->rcTarget.bottom = m_lFrameHeight;

		BITMAPINFOHEADER* pbmi = &pVidHdr->bmiHeader;
		pbmi->biWidth  = m_lFrameWidth;
		pbmi->biHeight = m_lFrameHeight;
    
		// Stride = (width * bytes/pixel), rounded to the next DWORD boundary.
		LONG lStride = (m_lFrameWidth * (pbmi->biBitCount / 8) + 3) & ~3;

		// Image size = stride * height.
		pbmi->biSizeImage = m_lFrameHeight * lStride;

		// Apply the adjusted type to the video input.
		hr = spIWMVideoMediaProps->SetMediaType(pType);
		if (FAILED(hr))
			return hr;

		/* you can change this quality */
		spIWMVideoMediaProps->SetQuality(100);
		return hr;
	}
};

class CMainFrame : public CFrameWindowImpl<CMainFrame>, public CUpdateUI<CMainFrame>
{
	HToupcam		m_hcam;
	CMainView		m_view;
	ToupcamDeviceV2	m_arrDev[TOUPCAM_MAX], m_dev;
	BOOL			m_bPaused;
	int				m_nSnapType; // 0-> not snaping, 1 -> single snap, 2 -> multiple snap
	unsigned		m_nSnapSeq;
	unsigned		m_nSnapFile;

	wchar_t			m_szFilePath[MAX_PATH];

	CWmvRecord*		m_pWmvRecord;
	BYTE*			m_pData;
	BITMAPINFOHEADER	m_header;

	bool			m_bTriggerMode;
	typedef enum {
		eTriggerNumber,
		eTriggerLoop
	} eTriggerType;
	eTriggerType	m_eTriggerType;
	unsigned short	m_nTriggerNumber;

	unsigned		m_xRoiOffset, m_yRoiOffset, m_xRoiWidth, m_yRoiHeight;

	BEGIN_MSG_MAP_EX(CMainFrame)
		MSG_WM_CREATE(OnCreate)
		MESSAGE_HANDLER(WM_DESTROY, OnWmDestroy)
		MESSAGE_HANDLER(MSG_CAMEVENT, OnMsgCamEvent)
		MESSAGE_HANDLER(MSG_CAMENUM, OnMsgCamEnum)
		MSG_WM_TIMER(OnTimer)
		MSG_WM_DEVICECHANGE(OnWmDeviceChange)
		COMMAND_RANGE_HANDLER_EX(ID_DEVICE_DEVICE0, ID_DEVICE_DEVICEF, OnOpenDevice)
		COMMAND_RANGE_HANDLER_EX(ID_PREVIEW_RESOLUTION0, ID_PREVIEW_RESOLUTION4, OnPreviewResolution)
		COMMAND_RANGE_HANDLER_EX(ID_SNAP_RESOLUTION0, ID_SNAP_RESOLUTION4, OnSnapResolution)
		COMMAND_RANGE_HANDLER_EX(ID_SNAPN_RESOLUTION0, ID_SNAPN_RESOLUTION4, OnSnapnResolution)
		COMMAND_RANGE_HANDLER_EX(ID_TESTPATTERN0, ID_TESTPATTERN3, OnTestPattern)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_WHITEBALANCE, OnWhiteBalance)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_AUTOEXPOSURE, OnAutoExposure)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_VERTICALFLIP, OnVerticalFlip)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_HORIZONTALFLIP, OnHorizontalFlip)
		COMMAND_ID_HANDLER_EX(ID_ACTION_PAUSE, OnPause)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_EXPOSURETIME, OnExposureTime)
		COMMAND_ID_HANDLER_EX(ID_ACTION_STARTRECORD, OnStartRecord)
		COMMAND_ID_HANDLER_EX(ID_ACTION_STOPRECORD, OnStopRecord)
		COMMAND_ID_HANDLER_EX(ID_ACTION_LED, OnLed)
		COMMAND_ID_HANDLER_EX(ID_PIXELFORMAT, OnPixelFormat)
		COMMAND_ID_HANDLER_EX(ID_TECTARGET, OnTECTarget)
		COMMAND_ID_HANDLER_EX(ID_ACTION_EEPROM, OnEEPROM)
		COMMAND_ID_HANDLER_EX(ID_ACTION_FLASH, OnFlash)
		COMMAND_ID_HANDLER_EX(ID_ACTION_UART, OnUART)
		COMMAND_ID_HANDLER_EX(ID_ACTION_FWVER, OnFwVer)
		COMMAND_ID_HANDLER_EX(ID_ACTION_HWVER, OnHwVer)
		COMMAND_ID_HANDLER_EX(ID_ACTION_FPGAVER, OnFpgaVer)
		COMMAND_ID_HANDLER_EX(ID_ACTION_PRODUCTIONDATE, OnProductionDate)
		COMMAND_ID_HANDLER_EX(ID_ACTION_SN, OnSn)
		COMMAND_ID_HANDLER_EX(ID_ACTION_RAWFORMAT, OnRawformat)
		COMMAND_ID_HANDLER_EX(ID_ACTION_ROI, OnRoi)
		COMMAND_ID_HANDLER_EX(ID_TRIGGER_MODE, OnTriggerMode)
		COMMAND_ID_HANDLER_EX(ID_TRIGGER_TRIGGER, OnTriggerTrigger)
		COMMAND_ID_HANDLER_EX(ID_TRIGGER_NUMBER, OnTriggerNumber)
		COMMAND_ID_HANDLER_EX(ID_TRIGGER_IOCONFIG, OnIoControl)
		COMMAND_ID_HANDLER_EX(ID_MAXAE, OnMaxAE)
		COMMAND_ID_HANDLER_EX(ID_TRIGGER_LOOP, OnTriggerLoop)
		COMMAND_ID_HANDLER_EX(ID_SPEED, OnSpeed)
		CHAIN_MSG_MAP(CUpdateUI<CMainFrame>)
		CHAIN_MSG_MAP(CFrameWindowImpl<CMainFrame>)
	END_MSG_MAP()

	DECLARE_FRAME_WND_CLASS(NULL, IDR_MAIN);

	BEGIN_UPDATE_UI_MAP(CMainFrame)
		UPDATE_ELEMENT(ID_CONFIG_WHITEBALANCE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_CONFIG_AUTOEXPOSURE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_CONFIG_VERTICALFLIP, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_CONFIG_HORIZONTALFLIP, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_STARTRECORD, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_STOPRECORD, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_PAUSE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_LED, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PIXELFORMAT, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TECTARGET, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SPEED, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_EEPROM, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_FLASH, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_UART, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_FWVER, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_HWVER, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_FPGAVER, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TRIGGER_IOCONFIG, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_PRODUCTIONDATE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_SN, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_ACTION_RAWFORMAT, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_CONFIG_EXPOSURETIME, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PREVIEW_RESOLUTION0, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PREVIEW_RESOLUTION1, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PREVIEW_RESOLUTION2, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PREVIEW_RESOLUTION3, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_PREVIEW_RESOLUTION4, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAP_RESOLUTION0, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAP_RESOLUTION1, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAP_RESOLUTION2, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAP_RESOLUTION3, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAP_RESOLUTION4, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAPN_RESOLUTION0, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAPN_RESOLUTION1, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAPN_RESOLUTION2, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAPN_RESOLUTION3, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_SNAPN_RESOLUTION4, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TESTPATTERN0, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TESTPATTERN1, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TESTPATTERN2, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TESTPATTERN3, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TRIGGER_MODE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TRIGGER_TRIGGER, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_MAXAE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_TRIGGER_LOOP, UPDUI_MENUPOPUP)
	END_UPDATE_UI_MAP()
public:
	CMainFrame()
	: m_hcam(NULL), m_bPaused(FALSE), m_nSnapType(0), m_nSnapSeq(0), m_nSnapFile(0), m_pWmvRecord(NULL), m_pData(NULL), m_view(this)
	{
		m_bTriggerMode = false;
		m_nTriggerNumber = 1;
		m_eTriggerType = eTriggerNumber;

		memset(m_arrDev, 0, sizeof(m_arrDev));
		memset(m_szFilePath, 0, sizeof(m_szFilePath));
		
		memset(&m_header, 0, sizeof(m_header));
		m_header.biSize = sizeof(BITMAPINFOHEADER);
		m_header.biPlanes = 1;
		m_header.biBitCount = 24;

		m_xRoiOffset = m_yRoiOffset = m_xRoiWidth = m_yRoiHeight = 0;
	}

	bool GetData(BITMAPINFOHEADER** pHeader, BYTE** pData)
	{
		if (m_pData)
		{
			*pData = m_pData;
			*pHeader = &m_header;
			return true;
		}

		return false;
	}
private:
	LRESULT OnMsgCamEvent(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		switch (wParam)
		{
		case TOUPCAM_EVENT_ERROR:
		case TOUPCAM_EVENT_NOFRAMETIMEOUT:
		case TOUPCAM_EVENT_NOPACKETTIMEOUT:
			OnEventError();
			break;
		case TOUPCAM_EVENT_DISCONNECTED:
			OnEventDisconnected();
			break;
		case TOUPCAM_EVENT_EXPOSURE:
			OnEventExpo();
			break;
		case TOUPCAM_EVENT_TEMPTINT:
			OnEventTemptint();
			break;
		case TOUPCAM_EVENT_IMAGE:
			OnEventImage();
			if (eTriggerLoop == m_eTriggerType)
				Toupcam_Trigger(m_hcam, 1);
			break;
		case TOUPCAM_EVENT_STILLIMAGE:
			OnEventSnap();
			break;
		}
		return 0;
	}

	void OnTimer(UINT_PTR nIDEvent)
	{
		if (1 == nIDEvent)
			UpdateFrameText();
	}

	BOOL OnWmDeviceChange(UINT nEventType, DWORD_PTR dwData)
	{
		if ((DBT_DEVNODES_CHANGED == nEventType) || (DBT_DEVICEARRIVAL == nEventType) || (DBT_DEVICEREMOVECOMPLETE == nEventType))
			PostMessage(MSG_CAMENUM);
		return TRUE;
	}

	LRESULT OnMsgCamEnum(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		EnumCamera();
		return 0;
	}

	void EnumCamera()
	{
		CMenuHandle menu = GetMenu();
		CMenuHandle submenu = menu.GetSubMenu(0);
		while (submenu.GetMenuItemCount() > 0)
			submenu.RemoveMenu(submenu.GetMenuItemCount() - 1, MF_BYPOSITION);

		const unsigned cnt = Toupcam_EnumV2(m_arrDev);
		if (0 == cnt)
			submenu.AppendMenu(MF_GRAYED | MF_STRING, ID_DEVICE_DEVICE0, L"No Device");
		else
		{
			for (unsigned i = 0; i < cnt; ++i)
				submenu.AppendMenu(MF_STRING, ID_DEVICE_DEVICE0 + i, m_arrDev[i].displayname);
		}
	}

	static void __stdcall GigeHotplug(void* ctxHotPlug)
	{
		HWND hWnd = (HWND)ctxHotPlug;
		if (::IsWindow(hWnd))
			::PostMessage(hWnd, MSG_CAMENUM, 0, 0);
	}

	int OnCreate(LPCREATESTRUCT /*lpCreateStruct*/)
	{
		Toupcam_GigeEnable(GigeHotplug, m_hWnd);
		EnumCamera();
		CreateSimpleStatusBar();

		{
			int iWidth[] = { 150, 450, 650, 850, -1 };
			CStatusBarCtrl statusbar(m_hWndStatusBar);
			statusbar.SetParts(_countof(iWidth), iWidth);
		}

		m_hWndClient = m_view.Create(m_hWnd, rcDefault, NULL, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN, WS_EX_CLIENTEDGE);
		
		OnDeviceChanged();
		SetTimer(1, 1000);
		return 0;
	}

	void OnWhiteBalance(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
			Toupcam_AwbOnce(m_hcam, NULL, NULL);
	}

	void OnAutoExposure(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			int bAutoExposure = 0;
			if (SUCCEEDED(Toupcam_get_AutoExpoEnable(m_hcam, &bAutoExposure)))
			{
				bAutoExposure = !bAutoExposure;
				Toupcam_put_AutoExpoEnable(m_hcam, bAutoExposure);
				UISetCheck(ID_CONFIG_AUTOEXPOSURE, bAutoExposure ? 1 : 0);
				UIEnable(ID_CONFIG_EXPOSURETIME, !bAutoExposure);
			}
		}
	}

	void OnVerticalFlip(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			BOOL b = FALSE;
			if (SUCCEEDED(Toupcam_get_VFlip(m_hcam, &b)))
			{
				b = !b;
				Toupcam_put_VFlip(m_hcam, b);
				UISetCheck(ID_CONFIG_VERTICALFLIP, b ? 1 : 0);
			}
		}
	}

	void OnHorizontalFlip(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			BOOL b = FALSE;
			if (SUCCEEDED(Toupcam_get_HFlip(m_hcam, &b)))
			{
				b = !b;
				Toupcam_put_HFlip(m_hcam, b);
				UISetCheck(ID_CONFIG_HORIZONTALFLIP, b ? 1 : 0);
			}
		}
	}

	void OnPause(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			m_bPaused = !m_bPaused;
			Toupcam_Pause(m_hcam, m_bPaused);
			
			UISetCheck(ID_ACTION_PAUSE, m_bPaused ? 1 : 0);
			UIEnable(ID_ACTION_STARTRECORD, !m_bPaused);
		}
	}

	void OnExposureTime(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CExposureTimeDlg dlg(m_hcam);
			if (IDOK == dlg.DoModal())
				UpdateExposureTimeText();
		}
	}

	void OnMaxAE(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CMaxAEDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}

	void OnLed(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CLedDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}

	void OnPixelFormat(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CPixelFormatDlg dlg(m_dev, m_hcam);
			dlg.DoModal();
		}
	}

	void OnTECTarget(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam && (m_dev.model->flag & TOUPCAM_FLAG_TEC_ONOFF)) // support set the tec target
		{
			CTECTargetDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}

	void OnSpeed(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CSpeedDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}

	void OnEEPROM(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CEEPROMDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}
	

	void OnFlash(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			if (Toupcam_rwc_Flash(m_hcam, TOUPCAM_FLASH_SIZE, 0, 0, NULL) <= 0)
				AtlMessageBox(m_hWnd, L"No Flash available");
			else
			{
				CFlashDlg dlg(m_hcam);
				dlg.DoModal();
			}
		}
	}

	void OnUART(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CUARTDlg dlg(m_hcam);
			dlg.DoModal();
		}
	}

	void OnRoi(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CRoiDlg dlg;
			Toupcam_get_Roi(m_hcam, &dlg.xOffset_, &dlg.yOffset_, &dlg.xWidth_, &dlg.yHeight_);
			if (IDOK == dlg.DoModal())
			{
				if (SUCCEEDED(Toupcam_put_Roi(m_hcam, dlg.xOffset_, dlg.yOffset_, dlg.xWidth_, dlg.yHeight_)))
				{
					Toupcam_get_Roi(m_hcam, NULL, NULL, (unsigned*)&m_header.biWidth, (unsigned*)&m_header.biHeight);
					m_header.biSizeImage = TDIBWIDTHBYTES(m_header.biWidth * m_header.biBitCount) * m_header.biHeight;
					UpdateResolutionText();
				}
			}
		}
		else
		{
			CRoiDlg dlg;
			dlg.xOffset_ = m_xRoiOffset;
			dlg.yOffset_ = m_yRoiOffset;
			dlg.xWidth_ = m_xRoiWidth;
			dlg.yHeight_ = m_yRoiHeight;
			if (IDOK == dlg.DoModal())
			{
				m_xRoiOffset = dlg.xOffset_;
				m_yRoiOffset = dlg.yOffset_;
				m_xRoiWidth = dlg.xWidth_;
				m_yRoiHeight = dlg.yHeight_;
			}
		}
	}

	void OnFwVer(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		char ver[16] = { 0 };
		if (SUCCEEDED(Toupcam_get_FwVersion(m_hcam, ver)))
		{
			CA2T a2t(ver);
			AtlMessageBox(m_hWnd, a2t.m_psz, L"FwVer");
		}
	}

	void OnHwVer(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		char ver[16] = { 0 };
		if (SUCCEEDED(Toupcam_get_HwVersion(m_hcam, ver)))
		{
			CA2T a2t(ver);
			AtlMessageBox(m_hWnd, a2t.m_psz, L"HwVer");
		}
	}

	void OnIoControl(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			if (m_dev.model->ioctrol <= 0)
				AtlMessageBox(m_hWnd, L"No IoControl");
			else
			{
				CIocontrolDlg dlg(m_hcam, m_dev);
				dlg.DoModal();
			}
		}
	}

	void OnFpgaVer(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		char ver[16] = { 0 };
		if (SUCCEEDED(Toupcam_get_FpgaVersion(m_hcam, ver)))
		{
			CA2T a2t(ver);
			AtlMessageBox(m_hWnd, a2t.m_psz, L"FPGAVer");
		}
	}

	void OnTestPattern(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		if (NULL == m_hcam)
			return;
		int val = nID - ID_TESTPATTERN0;
		if (val)
			val = val * 2 + 1;
		Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TESTPATTERN, val);
	}

	void OnProductionDate(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		char pdate[10] = { 0 };
		if (SUCCEEDED(Toupcam_get_ProductionDate(m_hcam, pdate)))
		{
			CA2T a2t(pdate);
			AtlMessageBox(m_hWnd, a2t.m_psz, L"ProductionDate");
		}
	}

	void OnSn(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		char sn[32] = { 0 };
		if (SUCCEEDED(Toupcam_get_SerialNumber(m_hcam, sn)))
		{
			CA2T a2t(sn);
			AtlMessageBox(m_hWnd, a2t.m_psz, L"Serial Number");
		}
	}

	void OnRawformat(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		unsigned nFourCC = 0, bitsperpixel = 0;
		if (SUCCEEDED(Toupcam_get_RawFormat(m_hcam, &nFourCC, &bitsperpixel)))
		{
			wchar_t str[257];
			swprintf(str, L"FourCC:0x%08x, %c%c%c%c\nBits per Pixel: %u", nFourCC, (char)(nFourCC & 0xff), (char)((nFourCC >> 8) & 0xff), (char)((nFourCC >> 16) & 0xff), (char)((nFourCC >> 24) & 0xff), bitsperpixel);
			AtlMessageBox(m_hWnd, str, L"Raw Format");
		}
	}

	void OnTriggerMode(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		m_bTriggerMode = !m_bTriggerMode;
		UISetCheck(ID_TRIGGER_MODE, m_bTriggerMode ? 1 : 0);
		if (m_hcam)
		{
			int val = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, &val);
			if (val == 0)
				val = (m_dev.model->flag & TOUPCAM_FLAG_TRIGGER_EXTERNAL) ? 2 : 1;
			else
				val = 0;
			Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, val);
			UIEnable(ID_ACTION_STOPRECORD, (m_hcam && val) ? TRUE : FALSE);
			UIEnable(ID_TRIGGER_TRIGGER, val ? 1 : 0);
			UIEnable(ID_TRIGGER_LOOP, val ? 1 : 0);
			UIEnable(ID_TRIGGER_IOCONFIG, (2 == val) ? 1 : 0);
		}
	}

	void OnTriggerNumber(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		CTriggerNumberDlg dlg;
		dlg.number_ = m_nTriggerNumber;
		if (IDOK == dlg.DoModal())
		{
			m_nTriggerNumber = dlg.number_;
			if (m_dev.model->ioctrol > 0)
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_BURSTCOUNTER, m_nTriggerNumber, NULL);
		}
	}

	void OnTriggerTrigger(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			int val = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, &val);
			if (val == 2)
			{
				m_eTriggerType = eTriggerNumber;
				Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, 5, NULL);
				const HRESULT hr = Toupcam_Trigger(m_hcam, m_nTriggerNumber);
				if (E_INVALIDARG == hr)
				{
					if (m_nTriggerNumber > 1)
						AtlMessageBox(m_hWnd, L"TOUPCAM_FLAG_TRIGGER_SINGLE: only number = 1 supported");
				}
			}
		}
	}

	void OnTriggerLoop(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			int val = 0;
			Toupcam_get_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, &val);
			if (val == 2)
			{
				if (eTriggerLoop == m_eTriggerType)
				{
					m_eTriggerType = eTriggerNumber;
					UIEnable(ID_TRIGGER_TRIGGER, TRUE);
					Toupcam_Trigger(m_hcam, 0);
				}
				else
				{
					UIEnable(ID_TRIGGER_TRIGGER, FALSE);
					m_eTriggerType = eTriggerLoop;
					Toupcam_IoControl(m_hcam, 0, TOUPCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, 5, NULL);
					Toupcam_Trigger(m_hcam, 1);
				}
			}
		}
	}

	void OnPreviewResolution(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		if (NULL == m_hcam)
			return;

		unsigned eSize = 0;
		if (SUCCEEDED(Toupcam_get_eSize(m_hcam, &eSize)))
		{
			if (eSize != nID - ID_PREVIEW_RESOLUTION0)
			{
				if (SUCCEEDED(Toupcam_Stop(m_hcam)))
				{
					OnStopRecord(0, 0, NULL);

					m_bPaused = FALSE;
					m_nSnapType = 0;
					m_nSnapSeq = 0;
					UISetCheck(ID_ACTION_PAUSE, FALSE);

					Toupcam_put_eSize(m_hcam, nID - ID_PREVIEW_RESOLUTION0);
					for (unsigned i = 0; i < m_dev.model->preview; ++i)
						UISetCheck(ID_PREVIEW_RESOLUTION0 + i, (nID - ID_PREVIEW_RESOLUTION0 == i) ? 1 : 0);
					UpdateSnapMenu();
					if (SUCCEEDED(Toupcam_get_Size(m_hcam, (int*)&m_header.biWidth, (int*)&m_header.biHeight)))
					{
						UpdateResolutionText();
						UpdateStatusText(3, L"");
						UpdateStatusText(4, L"");
						UpdateExposureTimeText();

						m_header.biSizeImage = TDIBWIDTHBYTES(m_header.biWidth * m_header.biBitCount) * m_header.biHeight;
						if (m_pData)
						{
							free(m_pData);
							m_pData = NULL;
						}
						m_pData = (BYTE*)malloc(m_header.biSizeImage);
						if (SUCCEEDED(Toupcam_StartPullModeWithWndMsg(m_hcam, m_hWnd, MSG_CAMEVENT)))
						{
							UIEnable(ID_ACTION_PAUSE, TRUE);
							UIEnable(ID_ACTION_STARTRECORD, TRUE);
							UIEnable(ID_TESTPATTERN0, TRUE);
							UIEnable(ID_TESTPATTERN1, TRUE);
							UIEnable(ID_TESTPATTERN2, TRUE);
							UIEnable(ID_TESTPATTERN3, TRUE);
						}
					}
				}
			}
		}
	}

	void OnSnapResolution(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		if (NULL == m_hcam)
			return;

		CFileDialog dlg(FALSE, L"jpg");
		if (IDOK == dlg.DoModal())
		{
			wcscpy(m_szFilePath, dlg.m_szFileName);
			if (SUCCEEDED(Toupcam_Snap(m_hcam, nID - ID_SNAP_RESOLUTION0)))
			{
				m_nSnapType = 1;
				m_nSnapSeq = 0;
				UpdateSnapMenu();
			}
		}
	}

	void OnSnapnResolution(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		if (NULL == m_hcam)
			return;

		CSnapnDlg dlg;
		if ((IDOK == dlg.DoModal()) && (dlg.m_nNum > 0))
		{
			if (SUCCEEDED(Toupcam_SnapN(m_hcam, nID - ID_SNAPN_RESOLUTION0, dlg.m_nNum)))
			{
				m_nSnapType = 2;
				m_nSnapSeq = dlg.m_nNum;
				UpdateSnapMenu();
			}
		}
	}

	void OnOpenDevice(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		CloseDevice();

		m_header.biWidth = m_header.biHeight = 0;
		m_header.biSizeImage = 0;
		m_bPaused = FALSE;
		m_nSnapType = 0;
		m_nSnapSeq = 0;
		UISetCheck(ID_ACTION_PAUSE, FALSE);
		const int idx = nID - ID_DEVICE_DEVICE0;
		m_hcam = Toupcam_Open(m_arrDev[idx].id);
		if (m_hcam)
		{
			m_dev = m_arrDev[idx];
			/* just to demo put roi befor the camera is started */
			if (m_xRoiWidth && m_yRoiHeight)
			{
				Toupcam_put_Roi(m_hcam, m_xRoiOffset, m_yRoiOffset, m_xRoiWidth, m_yRoiHeight);
				Toupcam_get_Roi(m_hcam, NULL, NULL, (unsigned*)&m_header.biWidth, (unsigned*)&m_header.biHeight);
			}
			else
			{
				Toupcam_get_Size(m_hcam, (int*)&m_header.biWidth, (int*)&m_header.biHeight);
			}

			if (m_bTriggerMode)
			{
				if (m_dev.model->flag & TOUPCAM_FLAG_TRIGGER_EXTERNAL)
					Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, 2);
				else if (m_dev.model->flag & TOUPCAM_FLAG_TRIGGER_EXTERNAL)
					Toupcam_put_Option(m_hcam, TOUPCAM_OPTION_TRIGGER, 1);
			}

			OnDeviceChanged();
			UpdateStatusText(3, L"");
			UpdateStatusText(4, L"");

			if ((m_header.biWidth > 0) && (m_header.biHeight > 0))
			{
				m_header.biSizeImage = TDIBWIDTHBYTES(m_header.biWidth * m_header.biBitCount) * m_header.biHeight;
				m_pData = (BYTE*)malloc(m_header.biSizeImage);
				unsigned eSize = 0;
				if (SUCCEEDED(Toupcam_get_eSize(m_hcam, &eSize)))
				{
					for (unsigned i = 0; i < m_dev.model->preview; ++i)
						UISetCheck(ID_PREVIEW_RESOLUTION0 + i, (eSize == i) ? 1 : 0);
				}
				if (SUCCEEDED(Toupcam_StartPullModeWithWndMsg(m_hcam, m_hWnd, MSG_CAMEVENT)))
				{
					UIEnable(ID_ACTION_PAUSE, TRUE);
					UIEnable(ID_ACTION_STARTRECORD, TRUE);
					UIEnable(ID_TESTPATTERN0, TRUE);
					UIEnable(ID_TESTPATTERN1, TRUE);
					UIEnable(ID_TESTPATTERN2, TRUE);
					UIEnable(ID_TESTPATTERN3, TRUE);
				}
			}
		}
	}

	void OnStartRecord(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		CFileDialog dlg(FALSE, L"wmv");
		if (IDOK == dlg.DoModal())
		{
			StopRecord();

			DWORD dwBitrate = 4 * 1024 * 1024; /* bitrate, you can change this setting */
			CWmvRecord* pWmvRecord = new CWmvRecord(m_header.biWidth, m_header.biHeight);
			if (pWmvRecord->StartRecord(dlg.m_szFileName, dwBitrate))
			{
				m_pWmvRecord = pWmvRecord;
				UIEnable(ID_ACTION_STARTRECORD, FALSE);
				UIEnable(ID_ACTION_STOPRECORD, TRUE);
			}
			else
			{
				delete pWmvRecord;
			}
		}
	}

	void OnStopRecord(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		StopRecord();

		UIEnable(ID_ACTION_STARTRECORD, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_STOPRECORD, FALSE);
	}

	void OnEventImage()
	{
		ToupcamFrameInfoV4 info = { 0 };
		HRESULT hr = Toupcam_PullImageV4(m_hcam, m_pData, 0, m_header.biBitCount, 0, &info);
		if (FAILED(hr))
			return;
		if ((info.v3.width != m_header.biWidth) || (info.v3.height != m_header.biHeight))
			return;

		m_view.Invalidate();

		UpdateFrameInfoText(info);
		if (m_pWmvRecord)
			m_pWmvRecord->WriteSample(m_pData);
	}

	void OnEventSnap()
	{
		BITMAPINFOHEADER header = { 0 };
		header.biSize = sizeof(header);
		header.biPlanes = 1;
		header.biBitCount = 24;
		ToupcamFrameInfoV4 info = { 0 };
		HRESULT hr = Toupcam_PullImageV4(m_hcam, NULL, 1, 24, 0, &info); //first, peek the width and height
		if (SUCCEEDED(hr))
		{
			header.biWidth = info.v3.width;
			header.biHeight = info.v3.height;
			header.biSizeImage = TDIBWIDTHBYTES(header.biWidth * header.biBitCount) * header.biHeight;
			void* pSnapData = malloc(header.biSizeImage);
			if (pSnapData)
			{
				hr = Toupcam_PullImageV4(m_hcam, pSnapData, 1, 24, 0, NULL);
				if (SUCCEEDED(hr))
				{
					if (2 == m_nSnapType)
					{
						wchar_t strPath[MAX_PATH];
						swprintf(strPath, L"%04u.jpg", m_nSnapFile++);
						SaveImageByWIC(strPath, pSnapData, &header);
					}
					else
					{
						if (PathMatchSpec(m_szFilePath, L"*.bmp"))
							SaveImageBmp(m_szFilePath, pSnapData, &header);
						else
							SaveImageByWIC(m_szFilePath, pSnapData, &header);
					}
				}

				free(pSnapData);
			}
		}

		if (1 == m_nSnapType)
			m_nSnapType = 0;
		else if (2 == m_nSnapType)
		{
			if (m_nSnapSeq > 0)
			{
				if (--m_nSnapSeq == 0)
					m_nSnapType = 0;
			}
		}
		UpdateSnapMenu();
	}

	LRESULT OnWmDestroy(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
	{
		CloseDevice();

		CFrameWindowImpl<CMainFrame>::OnDestroy(uMsg, wParam, lParam, bHandled);
		return 0;
	}

	void OnEventError()
	{
		CloseDevice();
		AtlMessageBox(m_hWnd, L"Generic error.");
	}

	void OnEventDisconnected()
	{
		CloseDevice();
		AtlMessageBox(m_hWnd, L"Camera disconnect.");
	}

	void OnEventTemptint()
	{
		wchar_t res[128];
		int nTemp = TOUPCAM_TEMP_DEF, nTint = TOUPCAM_TINT_DEF;
		Toupcam_get_TempTint(m_hcam, &nTemp, &nTint);
		swprintf(res, L"Temp = %d, Tint = %d", nTemp, nTint);
		UpdateStatusText(2, res);
	}

	void OnEventExpo()
	{
		wchar_t res[128];
		unsigned nTime = 0;
		unsigned short Gain = 0;
		if (SUCCEEDED(Toupcam_get_ExpoTime(m_hcam, &nTime)) && SUCCEEDED(Toupcam_get_ExpoAGain(m_hcam, &Gain)))
		{
			swprintf(res, L"ExposureTime = %u, Gain = %hu", nTime, Gain);
			UpdateStatusText(1, res);
		}
	}

	void CloseDevice()
	{
		OnStopRecord(0, 0, NULL);

		if (m_hcam)
		{
			Toupcam_Close(m_hcam);
			m_hcam = NULL;

			if (m_pData)
			{
				free(m_pData);
				m_pData = NULL;
			}
		}
		OnDeviceChanged();
	}

	void OnDeviceChanged()
	{
		CMenuHandle menu = GetMenu();
		CMenuHandle submenu = menu.GetSubMenu(1);
		CMenuHandle previewsubmenu = submenu.GetSubMenu(0);
		CMenuHandle snapsubmenu = submenu.GetSubMenu(1);
		CMenuHandle snapnsubmenu = submenu.GetSubMenu(2);
		while (previewsubmenu.GetMenuItemCount() > 0)
			previewsubmenu.RemoveMenu(previewsubmenu.GetMenuItemCount() - 1, MF_BYPOSITION);
		while (snapsubmenu.GetMenuItemCount() > 0)
			snapsubmenu.RemoveMenu(snapsubmenu.GetMenuItemCount() - 1, MF_BYPOSITION);
		while (snapnsubmenu.GetMenuItemCount() > 0)
			snapnsubmenu.RemoveMenu(snapnsubmenu.GetMenuItemCount() - 1, MF_BYPOSITION);

		CStatusBarCtrl statusbar(m_hWndStatusBar);

		if (NULL == m_hcam)
		{
			previewsubmenu.AppendMenu(MF_STRING | MF_GRAYED, ID_PREVIEW_RESOLUTION0, L"Empty");
			snapsubmenu.AppendMenu(MF_STRING | MF_GRAYED, ID_SNAP_RESOLUTION0, L"Empty");
			snapnsubmenu.AppendMenu(MF_STRING | MF_GRAYED, ID_SNAP_RESOLUTION0, L"Empty");
			UIEnable(ID_SNAP_RESOLUTION0, FALSE);
			UIEnable(ID_PREVIEW_RESOLUTION0, FALSE);

			statusbar.SetText(0, L"");
			statusbar.SetText(1, L"");
			statusbar.SetText(2, L"");
			statusbar.SetText(3, L"");
			statusbar.SetText(4, L"");

			UIEnable(ID_CONFIG_EXPOSURETIME, FALSE);
		}
		else
		{
			unsigned eSize = 0;
			Toupcam_get_eSize(m_hcam, &eSize);

			wchar_t res[128];
			for (unsigned i = 0; i < m_dev.model->preview; ++i)
			{
				swprintf(res, L"%u * %u", m_dev.model->res[i].width, m_dev.model->res[i].height);
				previewsubmenu.AppendMenu(MF_STRING, ID_PREVIEW_RESOLUTION0 + i, res);
				snapsubmenu.AppendMenu(MF_STRING, ID_SNAP_RESOLUTION0 + i, res);
				snapnsubmenu.AppendMenu(MF_STRING, ID_SNAPN_RESOLUTION0 + i, res);

				UIEnable(ID_PREVIEW_RESOLUTION0 + i, TRUE);
			}
			UpdateSnapMenu();

			UpdateResolutionText();
			UpdateExposureTimeText();

			int nTemp = TOUPCAM_TEMP_DEF, nTint = TOUPCAM_TINT_DEF;
			if (SUCCEEDED(Toupcam_get_TempTint(m_hcam, &nTemp, &nTint)))
			{
				swprintf(res, L"Temp = %d, Tint = %d", nTemp, nTint);
				statusbar.SetText(2, res);
			}

			BOOL bAutoExposure = TRUE;
			if (SUCCEEDED(Toupcam_get_AutoExpoEnable(m_hcam, &bAutoExposure)))
			{
				UISetCheck(ID_CONFIG_AUTOEXPOSURE, bAutoExposure ? 1 : 0);
				UIEnable(ID_CONFIG_EXPOSURETIME, !bAutoExposure);
			}
		}

		UIEnable(ID_ACTION_PAUSE, FALSE);
		UIEnable(ID_ACTION_STARTRECORD, FALSE);
		UIEnable(ID_ACTION_STOPRECORD, FALSE);
		UIEnable(ID_CONFIG_AUTOEXPOSURE, m_hcam ? TRUE : FALSE);
		UIEnable(ID_CONFIG_HORIZONTALFLIP, m_hcam ? TRUE : FALSE);
		UIEnable(ID_CONFIG_VERTICALFLIP, m_hcam ? TRUE : FALSE);
		UIEnable(ID_CONFIG_WHITEBALANCE, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_LED, m_hcam ? TRUE : FALSE);
		UIEnable(ID_PIXELFORMAT, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_EEPROM, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_FLASH, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_UART, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_FWVER, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_HWVER, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_FPGAVER, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_PRODUCTIONDATE, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_SN, m_hcam ? TRUE : FALSE);
		UIEnable(ID_ACTION_RAWFORMAT, m_hcam ? TRUE : FALSE);
		UISetCheck(ID_ACTION_PAUSE, 0);
		UISetCheck(ID_CONFIG_HORIZONTALFLIP, 0);
		UISetCheck(ID_CONFIG_VERTICALFLIP, 0);
		UIEnable(ID_ACTION_STOPRECORD, m_hcam ? TRUE : FALSE);
		UIEnable(ID_TECTARGET, (m_hcam && (m_dev.model->flag & TOUPCAM_FLAG_TEC_ONOFF)) ? TRUE : FALSE);
		UIEnable(ID_SPEED, m_hcam ? TRUE : FALSE);
		UIEnable(ID_MAXAE, m_hcam ? TRUE : FALSE);

		UIEnable(ID_TRIGGER_NUMBER, m_hcam ? TRUE : FALSE);
		UIEnable(ID_TRIGGER_TRIGGER, FALSE);
		UIEnable(ID_TRIGGER_LOOP, FALSE);
		UIEnable(ID_TRIGGER_IOCONFIG, FALSE);
		UIEnable(ID_TESTPATTERN0, FALSE);
		UIEnable(ID_TESTPATTERN1, FALSE);
		UIEnable(ID_TESTPATTERN2, FALSE);
		UIEnable(ID_TESTPATTERN3, FALSE);
	}

	void UpdateSnapMenu()
	{
		if (m_nSnapType)
		{
			for (unsigned i = 0; i < m_dev.model->preview; ++i)
			{
				UIEnable(ID_SNAP_RESOLUTION0 + i, FALSE);
				UIEnable(ID_SNAPN_RESOLUTION0 + i, FALSE);
			}
			return;
		}

		unsigned eSize = 0;
		if (SUCCEEDED(Toupcam_get_eSize(m_hcam, &eSize)))
		{
			for (unsigned i = 0; i < m_dev.model->preview; ++i)
			{
				if (m_dev.model->still == m_dev.model->preview) /* still capture full supported */
				{
					UIEnable(ID_SNAP_RESOLUTION0 + i, TRUE);
					UIEnable(ID_SNAPN_RESOLUTION0 + i, TRUE);
				}
				else if (0 == m_dev.model->still) /* still capture not supported */
				{
					UIEnable(ID_SNAP_RESOLUTION0 + i, (eSize == i) ? TRUE : FALSE);
					UIEnable(ID_SNAPN_RESOLUTION0 + i, (eSize == i) ? TRUE : FALSE);
				}
				else if (m_dev.model->still < m_dev.model->preview)
				{
					if ((eSize == i) || (i < m_dev.model->still))
					{
						UIEnable(ID_SNAP_RESOLUTION0 + i, TRUE);
						UIEnable(ID_SNAPN_RESOLUTION0 + i, TRUE);
					}
					else
					{
						UIEnable(ID_SNAP_RESOLUTION0 + i, FALSE);
						UIEnable(ID_SNAPN_RESOLUTION0 + i, FALSE);
					}
				}
			}
		}
	}

	void UpdateResolutionText()
	{
		wchar_t res[128];
		unsigned xOffset = 0, yOffset = 0, nWidth = 0, nHeight = 0;
		if (SUCCEEDED(Toupcam_get_Roi(m_hcam, &xOffset, &yOffset, &nWidth, &nHeight)))
		{
			swprintf(res, L"%u, %u, %u * %u", xOffset, yOffset, nWidth, nHeight);
			UpdateStatusText(0, res);
		}
	}

	void UpdateStatusText(int nPane, const wchar_t* str)
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		statusbar.SetText(nPane, str);
	}

	void UpdateFrameText()
	{
		unsigned nFrame = 0, nTime = 0, nTotalFrame = 0;
		if (m_hcam && SUCCEEDED(Toupcam_get_FrameRate(m_hcam, &nFrame, &nTime, &nTotalFrame)))
		{
			wchar_t str[256];
			if (nTime >= 1000)
				swprintf(str, L"total: %u, fps: %.1f", nTotalFrame, nFrame * 1000.0 / nTime);
			else
				swprintf(str, L"total: %u", nTotalFrame);
			UpdateStatusText(3, str);
		}
	}

	void UpdateFrameInfoText(const ToupcamFrameInfoV4& info)
	{
		wchar_t str[256];
		swprintf(str, L"seq: %u, timestamp: %llu", info.v3.seq, info.v3.timestamp);
		UpdateStatusText(4, str);
	}

	void UpdateExposureTimeText()
	{
		wchar_t res[128];
		unsigned nTime = 0;
		unsigned short Gain = 0;
		if (SUCCEEDED(Toupcam_get_ExpoTime(m_hcam, &nTime)) && SUCCEEDED(Toupcam_get_ExpoAGain(m_hcam, &Gain)))
		{
			swprintf(res, L"ExpoTime = %u, Gain = %hu", nTime, Gain);
			UpdateStatusText(1, res);
		}
	}

	/* this is called in the UI thread */
	void StopRecord()
	{
		if (m_pWmvRecord)
		{
			m_pWmvRecord->StopRecord();

			delete m_pWmvRecord;
			m_pWmvRecord = NULL;
		}
	}
};

LRESULT CMainView::OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	CPaintDC dc(m_hWnd);

	RECT rc;
	GetClientRect(&rc);
	BITMAPINFOHEADER* pHeader = NULL;
	BYTE* pData = NULL;
	if (m_pMainFrame->GetData(&pHeader, &pData))
	{
		if ((m_nOldWidth != pHeader->biWidth) || (m_nOldHeight != pHeader->biHeight))
		{
			m_nOldWidth = pHeader->biWidth;
			m_nOldHeight = pHeader->biHeight;
			dc.FillRect(&rc, (HBRUSH)WHITE_BRUSH);
		}
		const int m = dc.SetStretchBltMode(COLORONCOLOR);
		StretchDIBits(dc, rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top, 0, 0, pHeader->biWidth, pHeader->biHeight, pData, (BITMAPINFO*)pHeader, DIB_RGB_COLORS, SRCCOPY);
		dc.SetStretchBltMode(m);
	}
	else
	{
		dc.FillRect(&rc, (HBRUSH)WHITE_BRUSH);
	}

	return 0;
}

static int Run(int nCmdShow = SW_SHOWDEFAULT)
{
	CMessageLoop theLoop;
	_Module.AddMessageLoop(&theLoop);

	CMainFrame frmMain;
	if (frmMain.CreateEx() == NULL)
		return 0;
	frmMain.ShowWindow(nCmdShow);

	int nRet = theLoop.Run();
	_Module.RemoveMessageLoop();
	return nRet;
}

int WINAPI _tWinMain(HINSTANCE hInstance, HINSTANCE /*hPrevInstance*/, LPTSTR /*pCmdLine*/, int nCmdShow)
{
	INITCOMMONCONTROLSEX iccx;
	iccx.dwSize = sizeof(iccx);
	iccx.dwICC = ICC_COOL_CLASSES | ICC_BAR_CLASSES;
	InitCommonControlsEx(&iccx);
	OleInitialize(NULL);

	_Module.Init(NULL, hInstance);
	int nRet = Run(nCmdShow);
	_Module.Term();
	return nRet;
}

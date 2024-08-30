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
#include <mutex>

#define MSG_CAMEVENT	(WM_APP + 1)
#define MSG_CAMIMAGE	(WM_APP + 2)
#define MSG_CAMSNAP		(WM_APP + 3)

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

class CExposureTimeDlg : public CDialogImpl<CExposureTimeDlg>
{
	HToupcam	m_hcam;
public:
	enum { IDD = IDD_EXPOSURETIME };

	CExposureTimeDlg(HToupcam hcam)
	: m_hcam(hcam)
	{
	}

	BEGIN_MSG_MAP(CExposureTimeDlg)
		MESSAGE_HANDLER(WM_INITDIALOG, OnInitDialog)
		COMMAND_ID_HANDLER(IDOK, OnOK)
		COMMAND_ID_HANDLER(IDCANCEL, OnCancel)
	END_MSG_MAP()

	LRESULT OnInitDialog(UINT /*uMsg*/, WPARAM /*wParam*/, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		CenterWindow(GetParent());

		unsigned nMin = 0, nMax = 0, nDef = 0, nTime = 0;
		if (SUCCEEDED(Toupcam_get_ExpTimeRange(m_hcam, &nMin, &nMax, &nDef)))
		{
			CTrackBarCtrl ctrl(GetDlgItem(IDC_SLIDER1));
			ctrl.SetRangeMin(nMin);
			ctrl.SetRangeMax(nMax);

			if (SUCCEEDED(Toupcam_get_ExpoTime(m_hcam, &nTime)))
				ctrl.SetPos(nTime);
		}
		
		return TRUE;
	}

	LRESULT OnOK(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		CTrackBarCtrl ctrl(GetDlgItem(IDC_SLIDER1));
		Toupcam_put_ExpoTime(m_hcam, ctrl.GetPos());

		EndDialog(wID);
		return 0;
	}

	LRESULT OnCancel(WORD /*wNotifyCode*/, WORD wID, HWND /*hWndCtl*/, BOOL& /*bHandled*/)
	{
		EndDialog(wID);
		return 0;
	}
};

class CMainView : public CWindowImpl<CMainView>
{
	CMainFrame*	m_pMainFrame;
public:

	static ATL::CWndClassInfo& GetWndClassInfo()
	{
		static ATL::CWndClassInfo wc =
		{
			{ sizeof(WNDCLASSEX), CS_HREDRAW | CS_VREDRAW, StartWindowProc,
			  0, 0, NULL, NULL, NULL, (HBRUSH)NULL_BRUSH, NULL, NULL, NULL },
			NULL, NULL, IDC_ARROW, TRUE, 0, _T("")
		};
		return wc;
	}

	CMainView(CMainFrame* pMainFrame)
	: m_pMainFrame(pMainFrame)
	{
	}

	BEGIN_MSG_MAP(CMainView)
		MESSAGE_HANDLER(WM_PAINT, OnWmPaint)
		MESSAGE_HANDLER(WM_ERASEBKGND, OnEraseBkgnd)
	END_MSG_MAP()

	LRESULT OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnEraseBkgnd(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
	{
		return 1;
	}
};

class CMainFrame : public CFrameWindowImpl<CMainFrame>, public CUpdateUI<CMainFrame>
{
	HToupcam			m_hcam;
	CMainView			m_view;
	ToupcamDeviceV2		m_dev[TOUPCAM_MAX];
	unsigned			m_nIndex;
	bool				m_bSnap;
	unsigned			m_nFrameCount;
	DWORD				m_dwStartTick, m_dwLastTick;
	
	wchar_t				m_szFilePath[MAX_PATH];
	
	std::mutex			m_mutex;
	BYTE*				m_pData;
	BITMAPINFOHEADER	m_header;
	LONG				m_nOldWidth, m_nOldHeight;
public:
	DECLARE_FRAME_WND_CLASS(NULL, IDR_MAIN)

	BEGIN_MSG_MAP_EX(CMainFrame)
		MSG_WM_CREATE(OnCreate)
		MESSAGE_HANDLER(WM_DESTROY, OnWmDestroy)
		MESSAGE_HANDLER(MSG_CAMEVENT, OnMsgCamEvent)
		MESSAGE_HANDLER(MSG_CAMIMAGE, OnMsgCamImage)
		MESSAGE_HANDLER(MSG_CAMSNAP, OnMsgCamSnap)
		COMMAND_RANGE_HANDLER_EX(ID_DEVICE_DEVICE0, ID_DEVICE_DEVICEF, OnOpenDevice)
		COMMAND_RANGE_HANDLER_EX(ID_PREVIEW_RESOLUTION0, ID_PREVIEW_RESOLUTION4, OnPreviewResolution)
		COMMAND_RANGE_HANDLER_EX(ID_SNAP_RESOLUTION0, ID_SNAP_RESOLUTION4, OnSnapResolution)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_WHITEBALANCE, OnWhiteBalance)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_AUTOEXPOSURE, OnAutoExposure)
		COMMAND_ID_HANDLER_EX(ID_CONFIG_EXPOSURETIME, OnExposureTime)
		CHAIN_MSG_MAP(CUpdateUI<CMainFrame>)
		CHAIN_MSG_MAP(CFrameWindowImpl<CMainFrame>)
	END_MSG_MAP()

	BEGIN_UPDATE_UI_MAP(CMainFrame)
		UPDATE_ELEMENT(ID_CONFIG_WHITEBALANCE, UPDUI_MENUPOPUP)
		UPDATE_ELEMENT(ID_CONFIG_AUTOEXPOSURE, UPDUI_MENUPOPUP)
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
	END_UPDATE_UI_MAP()

	LRESULT OnMsgCamEvent(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		switch (wParam)
		{
		case TOUPCAM_EVENT_ERROR:
		case TOUPCAM_EVENT_NOFRAMETIMEOUT:
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
		default:
			break;
		}
		return 0;
	}

	CMainFrame()
		: m_hcam(NULL), m_nIndex(0), m_bSnap(false), m_nFrameCount(0), m_dwStartTick(0), m_dwLastTick(0), m_pData(NULL), m_view(this), m_nOldWidth(0), m_nOldHeight(0)
	{
		memset(m_dev, 0, sizeof(m_dev));
		memset(m_szFilePath, 0, sizeof(m_szFilePath));

		memset(&m_header, 0, sizeof(m_header));
		m_header.biSize = sizeof(BITMAPINFOHEADER);
		m_header.biPlanes = 1;
		m_header.biBitCount = 24;
	}

	int OnCreate(LPCREATESTRUCT /*lpCreateStruct*/)
	{
		CMenuHandle menu = GetMenu();
		CMenuHandle submenu = menu.GetSubMenu(0);
		while (submenu.GetMenuItemCount() > 0)
			submenu.RemoveMenu(submenu.GetMenuItemCount() - 1, MF_BYPOSITION);

		unsigned cnt = Toupcam_EnumV2(m_dev);
		if (0 == cnt)
			submenu.AppendMenu(MF_GRAYED | MF_STRING, ID_DEVICE_DEVICE0, L"No Device");
		else
		{
			for (unsigned i = 0; i < cnt; ++i)
				submenu.AppendMenu(MF_STRING, ID_DEVICE_DEVICE0 + i, m_dev[i].displayname);
		}

		CreateSimpleStatusBar();
		{
			int iWidth[] = { 150, 400, 600, -1 };
			CStatusBarCtrl statusbar(m_hWndStatusBar);
			statusbar.SetParts(_countof(iWidth), iWidth);
		}

		m_hWndClient = m_view.Create(m_hWnd, rcDefault, NULL, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | WS_CLIPCHILDREN, WS_EX_CLIENTEDGE);

		OnDeviceChanged();
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

	void OnExposureTime(UINT /*uNotifyCode*/, int /*nID*/, HWND /*wndCtl*/)
	{
		if (m_hcam)
		{
			CExposureTimeDlg dlg(m_hcam);
			if (IDOK == dlg.DoModal())
				UpdateExposureTimeText();
		}
	}

	LRESULT OnMsgCamImage(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		++m_nFrameCount;
		if (0 == m_dwStartTick)
			m_dwLastTick = m_dwStartTick = GetTickCount();
		else
			m_dwLastTick = GetTickCount();
		m_view.Invalidate();

		UpdateFrameText();
		return 0;
	}

	LRESULT OnMsgCamSnap(UINT /*uMsg*/, WPARAM wParam, LPARAM /*lParam*/, BOOL& /*bHandled*/)
	{
		m_bSnap = false;
		UpdateSnapMenu();
		return 0;
	}

	void OnDataEvent(bool bSnap)
	{
		if (bSnap)
		{
			ToupcamFrameInfoV4 info = { 0 };
			Toupcam_PullImageV4(m_hcam, NULL, 1, 24, 0, &info);
			BITMAPINFOHEADER header = { 0 };
			header.biSize = sizeof(header);
			header.biPlanes = 1;
			header.biBitCount = 24;
			header.biWidth = info.v3.width;
			header.biHeight = info.v3.height;
			header.biSizeImage = TDIBWIDTHBYTES(header.biWidth * header.biBitCount) * header.biHeight;
			void* pSnapData = malloc(header.biSizeImage);
			if (pSnapData)
			{
				Toupcam_PullImageV4(m_hcam, pSnapData, 1, 24, 0, NULL);
				SaveImageBmp(m_szFilePath, pSnapData, &header);

				free(pSnapData);
			}
			PostMessage(MSG_CAMSNAP);
		}
		else
		{
			{
				std::lock_guard<std::mutex> lock(m_mutex);
				Toupcam_PullImageV4(m_hcam, m_pData, 0, 24, 0, NULL);
			}
			PostMessage(MSG_CAMIMAGE);
		}
	}

	static void __stdcall StaticOnEventCallback(unsigned nEvent, void* pCallbackCtx)
	{
		CMainFrame* pThis = (CMainFrame*)pCallbackCtx;
		switch (nEvent)
		{
		case TOUPCAM_EVENT_IMAGE:
			pThis->OnDataEvent(false);
			break;
		case TOUPCAM_EVENT_STILLIMAGE:
			pThis->OnDataEvent(true);
			break;
		default:
			pThis->PostMessage(MSG_CAMEVENT, nEvent);
			break;
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
					m_nFrameCount = 0;
					m_bSnap = false;
					m_dwStartTick = m_dwLastTick = 0;
					m_nOldWidth = m_nOldHeight = 0;

					Toupcam_put_eSize(m_hcam, nID - ID_PREVIEW_RESOLUTION0);
					for (unsigned i = 0; i < m_dev[m_nIndex].model->preview; ++i)
						UISetCheck(ID_PREVIEW_RESOLUTION0 + i, (nID - ID_PREVIEW_RESOLUTION0 == i) ? 1 : 0);
					UpdateSnapMenu();
					if (SUCCEEDED(Toupcam_get_Size(m_hcam, (int*)&m_header.biWidth, (int*)&m_header.biHeight)))
					{
						UpdateResolutionText();
						UpdateFrameText(L"");
						UpdateExposureTimeText();

						m_header.biSizeImage = TDIBWIDTHBYTES(m_header.biWidth * m_header.biBitCount) * m_header.biHeight;
						if (m_pData)
						{
							free(m_pData);
							m_pData = NULL;
						}
						m_pData = (BYTE*)malloc(m_header.biSizeImage);
						Toupcam_StartPullModeWithCallback(m_hcam, StaticOnEventCallback, this);
					}
				}
			}
		}
	}

	void OnSnapResolution(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		if (NULL == m_hcam)
			return;

		CFileDialog dlg(FALSE, L"bmp");
		if (IDOK == dlg.DoModal())
		{
			wcscpy(m_szFilePath, dlg.m_szFileName);
			if (SUCCEEDED(Toupcam_Snap(m_hcam, nID - ID_SNAP_RESOLUTION0)))
			{
				m_bSnap = true;
				UpdateSnapMenu();
			}
		}
	}

	void OnOpenDevice(UINT /*uNotifyCode*/, int nID, HWND /*wndCtl*/)
	{
		CloseDevice();

		m_header.biWidth = m_header.biHeight = 0;
		m_header.biSizeImage = 0;
		m_bSnap = false;
		m_nFrameCount = 0;
		m_dwStartTick = m_dwLastTick = 0;
		m_nOldWidth = m_nOldHeight = 0;
		m_nIndex = nID - ID_DEVICE_DEVICE0;
		m_hcam = Toupcam_Open(m_dev[m_nIndex].id);
		if (m_hcam)
		{
			Toupcam_get_Size(m_hcam, (int*)&m_header.biWidth, (int*)&m_header.biHeight);

			OnDeviceChanged();
			UpdateFrameText(L"");

			if ((m_header.biWidth > 0) && (m_header.biHeight > 0))
			{
				m_header.biSizeImage = TDIBWIDTHBYTES(m_header.biWidth * m_header.biBitCount) * m_header.biHeight;
				m_pData = (BYTE*)malloc(m_header.biSizeImage);
				unsigned eSize = 0;
				if (SUCCEEDED(Toupcam_get_eSize(m_hcam, &eSize)))
				{
					for (unsigned i = 0; i < m_dev[m_nIndex].model->preview; ++i)
						UISetCheck(ID_PREVIEW_RESOLUTION0 + i, (eSize == i) ? 1 : 0);
				}
				Toupcam_StartPullModeWithCallback(m_hcam, StaticOnEventCallback, this);
			}
		}
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
		AtlMessageBox(m_hWnd, _T("Generic error."));
	}

	void OnEventDisconnected()
	{
		CloseDevice();
		AtlMessageBox(m_hWnd, _T("The camera is disconnected, maybe has been pulled out."));
	}

	void OnEventTemptint()
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		wchar_t res[128];
		int nTemp = TOUPCAM_TEMP_DEF, nTint = TOUPCAM_TINT_DEF;
		Toupcam_get_TempTint(m_hcam, &nTemp, &nTint);
		swprintf(res, L"Temp = %d, Tint = %d", nTemp, nTint);
		statusbar.SetText(2, res);
	}

	void OnEventExpo()
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		wchar_t res[128];
		unsigned nTime = 0;
		unsigned short Gain = 0;
		if (SUCCEEDED(Toupcam_get_ExpoTime(m_hcam, &nTime)) && SUCCEEDED(Toupcam_get_ExpoAGain(m_hcam, &Gain)))
		{
			swprintf(res, L"ExposureTime = %u, Gain = %hu", nTime, Gain);
			statusbar.SetText(1, res);
		}
	}

	void Draw()
	{
		CPaintDC dc(m_view.m_hWnd);

		RECT rc;
		m_view.GetClientRect(&rc);
		if (m_pData)
		{
			if ((m_nOldWidth != m_header.biWidth) || (m_nOldHeight != m_header.biHeight))
			{
				m_nOldWidth = m_header.biWidth;
				m_nOldHeight = m_header.biHeight;
				dc.FillRect(&rc, (HBRUSH)WHITE_BRUSH);
			}
			int m = dc.SetStretchBltMode(COLORONCOLOR);
			{
				std::lock_guard<std::mutex> lock(m_mutex);
				StretchDIBits(dc, rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top, 0, 0, m_header.biWidth, m_header.biHeight, m_pData, (BITMAPINFO*)&m_header, DIB_RGB_COLORS, SRCCOPY);
			}
			dc.SetStretchBltMode(m);
		}
		else
		{
			dc.FillRect(&rc, (HBRUSH)WHITE_BRUSH);
		}
	}

private:
	void CloseDevice()
	{
		m_bSnap = false;
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
		while (previewsubmenu.GetMenuItemCount() > 0)
			previewsubmenu.RemoveMenu(previewsubmenu.GetMenuItemCount() - 1, MF_BYPOSITION);
		while (snapsubmenu.GetMenuItemCount() > 0)
			snapsubmenu.RemoveMenu(snapsubmenu.GetMenuItemCount() - 1, MF_BYPOSITION);

		CStatusBarCtrl statusbar(m_hWndStatusBar);

		if (NULL == m_hcam)
		{
			previewsubmenu.AppendMenu(MF_STRING | MF_GRAYED, ID_PREVIEW_RESOLUTION0, L"Empty");
			snapsubmenu.AppendMenu(MF_STRING | MF_GRAYED, ID_SNAP_RESOLUTION0, L"Empty");
			UIEnable(ID_SNAP_RESOLUTION0, FALSE);
			UIEnable(ID_PREVIEW_RESOLUTION0, FALSE);

			statusbar.SetText(0, L"");
			statusbar.SetText(1, L"");
			statusbar.SetText(2, L"");
			statusbar.SetText(3, L"");

			UIEnable(ID_CONFIG_EXPOSURETIME, FALSE);
		}
		else
		{
			unsigned eSize = 0;
			Toupcam_get_eSize(m_hcam, &eSize);

			wchar_t res[128];
			for (unsigned i = 0; i < m_dev[m_nIndex].model->preview; ++i)
			{
				swprintf(res, L"%u * %u", m_dev[m_nIndex].model->res[i].width, m_dev[m_nIndex].model->res[i].height);
				previewsubmenu.AppendMenu(MF_STRING, ID_PREVIEW_RESOLUTION0 + i, res);
				snapsubmenu.AppendMenu(MF_STRING, ID_SNAP_RESOLUTION0 + i, res);

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

		UIEnable(ID_CONFIG_AUTOEXPOSURE, m_hcam ? TRUE : FALSE);
		UIEnable(ID_CONFIG_WHITEBALANCE, m_hcam ? TRUE : FALSE);
	}

	void UpdateSnapMenu()
	{
		if (m_bSnap)
		{
			for (unsigned i = 0; i < m_dev[m_nIndex].model->preview; ++i)
				UIEnable(ID_SNAP_RESOLUTION0 + i, FALSE);
			return;
		}

		unsigned eSize = 0;
		if (SUCCEEDED(Toupcam_get_eSize(m_hcam, &eSize)))
		{
			for (unsigned i = 0; i < m_dev[m_nIndex].model->preview; ++i)
			{
				if (m_dev[m_nIndex].model->still == m_dev[m_nIndex].model->preview) /* still capture full supported */
					UIEnable(ID_SNAP_RESOLUTION0 + i, TRUE);
				else if (0 == m_dev[m_nIndex].model->still) /* still capture not supported */
					UIEnable(ID_SNAP_RESOLUTION0 + i, (eSize == i) ? TRUE : FALSE);
				else if (m_dev[m_nIndex].model->still < m_dev[m_nIndex].model->preview)
				{
					if ((eSize == i) || (i < m_dev[m_nIndex].model->still))
						UIEnable(ID_SNAP_RESOLUTION0 + i, TRUE);
					else
						UIEnable(ID_SNAP_RESOLUTION0 + i, FALSE);
				}
			}
		}
	}

	void UpdateResolutionText()
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		wchar_t res[128];
		unsigned xOffset = 0, yOffset = 0, nWidth = 0, nHeight = 0;
		if (SUCCEEDED(Toupcam_get_Roi(m_hcam, &xOffset, &yOffset, &nWidth, &nHeight)))
		{
			swprintf(res, L"%u, %u, %u * %u", xOffset, yOffset, nWidth, nHeight);
			statusbar.SetText(0, res);
		}
	}

	void UpdateFrameText(const wchar_t* str)
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		statusbar.SetText(3, str);
	}

	void UpdateFrameText()
	{
		wchar_t str[256];
		if (m_dwLastTick != m_dwStartTick)
			swprintf(str, L"%u, %.2f", m_nFrameCount, m_nFrameCount / ((m_dwLastTick - m_dwStartTick) / 1000.0));
		else
			swprintf(str, L"%u", m_nFrameCount);
		UpdateFrameText(str);
	}

	void UpdateExposureTimeText()
	{
		CStatusBarCtrl statusbar(m_hWndStatusBar);
		wchar_t res[128];
		unsigned nTime = 0;
		unsigned short Gain = 0;
		if (SUCCEEDED(Toupcam_get_ExpoTime(m_hcam, &nTime)) && SUCCEEDED(Toupcam_get_ExpoAGain(m_hcam, &Gain)))
		{
			swprintf(res, L"ExposureTime = %u, Gain = %hu", nTime, Gain);
			statusbar.SetText(1, res);
		}
	}
};

LRESULT CMainView::OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	m_pMainFrame->Draw();
	return 0;
}

static int Run(int nCmdShow = SW_SHOWDEFAULT)
{
	CMessageLoop theLoop;
	_Module.AddMessageLoop(&theLoop);

	CMainFrame frmMain;

	if (frmMain.CreateEx() == NULL)
	{
		ATLTRACE(_T("Main window creation failed!\n"));
		return 0;
	}

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
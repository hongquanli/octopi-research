#include <atlbase.h>
#include <atltypes.h>
#include <atlwin.h>
#include <atlapp.h>
#include <atlgdi.h>
#include "graph.h"
#include "dpi.h"

HCURSOR g_curHand2 = nullptr;
HCURSOR g_curHand1 = nullptr;
HCURSOR g_curMove = nullptr;
HCURSOR g_curArrow = nullptr;

static constexpr COLORREF ArrayColor[] = {
	/*Red*/					RGB(255, 0, 0),
	/*Green*/				RGB(0, 255, 0),
	/*Blue*/				RGB(0, 0, 255),
	/*Navy*/				RGB(0, 0, 128),
	/*MediumBlue*/			RGB(0, 0, 205),
	/*DarkGreen*/			RGB(0, 100, 0),
	/*Green*/				RGB(0, 128, 0),
	/*Teal*/				RGB(0, 128, 128),
	/*DarkCyan*/			RGB(0, 139, 139),
	/*DeepSkyBlue*/			RGB(0, 191, 255),
	/*DarkTurquoise*/		RGB(0, 206, 209),
	/*MediumSpringGreen*/	RGB(0, 250, 154),
	/*SpringGreen*/			RGB(0, 255, 127),
	/*Cyan/Aqua*/			RGB(0, 255, 255),
	/*MidNightBlue*/		RGB(25, 25, 112),
	/*DodgerBlue*/			RGB(30, 144, 255),
	/*LightSeaGreen*/		RGB(32, 178, 170),
	/*ForestGreen*/			RGB(34, 139, 34),
	/*SeaGreen*/			RGB(46, 139, 87),
	/*DarkSlateGray*/		RGB(47, 79, 79),
	/*LimeGreen*/			RGB(50, 205, 50),
	/*MediumSeaGreen*/		RGB(60, 179, 113),
	/*Turquoise*/			RGB(64, 224, 208),
	/*RoyalBlue*/			RGB(65, 105, 225),
	/*SteelBlue*/			RGB(70, 130, 180),
	/*DarkSlateBlue*/		RGB(72, 61, 139),
	/*MediumTurquoise*/		RGB(72, 209, 204),
	/*Indigo*/				RGB(75, 0, 130),
	/*DarkOliveGreen*/		RGB(85, 107, 47),
	/*CadetBlue*/			RGB(95, 158, 160),
	/*CornFlowerBlue*/		RGB(100, 149, 237),
	/*MediumAquaMarine*/	RGB(102, 205, 170),
	/*DimGray*/				RGB(105, 105, 105),
	/*SlateBlue*/			RGB(106, 90, 205),
	/*OliveDrab*/			RGB(107, 142, 35),
	/*SlateGray*/			RGB(112, 128, 144),
	/*LightSlateGray*/		RGB(119, 136, 153),
	/*MediumSlateBlue*/		RGB(123, 104, 238),
	/*LawnGreen*/			RGB(124, 252, 0),
	/*ChartReuse*/			RGB(127, 255, 0),
	/*AquaMarine*/			RGB(127, 255, 212),
	/*Maroon*/				RGB(128, 0, 0),
	/*Purple*/				RGB(128, 0, 128),
	/*Olive*/				RGB(128, 128, 0),
	/*SkyBlue*/				RGB(135, 206, 235),
	/*LightSkyBlue*/		RGB(135, 206, 250),
	/*BlueViolet*/			RGB(138, 43, 226),
	/*DarkRed*/				RGB(139, 0, 0),
	/*DarkMagenta*/			RGB(139, 0, 139),
	/*SaddleBrown*/			RGB(139, 69, 19),
	/*DarkSeaGreen*/		RGB(143, 188, 143),
	/*LightGreen*/			RGB(144, 238, 144),
	/*MediumPurple*/		RGB(147, 112, 219),
	/*DarkViolet*/			RGB(148, 0, 211),
	/*PaleGreen*/			RGB(152, 251, 152),
	/*DarkOrchid*/			RGB(153, 50, 204),
	/*YellowGreen*/			RGB(154, 205, 50),
	/*Sienna*/				RGB(160, 82, 45),
	/*Brown*/				RGB(165, 42, 42),
	/*LightBlue*/			RGB(173, 216, 230),
	/*GreenYellow*/			RGB(173, 255, 47),
	/*PaleTurquoise*/		RGB(175, 238, 238),
	/*LightSteelBlue*/		RGB(176, 196, 222),
	/*PowderBlue*/			RGB(176, 224, 230),
	/*FireBrick*/			RGB(178, 34, 34),
	/*DarkGoldenRod*/		RGB(184, 134, 11),
	/*MediumOrchid*/		RGB(186, 85, 211),
	/*RosyBrown*/			RGB(188, 143, 143),
	/*DarkKhaki*/			RGB(189, 183, 107),
	/*MediumVioletRed*/		RGB(199, 21, 133),
	/*IndianRed*/			RGB(205, 92, 92),
	/*Peru*/				RGB(205, 133, 63),
	/*Chocolate*/			RGB(210, 105, 30),
	/*Tan*/					RGB(210, 180, 140),
	/*PaleVioletRed*/		RGB(219, 112, 147),
	/*Thistle*/				RGB(216, 191, 216),
	/*Orchid*/				RGB(218, 112, 214),
	/*GoldenRod*/			RGB(218, 165, 32),
	/*Crimson*/				RGB(220, 20, 60),
	/*Plum*/				RGB(221, 160, 221),
	/*BurlyWood*/			RGB(222, 184, 135),
	/*DarkSalmon*/			RGB(233, 150, 122),
	/*Violet*/				RGB(238, 130, 238),
	/*PaleGoldenRod*/		RGB(238, 232, 170),
	/*LightCoral*/			RGB(240, 128, 128),
	/*Khaki*/				RGB(240, 230, 140),
	/*SandyBrown*/			RGB(244, 164, 96),
	/*Wheat*/				RGB(245, 222, 179),
	/*Salmon*/				RGB(250, 128, 114),
	/*Magenta/Fuchsia*/		RGB(255, 0, 255),
	/*DeepPink*/			RGB(255, 20, 147),
	/*OrangeRed*/			RGB(255, 69, 0),
	/*Tomato*/				RGB(255, 99, 71),
	/*HotPink*/				RGB(255, 105, 180),
	/*Coral*/				RGB(255, 127, 80),
	/*DarkOrange*/			RGB(255, 140, 0),
	/*LightSalmon*/			RGB(255, 160, 122),
	/*Orange*/				RGB(255, 165, 0),
	/*LightPink*/			RGB(255, 182, 193),
	/*Pink*/				RGB(255, 192, 203),
	/*Gold*/				RGB(255, 215, 0),
	/*PeachPuff*/			RGB(255, 218, 185)
};

void DrawArc(CDCHandle* pDC, CPoint point, int direction, int nSize)
{
	switch (direction)
	{
	case 0:
		{
			int x = 0;
			for (int y = point.y; y < (point.y + nSize); y++, x++)
			{
				pDC->MoveTo(point.x - x, y);
				pDC->LineTo(point.x + x, y);
			}
			break;
		}
	case 1:
		{
			int y = nSize;
			for (int x = (point.x - nSize); x < point.x; x++, y--)
			{
				pDC->MoveTo(x, point.y - y);
				pDC->LineTo(x, point.y + y);
			}
			break;
		}
	}
}

int FitScaleY(int a, int b)
{
	int r = g_dpi.UnscaleY(100) * a / b;
	if (r <= 1)
		return 10000;
	if (r <= 2)
		return 5000;
	if (r <= 5)
		return 2000;
	if (r <= 10)
		return 1000;
	if (r <= 20)
		return 500;
	if (r <= 50)
		return 200;
	if (r <= 100)
		return 100;
	if (r <= 200)
		return 50;
	if (r <= 500)
		return 20;
	if (r <= 1000)
		return 10;
	if (r <= 2000)
		return 5;
	if (r <= 5000)
		return 2;
	return 1;
}

CGraph::CGraph(bool bTemp)
: m_bTemp(bTemp), m_xmin(0), m_ymax(0), m_ymin(0), m_ymaxCur(0), m_yminCur(0)
, m_bMove(false)
{
	if (m_bTemp)
	{
		m_ymax = 1000;
		m_ymin = -500;
		m_data.resize(1);
		m_data[0].offset = 0;
		m_data[0].visible = true;
	}
	else
	{
		m_regkey.Create(HKEY_CURRENT_USER, L"Software\\democns");
	}

	m_rect.SetRectEmpty();

	m_oldxmin = m_oldyminCur = m_oldymaxCur = 0;
	m_xDefStep = g_dpi.ScaleX(DEF_XSTEP);
	m_xStepNum = m_xDefStep;
	m_xStepDen = 1;
	m_yStep = -1;

	m_crBackColor	= RGB(255, 255, 255);
	m_crAxisColor	= RGB(0, 0, 0);
	m_crGridColor	= RGB(150, 150, 150);

	m_nLeftMargin
			= m_nTopMargin
			= m_nRightMargin
			= m_nBottomMargin
			= g_dpi.ScaleX(2);
	m_nArcSize = m_nTickSize = g_dpi.ScaleX(5);

	m_xOrg = m_yOrg = m_xTextStep = 0;
	LOGFONT f1 = { 0 };
	NONCLIENTMETRICS ncm = { sizeof(NONCLIENTMETRICS) };
	if (SystemParametersInfo(SPI_GETNONCLIENTMETRICS, 0, &ncm, 0))
	{
		memcpy(&f1, &ncm.lfMenuFont, sizeof(f1));
		f1.lfWeight = FW_NORMAL;
		m_font.CreateFontIndirect(&f1);
	}
	else
	{
		LOGFONT guiFont = { 0 };
		if (GetObject(GetStockObject(DEFAULT_GUI_FONT), sizeof(LOGFONT), &guiFont))
		{
			memcpy(&f1, &guiFont, sizeof(f1));
			m_font.CreateFontIndirect(&f1);
		}
	}

	m_penAxis.CreatePen(PS_SOLID, 0, m_crAxisColor);
	m_penGrid.CreatePen(PS_DOT, 0, m_crGridColor);

	{
		CDCHandle dc(::GetDC(nullptr));
		int s = dc.SaveDC();
		dc.SelectFont(m_font);

		TEXTMETRIC tm = { 0 };
		dc.GetTextMetrics(&tm);
		{
			SIZE s;
			dc.GetTextExtent(_T("65535"), -1, &s);
			m_xTextStep = s.cx * 3 / 2 + g_dpi.ScaleX(8);
			m_xOrg = s.cx + g_dpi.ScaleX(8);
		}
		if (m_xOrg < tm.tmAveCharWidth * 3 + 2)
			m_xOrg = tm.tmAveCharWidth * 3 + 2;
		m_yOrg = tm.tmHeight + tm.tmExternalLeading + 4;

		if (s > 0)
			dc.RestoreDC(s);
		::ReleaseDC(nullptr, dc);
	}
}

void CGraph::Init(int num, int ymax)
{
	if (m_bTemp)
		m_data[0].y.clear();
	else
	{
		if ((num == m_data.size()) && (ymax == m_ymax))
		{
			for (int i = 0; i < num; ++i)
				m_data[i].y.clear();
		}
		else
		{
			m_ymax = ymax;

			m_data.clear();
			m_data.resize(num);

			wchar_t strVisible[128], strOffset[128];
			std::vector<BYTE> vecVisible(m_data.size());
			std::vector<int> vecOffset(m_data.size());
			swprintf(strVisible, L"visible%ux%d", (unsigned)m_data.size(), m_ymax);
			swprintf(strOffset, L"offset%ux%d", (unsigned)m_data.size(), m_ymax);
			DWORD dwVisible = vecVisible.size(), dwOffset = sizeof(int) * vecOffset.size();
			if ((ERROR_SUCCESS == m_regkey.QueryBinaryValue(strVisible, &vecVisible[0], &dwVisible))
				&& (ERROR_SUCCESS == m_regkey.QueryBinaryValue(strOffset, &vecOffset[0], &dwOffset))
				&& (dwVisible == m_data.size()) && (dwOffset == m_data.size() * sizeof(int)))
			{
				for (int i = 0; i < num; ++i)
				{
					m_data[i].offset = vecOffset[i];
					m_data[i].visible = vecVisible[i] ? true : false;
				}
			}
			else
			{
				for (int i = 0; i < num; ++i)
				{
					m_data[i].offset = 0;
					m_data[i].visible = (i < _countof(ArrayColor));
				}
			}
		}
	}

	Zoom11();
}

void CGraph::SaveReg()
{
	ATLASSERT(!m_bTemp);
	std::vector<BYTE> vecVisible(m_data.size());
	std::vector<int> vecOffset(m_data.size());
	for (size_t i = 0; i < m_data.size(); ++i)
	{
		vecVisible[i] = m_data[i].visible;
		vecOffset[i] = m_data[i].offset;
	}
	wchar_t str[128];
	swprintf(str, L"visible%ux%d", (unsigned)m_data.size(), m_ymax);
	m_regkey.SetBinaryValue(str, &vecVisible[0], vecVisible.size());
	swprintf(str, L"offset%ux%d", (unsigned)m_data.size(), m_ymax);
	m_regkey.SetBinaryValue(str, &vecOffset[0], sizeof(int) * vecOffset.size());
}

void CGraph::Set(const std::vector<BYTE>& vecVisible, const std::vector<int>& vecOffset)
{
	ATLASSERT(!m_bTemp);
	for (size_t i = 0; i < m_data.size(); ++i)
	{
		m_data[i].visible = vecVisible[i];
		m_data[i].offset = vecOffset[i];
	}
	SaveReg();
	Invalidate(FALSE);
}

void CGraph::Get(std::vector<BYTE>& vecVisible, std::vector<int>& vecOffset)
{
	ATLASSERT(!m_bTemp);
	for (size_t i = 0; i < m_data.size(); ++i)
	{
		vecVisible[i] = m_data[i].visible;
		vecOffset[i] = m_data[i].offset;
	}
}

void CGraph::AddData(const int arr[])
{
	if (m_bTemp)
		m_data[0].y.push_back(arr[0]);
	else
	{
		for (size_t i = 0; i < m_data.size(); ++i)
			m_data[i].y.push_back(arr[i]);
	}
	if (1 == m_data[0].y.size())
		Zoom11();
	else
	{
		if ((dataNum() - m_xmin) * m_xStepNum / m_xStepDen >= m_rect.Width())
			m_xmin = dataNum() - m_rect.Width() / m_xStepNum / m_xStepDen + 10;
		Invalidate(FALSE);
	}
}

bool CGraph::CanZoomOut(bool bX)const
{
	if (dataNum() <= 0)
		return false;
	if (bX)
		return (dataNum() > 0) && (m_xStepNum * 1024 > m_xStepDen);
	else
		return (dataNum() > 0) && (m_yStep > 0) && ((m_yminCur > m_ymin) || (m_ymaxCur < m_ymax));
}

bool CGraph::CanZoomIn(bool bX)const
{
	if (dataNum() <= 0)
		return false;
	if (bX)
		return (dataNum() > 0) && (m_xStepNum < g_dpi.ScaleX(MAX_XSTEP) * m_xStepDen);
	else
	{
		if ((dataNum() > 0) && (m_yStep > 0))
		{
			int newminY = m_yminCur, newmaxY = m_ymaxCur;
			return CalcZoomInY(newminY, newmaxY);
		}
		return false;
	}
}

void CGraph::OnSizeChanged()
{
	GetClientRect(&m_rect);

	m_rect.left   += m_nLeftMargin;
	m_rect.top    += m_nTopMargin + m_nArcSize;
	m_rect.right  -= m_nRightMargin + m_nArcSize;
	m_rect.bottom -= m_nBottomMargin;

	m_rect.top += m_nArcSize;
	m_rect.right -= m_nArcSize;
	m_rect.left += m_xOrg;
	m_rect.bottom -= m_yOrg;
}

void CGraph::Down()
{
	const int range = m_ymaxCur - m_yminCur;
	int newmax = m_ymaxCur + range / 10;
	if (newmax > m_ymax)
		newmax = m_ymax;
	int newmin = newmax - range;

	if (newmin < m_ymin)
		newmin = m_ymin;
	if (newmax > m_ymax)
		newmax = m_ymax;

	m_yminCur = newmin;
	m_ymaxCur = newmax;

	CalcYStep();
	Invalidate(FALSE);
}

void CGraph::Up()
{
	const int range = m_ymaxCur - m_yminCur;
	int newmin = m_yminCur - range / 10;
	if (newmin < m_ymin)
		newmin = m_ymin;
	int newmax = newmin + range;

	if (newmin < m_ymin)
		newmin = m_ymin;
	if (newmax > m_ymax)
		newmax = m_ymax;

	m_yminCur = newmin;
	m_ymaxCur = newmax;
	
	CalcYStep();
	Invalidate(FALSE);
}

void CGraph::Zoom11()
{
	m_xmin = 0;
	m_yminCur = m_ymin;
	m_ymaxCur = m_ymax;
	m_xStepNum = m_xDefStep;
	m_xStepDen = 1;

	CalcYStep();
	Invalidate(FALSE);
}

bool CGraph::CalcZoomInY(int& newminY, int& newmaxY)const
{
	const int y = (m_ymaxCur + m_yminCur) / 2;
	newminY = m_yminCur + (y - m_yminCur) / 4;
	newmaxY = m_ymaxCur - (m_ymaxCur - y) / 4;
	AdjustZoomY(newminY, newmaxY);
	return (m_yminCur != newminY) || (m_ymaxCur != newmaxY);
}

void CGraph::ZoomIn(bool bX)
{
	if (bX)
	{
		if (m_xStepNum < g_dpi.ScaleX(MAX_XSTEP) * m_xStepDen)
		{
			if (m_xStepDen > 1)
				m_xStepDen /= 2;
			else
				++m_xStepNum;
		}
	}
	else
	{
		int newminY = m_yminCur, newmaxY = m_ymaxCur;
		if (CalcZoomInY(newminY, newmaxY))
		{
			m_yminCur = newminY;
			m_ymaxCur = newmaxY;
			CalcYStep();
		}
	}
	Invalidate(FALSE);
}

void CGraph::ZoomMax(bool bX)
{
	if (bX)
	{
		while (m_xStepNum < g_dpi.ScaleX(MAX_XSTEP) * m_xStepDen)
		{
			if (m_xStepDen > 1)
				m_xStepDen /= 2;
			else
				++m_xStepNum;
		}
	}
	else
	{
		do {
			int newminY = m_yminCur, newmaxY = m_ymaxCur;
			if (!CalcZoomInY(newminY, newmaxY))
				break;
			m_yminCur = newminY;
			m_ymaxCur = newmaxY;
		} while (true);

		CalcYStep();
	}
	Invalidate(FALSE);
}

void CGraph::ZoomOut(bool bX)
{
	if (bX)
	{
		if (m_xStepNum * 1024 > m_xStepDen)
		{
			if (m_xStepNum > 1)
				--m_xStepNum;
			else
				m_xStepDen *= 2;
		}
	}
	else
	{
		int delta = (m_ymaxCur - m_yminCur) / 2;
		if (delta + (m_ymaxCur - m_yminCur) > (m_ymax - m_ymin))
			delta = (m_ymax - m_ymin) - (m_ymaxCur - m_yminCur);
		if (delta < 2)
			delta = 2;
		int newmin = m_yminCur - delta / 2;
		int newmax = m_ymaxCur + delta / 2;
		if (newmin < m_ymin)
			newmin = m_ymin;
		if (newmax > m_ymax)
			newmax = m_ymax;

		AdjustZoomY(newmin, newmax);

		m_yminCur = newmin;
		m_ymaxCur = newmax;
	
		CalcYStep();
	}
	
	Invalidate(FALSE);
}

void CGraph::CalcYStep()
{
	if ((m_rect.Height() > 4) && (m_ymaxCur > m_yminCur))
		m_yStep = FitScaleY(m_rect.Height(), m_ymaxCur - m_yminCur);
	else
		m_yStep = -1;
}

LRESULT CGraph::OnWmSize(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	OnSizeChanged();
	CalcYStep();
	Invalidate();
	return 0;
}

LRESULT CGraph::OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	WTL::CPaintDC dc(m_hWnd);
	CRect rect;
	GetClientRect(&rect);
	if ((rect.Width() > (m_nLeftMargin + m_nRightMargin)) && (rect.Height() > (m_nTopMargin + m_nBottomMargin)))
	{
		CMemoryDC memdc(dc, rect);
		CDCHandle hdc(memdc.m_hDC);
		Draw(hdc, rect);
	}
	else
	{
		dc.FillSolidRect(&rect, m_crBackColor);
	}

	return 0;
}

void CGraph::Draw(CDCHandle& dc, CRect rect)
{
	dc.FillSolidRect(&rect, m_crBackColor);

	rect.left   += m_nLeftMargin;
	rect.top    += m_nTopMargin + m_nArcSize;
	rect.right  -= m_nRightMargin + m_nArcSize;
	rect.bottom -= m_nBottomMargin;

	rect.top += m_nArcSize;
	rect.right -= m_nArcSize;

	const int s = dc.SaveDC();
	if (s)
	{
		dc.SetBkMode(TRANSPARENT);
		dc.SelectFont(m_font);

		const int x = rect.left + m_xOrg;
		const int y = rect.bottom - m_yOrg;
		
		if ((x < rect.right) && (y > rect.top))
		{
#if defined(_DEBUG)
			{
				CRect r = rect;
				r.left += m_xOrg;
				r.bottom -= m_yOrg;
				ATLASSERT(r == m_rect);
			}
#endif
			dc.SelectPen(m_penAxis);

			dc.MoveTo(x, y);
			dc.LineTo(rect.right + m_nArcSize, y);
			DrawArc(&dc, CPoint(rect.right + m_nArcSize, y), 1, m_nArcSize);

			dc.MoveTo(x, y);
			dc.LineTo(x, rect.top - m_nArcSize);
			DrawArc(&dc, CPoint(x, rect.top - m_nArcSize), 0, m_nArcSize);

			dc.SelectFont(m_font);

			if (m_yStep > 0)
			{
				dc.SelectPen(m_penGrid);
				DrawX(&dc, m_rect);
				DrawY(&dc, m_rect);
			}

			if ((dataNum() > 0) && (m_ymaxCur > m_yminCur))
			{
				CRect newrect = m_rect;
				newrect.bottom += 1;
				newrect.right += 1;
				dc.IntersectClipRect(&newrect);

				int clr = 0;
				for (size_t i = 0; i < m_data.size(); ++i)
				{
					if (clr >= _countof(ArrayColor))
						break;
					if (m_data[i].visible)
					{
						WTL::CPen pen;
						pen.CreatePen(PS_SOLID, 0, ArrayColor[clr++]);
						dc.SelectPen(pen);
						DrawLine(&dc, m_data[i]);
					}
				}
			}
		}

		dc.RestoreDC(s);
	}
}

void CGraph::GetPoint(int x, int y, CPoint& pt)const
{
	const int fyRange = m_ymaxCur - m_yminCur;
	pt.x = m_rect.left + (x - m_xmin) * m_xStepNum / m_xStepDen;
	pt.y = (LONG)(m_rect.bottom - (y - m_yminCur) * m_rect.Height() / fyRange);
}

void CGraph::DrawLine(CDCHandle* pDC, const Data& data)const
{
	CPoint pt;
	GetPoint(m_xmin, data.y[m_xmin] + data.offset, pt);
	pDC->MoveTo(pt);
	for (int i = m_xmin + 1; i < dataNum(); ++i)
	{
		GetPoint(i, data.y[i] + data.offset, pt);
		pDC->LineTo(pt);
		if (pt.x > m_rect.right)
			break;
	}
}

void CGraph::DrawX(CDCHandle* pDC, const CRect& rect)const
{
	wchar_t cTxt[32];
	CSize csText;
	int f = 0, xStep = m_xTextStep * m_xStepDen / m_xStepNum, xExp = 0;
	while (xStep > 100)
	{
		xStep /= 10;
		xExp += 1;
	}
	if (xStep <= 2)
		xStep = 2;
	else if (xStep <= 5)
		xStep = 5;
	else if (xStep <= 10)
		xStep = 10;
	else if (xStep <= 20)
		xStep = 20;
	else if (xStep <= 50)
		xStep = 50;
	else
		xStep = 100;
	while (xExp-- > 0)
		xStep *= 10;
	while (1)
	{
		if (f >= m_xmin)
		{
			const int nX = rect.left + (f - m_xmin) * m_xStepNum / m_xStepDen;
			if (nX > rect.right)
				break;
			swprintf(cTxt, _T("%d"), f);
			if (!pDC->GetTextExtent(cTxt, -1, &csText))
				continue;
			CRect crText(nX - csText.cx / 2 - 2,
				rect.bottom + m_nTickSize,
				nX + csText.cx / 2,
				rect.bottom + csText.cy + m_nTickSize);
			pDC->DrawText(cTxt, -1, crText, DT_CENTER | DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX);
			pDC->MoveTo(nX, rect.bottom);
			pDC->LineTo(nX, rect.top);
		}
		
		f += xStep;
	}
}

void CGraph::DrawY(CDCHandle* pDC, const CRect& rect)const
{
	if (m_yStep <= 0 || (m_yminCur >= m_ymaxCur))
		return;

	wchar_t cTxt[64];
	CSize csText;
	int f = m_yminCur;
	if (m_yminCur >= 0)
		f -= m_yminCur % m_yStep;
	else
		f += m_yminCur % m_yStep;
	while (1)
	{
		const int nY = rect.bottom - MulDiv(f - m_yminCur, rect.Height(), m_ymaxCur - m_yminCur);
		if (nY < rect.top)
			break;
		if (nY <= rect.bottom)
		{
			if (m_bTemp)
				swprintf(cTxt, _T("%.1f"), f / 10.0);
			else
				swprintf(cTxt, _T("%d"), f);
			if (!pDC->GetTextExtent(cTxt, -1, &csText))
				continue;
			CRect crText(rect.left - csText.cx - m_nTickSize,
							(LONG)(nY - csText.cy / 2),
							rect.left - m_nTickSize,
							(LONG)(nY + csText.cy / 2));
			pDC->DrawText(cTxt, -1, crText, DT_RIGHT | DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX);
			pDC->MoveTo(rect.left, nY);
			pDC->LineTo(rect.right, nY);
		}

		f += m_yStep;
	}
}

void CGraph::AdjustZoomY(int& yVal1, int& yVal2)const
{
	if (yVal1 > yVal2)
		std::swap(yVal1, yVal2);
	if (abs(yVal1 - yVal2) < (m_ymax - m_ymin) / MAX_ZOOM)
	{
		const int a = ((m_ymax - m_ymin) / MAX_ZOOM - abs(yVal1 - yVal2)) / 2;
		yVal1 -= a;
		yVal2 += a;
	}
	if (yVal1 < m_ymin)
	{
		const int d = -yVal1 + m_ymin;
		yVal1 = m_ymin;
		yVal2 += d;
	}
	if (yVal2 > m_ymax)
	{
		const int d = yVal2 - m_ymax;
		yVal2 = m_ymax;
		yVal2 -= d;
	}
	ATLASSERT(yVal1 < yVal2);
}

void CGraph::Move()
{
	const int x = m_lastPt.x - m_firstPt.x;
	const int y = m_lastPt.y - m_firstPt.y;
	if ((0 == x) && (0 == y))
		return;
	
	if (x)
	{
		m_xmin = m_oldxmin - x * m_xStepDen / m_xStepNum;
		if (m_xmin < 0)
			m_xmin = 0;
		else if (m_xmin + 1 >= dataNum())
			m_xmin = dataNum() - 1;
	}

	if (y)
	{
		const int yRange = m_oldymaxCur - m_oldyminCur;
		const int fy = y * yRange / m_rect.Height();
		if (fy > 0)
		{
			m_ymaxCur = m_oldymaxCur + fy;
			if (m_ymaxCur > m_ymax)
				m_ymaxCur = m_ymax;
			m_yminCur = m_ymaxCur - yRange;
		}
		else if (fy < 0)
		{
			m_yminCur = m_oldyminCur + fy;
			if (m_yminCur < m_ymin)
				m_yminCur = m_ymin;
			m_ymaxCur = m_yminCur + yRange;
		}

		CalcYStep();
	}

	Invalidate(FALSE);
}

LRESULT CGraph::OnWmMousemove(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	if (GetCapture() == m_hWnd)
	{
		m_lastPt.x = GET_X_LPARAM(lParam);
		m_lastPt.y = GET_Y_LPARAM(lParam);
		if (m_lastPt.x < m_rect.left)
			m_lastPt.x = m_rect.left;
		else if (m_lastPt.x > m_rect.right)
			m_lastPt.x = m_rect.right;
		if (m_lastPt.y < m_rect.top)
			m_lastPt.y = m_rect.top;
		else if (m_lastPt.y > m_rect.bottom)
			m_lastPt.y = m_rect.bottom;

		if (m_bMove)
			Move();
		return 0;
	}
	
	bHandled = FALSE;
	return 1;
}

LRESULT CGraph::OnWmCancelmode(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	if (GetCapture() == m_hWnd)
		ReleaseCapture();
	if (m_bMove)
	{
		m_bMove = false;
		Invalidate(FALSE);
	}
	return 0;
}

LRESULT CGraph::OnWmLbuttonup(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	if (GetCapture() == m_hWnd)
	{
		ReleaseCapture();

		if (m_bMove)
		{
			m_bMove = false;
			Move();
			SetCursor(g_curHand1);
		}
		return 0;
	}

	bHandled = FALSE;
	return 1;
}

LRESULT CGraph::OnWmSetcursor(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	const DWORD dwPos = GetMessagePos();
	CPoint pt(GET_X_LPARAM(dwPos), GET_Y_LPARAM(dwPos));
	ScreenToClient(&pt);
	
	if (m_rect.PtInRect(pt))
		SetCursor(m_bMove ? g_curHand1 : g_curHand2);
	else
		SetCursor(g_curArrow);
	return 1;
}

LRESULT CGraph::OnWmLbuttondown(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	const CPoint pt(GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam));
	if (m_rect.PtInRect(pt))
	{
		SetCursor(g_curHand1);

		m_firstPt = m_lastPt = pt;
		m_oldxmin = m_xmin;
		m_oldyminCur = m_yminCur;
		m_oldymaxCur = m_ymaxCur;
		SetCapture();
		m_bMove = true;
	}

	::SetFocus(m_hWnd);
	return 0;
}

LRESULT CGraph::OnWmMousewheel(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled)
{
	if (GET_WHEEL_DELTA_WPARAM(wParam) > 0)
		Down();
	else if (GET_WHEEL_DELTA_WPARAM(wParam) < 0)
		Up();
	else
		bHandled = FALSE;
	return bHandled ? 0 : 1;
}

PBYTE CGraph::GetBitmap()
{
	BYTE* pDIB = nullptr;
	CRect rect;
	GetClientRect(&rect);
	WTL::CClientDC dc(m_hWnd);

	HDC hdc = CreateCompatibleDC(dc);
	ATLASSERT(hdc);

	CDCHandle memdc(hdc);
	WTL::CBitmap bmp;
	bmp.CreateCompatibleBitmap(dc, rect.Width(), rect.Height());
	ATLASSERT(bmp.m_hBitmap);
	HBITMAP hBmpOld = memdc.SelectBitmap(bmp);
	Draw(memdc, rect);
	if (hBmpOld)
	{
		CSize sz;
		if (bmp.GetSize(sz))
		{
			if ((sz.cx > 0) && (sz.cy > 0))
			{
				pDIB = (BYTE*)malloc(sizeof(BITMAPINFOHEADER) + WIDTHBYTES(24 * sz.cx) * sz.cy);
				if (pDIB)
				{
					BITMAPINFOHEADER* info = (BITMAPINFOHEADER*)pDIB;
					memset(info, 0, sizeof(BITMAPINFOHEADER));
					info->biSize = sizeof(BITMAPINFOHEADER);
					info->biWidth = sz.cx;
					info->biHeight = sz.cy;
					info->biPlanes = 1;
					info->biBitCount = 24;
					info->biCompression = BI_RGB;
					if (sz.cy != bmp.GetDIBits(hdc, 0, sz.cy, pDIB + sizeof(BITMAPINFOHEADER), (BITMAPINFO*)pDIB, DIB_RGB_COLORS))
						free(pDIB);
				}
			}
		}

		memdc.SelectBitmap(hBmpOld);
	}

	return pDIB;
}

void CGraph::OnCsv(const wchar_t* szFullPath)const
{
	FILE* fp = _wfopen(szFullPath, L"wt");
	if (fp)
	{
		if (m_bTemp)
		{
			for (size_t i = 0; i < m_data[0].y.size(); ++i)
			{
				fprintf(fp, "%.1f", m_data[0].y[i] / 10.0);
				if (i + 1 != m_data[0].y.size())
					fputs("\n", fp);
			}
		}
		else
		{
			for (size_t i = 0; i < m_data[0].y.size(); ++i)
			{
				for (size_t j = 0; j < m_data.size(); ++j)
				{
					fprintf(fp, "%d", m_data[j].y[i]);
					if (j + 1 != m_data.size())
						fputs(",", fp);
				}
				if (i + 1 != m_data[0].y.size())
					fputs("\n", fp);
			}
		}
		fclose(fp);
	}
}
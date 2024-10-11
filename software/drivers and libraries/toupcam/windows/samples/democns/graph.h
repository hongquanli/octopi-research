#ifndef __graph_h__
#define __graph_h__

#include <amvideo.h>
#include <vector>

#define MAX_ZOOM		100
#define MAX_XSTEP		15
#define DEF_XSTEP		5

typedef struct {
	BYTE	visible;
	int		offset;
	std::vector<int>	y;
} Data;

class CGraph : public CWindowImpl<CGraph>
{
	const bool	m_bTemp;	//temperature
	std::vector<Data> m_data;
	int			m_ymax, m_ymin, m_xmin;
	CPoint		m_firstPt, m_lastPt;
	bool		m_bMove;
	int			m_oldxmin, m_oldyminCur, m_oldymaxCur;

	COLORREF	m_crBackColor;
	COLORREF	m_crGridColor;
	COLORREF	m_crAxisColor;

	int			m_nLeftMargin,
				m_nTopMargin,
				m_nRightMargin,
				m_nBottomMargin;
	int			m_nArcSize;
	int			m_nTickSize;
	int			m_xTextStep;

	WTL::CFont	m_font;
	WTL::CPen	m_penGrid, m_penAxis;

	int			m_xOrg, m_yOrg;
	CRect		m_rect;

	int			m_yminCur, m_ymaxCur;
	int			m_yStep, m_xDefStep;
	int			m_xStepNum, m_xStepDen;

	CRegKey		m_regkey;
public:
	CGraph(bool bTemp = false);

	static ATL::CWndClassInfo& GetWndClassInfo()
	{
		static ATL::CWndClassInfo wc =
		{
			{ sizeof(WNDCLASSEX), CS_HREDRAW | CS_VREDRAW, StartWindowProc,
			  0, 0, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr },
			nullptr, nullptr, IDC_ARROW, TRUE, 0, _T("")
		};
		return wc;
	}

	BEGIN_MSG_MAP(CGraphImpl)
		MESSAGE_HANDLER(WM_PAINT, OnWmPaint)
		MESSAGE_HANDLER(WM_SIZE, OnWmSize);
		MESSAGE_HANDLER(WM_LBUTTONDOWN, OnWmLbuttondown)
		MESSAGE_HANDLER(WM_LBUTTONUP, OnWmLbuttonup)
		MESSAGE_HANDLER(WM_MOUSEMOVE, OnWmMousemove)
		MESSAGE_HANDLER(WM_SETCURSOR, OnWmSetcursor)
		MESSAGE_HANDLER(WM_CANCELMODE, OnWmCancelmode)
		MESSAGE_HANDLER(WM_MOUSEWHEEL, OnWmMousewheel)
	END_MSG_MAP()
public:
	void Init(int num, int ymax);
	const std::vector<Data>& GetData()const { return m_data; }
	void SetData(std::vector<Data>& v) { m_data.swap(v); }
	void Set(const std::vector<BYTE>& vecVisible, const std::vector<int>& vecOffset);
	void Get(std::vector<BYTE>& vecVisible, std::vector<int>& vecOffset);
	PBYTE GetBitmap();
	void OnCsv(const wchar_t* szFullPath)const;
	void AddData(const int arr[]);
	bool CanZoomOut(bool bX)const;
	bool CanZoomIn(bool bX)const;
	int dataNum()const
	{
		if (m_data.size())
			return (int)(m_data[0].y.size());
		return 0;
	}
	void Zoom11();
	void ZoomMax(bool bX);
	void ZoomIn(bool bX);
	void ZoomOut(bool bX);
public:
	LRESULT OnWmPaint(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmSize(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmLbuttondown(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmMousemove(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmLbuttonup(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmSetcursor(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmCancelmode(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
	LRESULT OnWmMousewheel(UINT uMsg, WPARAM wParam, LPARAM lParam, BOOL& bHandled);
private:
	void Up();
	void Down();
	void Draw(CDCHandle& dc, CRect rect);
	void DrawLine(CDCHandle* pDC, const Data& data)const;
	void DrawX(CDCHandle* pDC, const CRect& rect)const;
	void DrawY(CDCHandle* pDC, const CRect& rect)const;
	void CalcYStep();
	void GetPoint(int x, int y, CPoint& pt)const;
	void OnSizeChanged();
	void Move();
	bool CalcZoomInY(int& newminY, int& newmaxY)const;
	void AdjustZoomY(int& yVal1, int& yVal2)const;
	void SaveReg();
};

extern HCURSOR g_curHand2, g_curHand1, g_curMove, g_curArrow;

#endif
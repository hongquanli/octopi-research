#include "stdafx.h"
#include "CRectTrackerEx.h"

CRectTrackerEx::CRectTrackerEx()
	:CRectTracker()
{
}

void CRectTrackerEx::SetRectLimit(CRect rect)//Limit the size of the exposure window
{
	m_rectLimit.left = rect.left + 1;//One pixel smaller to the right
	m_rectLimit.right = rect.right - 1;
	m_rectLimit.top = rect.top + 1;
	m_rectLimit.bottom = rect.bottom - 1;
}

void CRectTrackerEx::OnChangedRect(const CRect& rectOld)
{
	if (!IsRectEmpty(m_rectLimit))
	{
		if (m_rect.Height() == rectOld.Height() && m_rect.Width() == rectOld.Width())//≥ﬂ¥ÁŒ¥±‰
		{
			if (m_rect.left < m_rectLimit.left)
				m_rect.left = m_rectLimit.left, m_rect.right = m_rect.left + rectOld.Width();
			else if (m_rect.right > m_rectLimit.right)
				m_rect.right = m_rectLimit.right, m_rect.left = m_rect.right - rectOld.Width();
			if (m_rect.top < m_rectLimit.top)
				m_rect.top = m_rectLimit.top, m_rect.bottom = m_rect.top + rectOld.Height();
			else if (m_rect.bottom > m_rectLimit.bottom)
				m_rect.bottom = m_rectLimit.bottom, m_rect.top = m_rect.bottom - rectOld.Height();
		}
		else//≥ﬂ¥Á±‰¡À
		{
			if (m_rect.left < m_rectLimit.left)
				m_rect.left = m_rectLimit.left, m_rect.right = rectOld.right;
			else if (m_rect.right > m_rectLimit.right)
				m_rect.right = m_rectLimit.right, m_rect.left = rectOld.left;
			if (m_rect.top < m_rectLimit.top)
				m_rect.top = m_rectLimit.top, m_rect.bottom = rectOld.bottom;
			else if (m_rect.bottom > m_rectLimit.bottom)
				m_rect.bottom = m_rectLimit.bottom, m_rect.top = rectOld.top;
		}
	}
	CRectTracker::OnChangedRect(m_rect);
}

void CRectTrackerEx::Draw(CDC* pDC, CPen* pen)
{
	if ((m_nStyle & (dottedLine | solidLine)) != 0)
	{
		CRect rect = m_rect;
		rect.NormalizeRect();

		CPen* pOldPen = NULL;
		CBrush* pOldBrush = NULL;
		int nOldROP;

		pOldPen = (CPen*)pDC->SelectObject(pen);
		pOldBrush = (CBrush*)pDC->SelectStockObject(NULL_BRUSH);
		nOldROP = pDC->SetROP2(R2_COPYPEN);
		pDC->Rectangle(rect.left, rect.top, rect.right, rect.bottom);

		if ((m_nStyle & (resizeInside | resizeOutside)) != 0)
		{
			UINT mask = GetHandleMask();
			for (int i = 0; i < 8; ++i)
			{
				if (mask & (1 << i))
				{
					GetHandleRect((TrackerHit)i, &rect);
					pDC->FillSolidRect(rect, RGB(255, 0, 0));
				}
			}
		}
	}
	else
	{
		CRectTracker::Draw(pDC);
	}
}

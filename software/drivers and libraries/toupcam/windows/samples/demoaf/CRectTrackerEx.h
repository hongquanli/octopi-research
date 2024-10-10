#pragma once
#include <afxext.h>

class CRectTrackerEx : public CRectTracker
{
    CRect m_rectLimit;
public:
    CRectTrackerEx();
    void SetRectLimit(CRect rect);
    void Draw(CDC* pDC, CPen* pen);
private:
    virtual void OnChangedRect(const CRect& rectOld);
};

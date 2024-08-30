#pragma once

#ifndef __AFXWIN_H__
	#error "include 'stdafx.h' before including this file for PCH"
#endif

#include "resource.h"		// main symbols

class CdemoafApp : public CWinApp
{
public:
	virtual BOOL InitInstance();
	DECLARE_MESSAGE_MAP()
};

extern CdemoafApp theApp;
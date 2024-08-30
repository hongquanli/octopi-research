#pragma once

#include "toupcam.h"

extern HToupcam g_hcam;
extern ToupcamDeviceV2 g_cur;
extern ToupcamDeviceV2 g_cam[TOUPCAM_MAX];
extern int g_cameraCnt;
extern int g_snapCount;
extern int g_ROITestCount;
extern bool g_bTesting;
extern bool g_bSnapFinish;
extern bool g_bSnapTest;
extern bool g_bImageSnap;
extern bool g_bROITest;
extern bool g_bROITest_SnapFinish;
extern bool g_bROITest_SnapStart;
extern bool g_bTriggerTest;
extern bool g_bEnableCheckBlack;
extern bool g_bCheckBlack;
extern bool g_bBlack;
extern bool g_bRealtime;
extern bool g_bReplug;
extern unsigned g_HeartbeatTimeout;
extern unsigned g_NopacketTimeout;
extern unsigned g_NoframeTimeout;
extern CString g_snapDir;

CString GetAppTimeDir(const TCHAR* header);
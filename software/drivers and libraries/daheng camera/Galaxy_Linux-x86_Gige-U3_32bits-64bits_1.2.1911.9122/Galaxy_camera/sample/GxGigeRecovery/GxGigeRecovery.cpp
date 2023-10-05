//----------------------------------------------------------------------------------
/**
\file    GxGigeRecovery.cpp 
\brief   sample to show Gige recovery function.
\version v1.0.1911.9041
\date    2019-11-04
*/
//----------------------------------------------------------------------------------

#include "GxIAPI.h"
#include <stdio.h>
#include <stdlib.h>
#include <iostream>
#include <string.h>
#include <termios.h>  
#include <unistd.h>  
#include <fcntl.h> 

#define MODULE_PATH_MAX_LENGTH 1024
using namespace std;
typedef unsigned char BYTE;

//----------------------------------------------------------------------------------
/** 
\  Class for camera control
*/
//----------------------------------------------------------------------------------
class CGigeRecovery
{
public:
    
    CGigeRecovery();
    virtual ~CGigeRecovery();

    /// Reconnect after dropped
    void GigeRecovery();

private:

    /// Open the camera
    bool __OnOpenDevice();

    /// Initialize the camera parameters
    bool __InitParam();

    /// Start acquisition
    bool __OnStartSnap();

    /// Stop acquisition
    bool __OnStopSnap();

    /// Close the Camera
    bool __OnCloseDevice();

    /// Continuous acquisition
    void __Acquisition();

    /// The function for camera offline event
    void __ProcessOffline();

    /// Reconnect after offline
    void __Recovery();

    /// Print the error message
    void __GetErrorString(GX_STATUS error_status);

    /// The callback function for camera offline event
    static void __attribute__((__stdcall__)) __OnDeviceOfflineCallbackFun(void* user_param);

private:
    
    GX_DEV_HANDLE             m_device_handle;                             ///< The camera handle
    GX_EVENT_CALLBACK_HANDLE  m_callback_handle;                           ///< The callback handle of camera offline 
    string                    m_file_path;                                 ///< The current path of the file
    string                    m_file_save_path;                            ///< The path of camera configuration parameter
    char                      m_module_path[MODULE_PATH_MAX_LENGTH];       ///< Get the current program path
    char                      m_mac_address[GX_INFO_LENGTH_32_BYTE];       ///< The camera MAC address
    GX_FRAME_DATA             m_frame_data;                                ///< The image acquired from the interface of GXGetImage
    bool                      m_is_offline;                                ///< Whether the camera is offline
    bool                      m_is_open;                                   ///< Whether the camera is opening 
    bool                      m_is_sanp;                                   ///< Whether the camera is acquisiting
};

//----------------------------------------------------------------------------------
/**
\main

\return int 
*/
//----------------------------------------------------------------------------------
int main(int argc, char* argv[])
{
    printf("\n");
    printf("-------------------------------------------------------------\n");
    printf("sample to show Gige recovery function.\n");
    printf("version: 1.0.1911.9041\n");
    printf("-------------------------------------------------------------\n");
    printf("\n");

    // Reconnect after device is offline
    CGigeRecovery object_device;
    object_device.GigeRecovery();

    // Use the x key to close exit
    printf("\n<press X or x key to exit>\n");
    bool run = true;
    while(run)
    {
        int c = getchar();
        switch(c)
        {
            case 'X':
            case 'x':
                run = false;
                break;
            default:;
        }	
    }
    
    return 0;
}

//---------------------------------------------------------------------------------
/**
\  Get the current program path

\return int
*/
//----------------------------------------------------------------------------------
int GetModuleFileName(char *name, int size)
{
    int count = 0;
    count = readlink("/proc/self/exe", name, size);
    if((count < 0) || count >= size)
    {
        return -1;
    }
    name[count] = '\0';

    return 0;
}

//---------------------------------------------------------------------------------
/**
\Constructor

*/
//----------------------------------------------------------------------------------
CGigeRecovery::CGigeRecovery()
{ 
    m_device_handle      = NULL;              // Camera handle
    m_callback_handle    = NULL;              // The camera offline callback handle
    m_frame_data.pImgBuf = NULL;              // image buffer
    m_file_path          = "";                // Get the current program path
    m_file_save_path     = "";                // The current path of the file
    m_is_offline         = false;             // Whether the camera is offline
    m_is_open            = false;             // Whether the camera is opening
    m_is_sanp            = false;             // Whether the camera is acquiring

    // Initialize the camera library .
    GX_STATUS status = GX_STATUS_SUCCESS;
    status = GXInitLib();
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        exit(0);
    }

    // Get the current program path
    GetModuleFileName(m_module_path, sizeof(m_module_path));
    char *tmp_p = NULL;
    tmp_p = strrchr(m_module_path, '/');
    *(tmp_p + 1) = '\0';
    m_file_path = m_module_path;
    m_file_save_path = m_file_path + "ConfigFile.ini";	
}

//---------------------------------------------------------------------------------
/**
\  Destructor

*/
//----------------------------------------------------------------------------------
CGigeRecovery::~CGigeRecovery()
{
    GX_STATUS status = GX_STATUS_SUCCESS;

    // Close the library
    status = GXCloseLib();
}

//---------------------------------------------------------------------------------
/**
\Open the camera

\return  bool    (true:success,false:fail)
*/
//----------------------------------------------------------------------------------
bool CGigeRecovery::__OnOpenDevice() 
{
    GX_STATUS         status   = GX_STATUS_SUCCESS;   
    uint32_t          device_number = 0;               // The Number of cameras
    bool              return_value    = false;         // 
    GX_DEVICE_IP_INFO device_ip_info;                  // The camera IP information
    GX_OPEN_PARAM     open_param;                      // Initialize the parameters for opening camera

    // Enumerate the number of cameras
    printf("====================CGigeRecovery::__OnOpenDevice()====================\n");
    status = GXUpdateDeviceList(&device_number, 1000);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    // Determine the number of currently cameras.
    if (device_number <= 0)
    {
        printf("<No device>\n");
        return false;
    }

    //Get the network information for the first camera
    status = GXGetDeviceIPInfo(1, &device_ip_info);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }
    memcpy(m_mac_address, device_ip_info.szMAC, GX_INFO_LENGTH_32_BYTE);

    // Open the device by the MAC address
    open_param.accessMode = GX_ACCESS_EXCLUSIVE;
    open_param.openMode   = GX_OPEN_MAC;
    open_param.pszContent = device_ip_info.szMAC;
    printf("<Open device by MAC: %s>\n", device_ip_info.szMAC);
    status = GXOpenDevice(&open_param, &m_device_handle);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    // Initialize the  parameters
    printf("<Initialize the device parameters>\n");
    return_value = __InitParam();
    if (!return_value)
    {
        return false;
    }

    // Export the parameter profile
    printf("<Export config file>\n");
    status = GXExportConfigFile(m_device_handle, m_file_save_path.c_str());
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    // Register the offline callback function
    printf("<Register device Offline callback>\n");
    status = GXRegisterDeviceOfflineCallback(m_device_handle, this, __OnDeviceOfflineCallbackFun, &m_callback_handle);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    m_is_open = true;	
    return true;
}

//---------------------------------------------------------------------------------
/**
\  Initialize the  parameters

\return  bool   (true:success,false:fail)
*/
//----------------------------------------------------------------------------------
bool CGigeRecovery::__InitParam()
{
    GX_STATUS status     = GX_STATUS_SUCCESS;  

    // The Raw image size
    int64_t   payload_size = 0;

    // Set to continuous acquisition
    status = GXSetEnum(m_device_handle, GX_ENUM_ACQUISITION_MODE, GX_ACQ_MODE_CONTINUOUS);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    // Set the triggerMode off
    status = GXSetEnum(m_device_handle, GX_ENUM_TRIGGER_MODE, GX_TRIGGER_MODE_OFF);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }

    // Get the image size
    status = GXGetInt(m_device_handle, GX_INT_PAYLOAD_SIZE, &payload_size);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }
    m_frame_data.pImgBuf = new BYTE[(size_t)payload_size];
    if (m_frame_data.pImgBuf == NULL)
    {
        printf("<Failed to allocate memory>\n");
        return false;
    }

    return true;
}

//---------------------------------------------------------------------------------
/**
\ The callback function for camera offline event
\param   user_param

\return  void
*/
//----------------------------------------------------------------------------------
void __attribute__((__stdcall__)) CGigeRecovery::__OnDeviceOfflineCallbackFun(void* user_param)
{
    CGigeRecovery *object_device = (CGigeRecovery *)user_param;

    // Camera offline
    object_device->m_is_offline = true;
    printf("**********************Device offline**********************\n");
}

//---------------------------------------------------------------------------------
/**
\ Start acquisition

\return   true:success,false:fail
*/
//----------------------------------------------------------------------------------
bool CGigeRecovery::__OnStartSnap() 
{
    GX_STATUS status = GX_STATUS_SUCCESS;  

    printf("====================CGigeRecovery::__OnStartSnap()====================\n");

    // Send start acquisition command
    printf("<Send start snap command to device>\n");
    status = GXSendCommand(m_device_handle, GX_COMMAND_ACQUISITION_START);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }
    m_is_sanp = true;

    return true;
}

//---------------------------------------------------------------------------------
/**
\  Stop acquisition

\return  bool   (true:success,false:fail)
*/
//----------------------------------------------------------------------------------
bool CGigeRecovery::__OnStopSnap() 
{
    GX_STATUS status = GX_STATUS_SUCCESS;  	
    printf("====================CGigeRecovery::__OnStopSnap()====================\n");

    // Stop Acquisition
    printf("<Send stop snap command to device>\n");
    status = GXSendCommand(m_device_handle, GX_COMMAND_ACQUISITION_STOP);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return false;
    }
    m_is_sanp = false;

    return true;
}

//---------------------------------------------------------------------------------
/**
\   Close the camera

\return  bool   (true:success,false:fail)
*/
//----------------------------------------------------------------------------------
bool CGigeRecovery::__OnCloseDevice() 
{
    GX_STATUS status = GX_STATUS_SUCCESS;

    printf("====================CGigeRecovery::__OnCloseDevice()====================\n");

    // Unregister the camera offline callback function
    printf("<Unregister device Offline callback>\n");
    status = GXUnregisterDeviceOfflineCallback(m_device_handle, m_callback_handle);
    m_callback_handle = NULL;
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
    }

    // Close the camera
    printf("<Close device>\n");
    status = GXCloseDevice(m_device_handle);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
    }
    m_device_handle = NULL;

    //Release the resources
    if (m_frame_data.pImgBuf != NULL)
    {
        delete[]m_frame_data.pImgBuf;
        m_frame_data.pImgBuf = NULL;
    }

    m_is_open = false;

    return true;
}

//----------------------------------------------------------------------------------
/**
\ Check if there is a keyboard button pressed
 
\return   int
*/
//----------------------------------------------------------------------------------
int _kbhit(void)  
{  
    struct termios oldt, newt;  
    int ch;  
    int oldf;  
    tcgetattr(STDIN_FILENO, &oldt);  
    newt = oldt;  
    newt.c_lflag &= ~(ICANON | ECHO);  
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);  
    oldf = fcntl(STDIN_FILENO, F_GETFL, 0);  
    fcntl(STDIN_FILENO, F_SETFL, oldf | O_NONBLOCK);  
    ch = getchar();  
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);  
    fcntl(STDIN_FILENO, F_SETFL, oldf);  
    if(ch != EOF)  
    {  
        ungetc(ch, stdin);  
        return 1;  
    }  
    return 0;  
} 

//---------------------------------------------------------------------------------
/**
\ Continuous acquisition

\return   void
*/
//----------------------------------------------------------------------------------
void CGigeRecovery::__Acquisition() 
{ 
    GX_STATUS status = GX_STATUS_SUCCESS; 
    printf("====================CGigeRecovery::__Acquisition()====================\n");
    printf("<Press any key to stop acquisition>\n");

    // No keyboard button pressed
    while(!_kbhit())
    {
        if (m_is_offline)       // Process offline event and reconnect
        {
            // Process offline event
            __ProcessOffline();

            // reconnect
            __Recovery();
        }
        else                    // live
        {
            status = GXGetImage(m_device_handle, &m_frame_data, 500);
            if (status == GX_STATUS_SUCCESS)
            {
                if(m_frame_data.nStatus == 0)
                {
                    printf("<Successfully get Image>\n");
                }
            }
            else
            {
                __GetErrorString(status);
            }
        }
    }

    getchar();
}

//---------------------------------------------------------------------------------
/**
\  Process offline event

\return   void
*/
//----------------------------------------------------------------------------------
void CGigeRecovery::__ProcessOffline()
{
    GX_STATUS status = GX_STATUS_SUCCESS;
    printf("**********************Process Offline**********************\r");

    // Stop acquisition firstly
    if (m_is_sanp)
    {
        // Stop acquisition
        printf("\n<Send stop snap command to device>\n");
        status = GXSendCommand(m_device_handle, GX_COMMAND_ACQUISITION_STOP);
        if (status != GX_STATUS_SUCCESS)
        {
            __GetErrorString(status);
        }
        m_is_sanp = false;
    }

    // Close the camera
    if (m_is_open)
    {
        // Unregister offline callback function
        printf("<Unregister device Offline callback>\n");
        status =  GXUnregisterDeviceOfflineCallback(m_device_handle, m_callback_handle);
        m_callback_handle = NULL;
        if (status != GX_STATUS_SUCCESS)
        {
            __GetErrorString(status);
        }

        // Close the camera
        printf("<Close device>\n");
        status = GXCloseDevice(m_device_handle);

        if (status != GX_STATUS_SUCCESS)
        {
            __GetErrorString(status);
        }
        m_device_handle = NULL;

        // Release the resources
        if (m_frame_data.pImgBuf != NULL)
        {
            delete[] m_frame_data.pImgBuf;
            m_frame_data.pImgBuf = NULL;
        }
        m_is_open = false;

    }
}

//---------------------------------------------------------------------------------
/**
\  Reconnect camera

\return   void
*/
//----------------------------------------------------------------------------------
void CGigeRecovery::__Recovery()
{
    GX_STATUS         status     = GX_STATUS_SUCCESS;   
    uint32_t          device_number   = 0;             // Number of devices  
    int64_t           payload_size = 0;                // Raw image size
    GX_OPEN_PARAM     open_param;                      // Initialize the parameters for opening camera

    printf("**********************Recovery**********************\r");

    status = GXUpdateDeviceList(&device_number, 1000);
    if (status != GX_STATUS_SUCCESS)
    {
        return;
    }

    // Determine the number of currently cameras.
    if (device_number <= 0)
    {
        return;
    }

    // 
    if (m_device_handle != NULL)
    {
        status = GXCloseDevice(m_device_handle);
        m_device_handle = NULL;
    }

    // Open the device by the MAC address
    open_param.accessMode = GX_ACCESS_EXCLUSIVE;
    open_param.openMode   = GX_OPEN_MAC;
    open_param.pszContent = m_mac_address;
    printf("\n<Open Device by MAC %s>\n", m_mac_address);
    status = GXOpenDevice(&open_param, &m_device_handle);

    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return;
    }

    // Import the configuration file
    printf("<Import config file>\n");
    status = GXImportConfigFile(m_device_handle, m_file_save_path.c_str());

    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return;
    }

    // Allocate buffer
    if (m_frame_data.pImgBuf != NULL)
    {
        delete[] m_frame_data.pImgBuf;
        m_frame_data.pImgBuf = NULL;
    }
    status = GXGetInt(m_device_handle, GX_INT_PAYLOAD_SIZE, &payload_size);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return;
    }
    m_frame_data.pImgBuf = new BYTE[(size_t)payload_size];
    if (m_frame_data.pImgBuf == NULL)
    {
        printf("<Failed to allocate memory>\n");
        return;
    }

    // Register the offline callback function
    printf("<Register device Offline callback>\n");
    status = GXRegisterDeviceOfflineCallback(m_device_handle, this, __OnDeviceOfflineCallbackFun, &m_callback_handle);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return;
    }
    m_is_open = true;

    // Send start acquisition command
    printf("<Send start snap command to device>\n");
    status = GXSendCommand(m_device_handle, GX_COMMAND_ACQUISITION_START);
    if (status != GX_STATUS_SUCCESS)
    {
        __GetErrorString(status);
        return;
    }
    m_is_sanp = true;
    m_is_offline = false;
}

//----------------------------------------------------------------------------------
/**
\ Get the error message
\param  error_status

\return void
*/
//----------------------------------------------------------------------------------
void CGigeRecovery::__GetErrorString(GX_STATUS error_status)
{
    char      *error_info = NULL;
    size_t    size         = 0;
    GX_STATUS status      = GX_STATUS_SUCCESS;

    // Get the length of the error message and apply for memory
    status = GXGetLastError(&error_status, NULL, &size);
    error_info = new char[size];
    if (error_info == NULL)
    {
        printf("<Failed to allocate memory>\n");
        return ;
    }

    // Get the error message
    status = GXGetLastError(&error_status, error_info, &size);
    if (status != GX_STATUS_SUCCESS)
    {
        printf("<GXGetLastError call fail>\n");
    }
    else
    {
        printf("%s\n",(char*)error_info);
    }

    // Release the resources
    if (error_info != NULL)
    {
        delete[]error_info;
        error_info = NULL;
    }
}

//----------------------------------------------------------------------------------
/**
\brief Reconnect after offline

\return void
*/
//----------------------------------------------------------------------------------
void CGigeRecovery::GigeRecovery()
{
    bool return_value = false;

    // Open the camera
    return_value = __OnOpenDevice();
    if (!return_value)
    {
        return;
    }

    // Start acquisition
    return_value = __OnStartSnap();
    if (!return_value)
    {
        __OnCloseDevice();
        return;
    }

    // acquisition
    __Acquisition();	

    // Stop acquisition
    __OnStopSnap();

    // Close camera
    __OnCloseDevice();
}






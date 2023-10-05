//-------------------------------------------------------------
/**
\file      HalconQRCode.cpp
\brief     Sample to show how to acquire image continuously and QR Code Recognition
\version   1.0.1901.9311
\date      2019.01.31
*/
//-------------------------------------------------------------

#include "halconcpp/HalconCpp.h"

#include "GxIAPI.h"
#include "DxImageProc.h"
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>

using namespace HalconCpp;

#define ACQ_BUFFER_NUM          5               ///< Acquisition Buffer Qty.
#define ACQ_TRANSFER_SIZE       (64 * 1024)     ///< Size of data transfer block
#define ACQ_TRANSFER_NUMBER_URB 64              ///< Qty. of data transfer block
#define FILE_NAME_LEN           50              ///< Save image file name length

#define DETECT_STATUS_SUCCESS   0               ///< QRCode detected
#define DETECT_STATUS_FAIL      -1              ///< QRCode not detected

#define PIXFMT_CVT_SUCCESS      0               ///< PixelFormatConvert success
#define PIXFMT_CVT_FAIL         -1              ///< PixelFormatConvert fail

#define IMGBUF_TO_HOBJ_SUCCESS      0           ///< Image transform into Hobject success
#define IMGBUF_TO_HOBJ_FAIL         -1          ///< Image transform into Hobject fail

//Show error message
#define GX_VERIFY(emStatus) \
    if (emStatus != GX_STATUS_SUCCESS)     \
    {                                      \
        GetErrorString(emStatus);          \
        return emStatus;                   \
    }

//Show error message, close device and lib
#define GX_VERIFY_EXIT(emStatus) \
    if (emStatus != GX_STATUS_SUCCESS)     \
    {                                      \
        GetErrorString(emStatus);          \
        GXCloseDevice(g_hDevice);          \
        g_hDevice = NULL;                  \
        GXCloseLib();                      \
        printf("<App Exit!>\n");           \
        return emStatus;                   \
    }

GX_DEV_HANDLE g_hDevice = NULL;                     ///< Device handle
bool g_bSavePPMImage = false;                       ///< SaveImage flag
bool g_bColorFilter = false;                        ///< Color filter support flag
int64_t g_i64ColorFilter = GX_COLOR_FILTER_NONE;    ///< Color filter of device
bool g_bAcquisitionFlag = false;                    ///< Thread running flag
pthread_t g_nAcquisitonThreadID = 0;                ///< Thread ID of Acquisition thread

unsigned char* g_pRGBImageBuf = NULL;               ///< Memory for RAW8toRGB24
unsigned char* g_pRaw8Image = NULL;                 ///< Memory for RAW16toRAW8

int64_t g_nPayloadSize = 0;                         ///< Payload size

//Allocate the memory for pixel format transform 
void PreForAcquisition();

//Release the memory allocated
void UnPreForAcquisition();

// Transform image buffer into halcon image data
int ImgBuf2HObject(uint32_t, uint32_t, HObject);

// Get QRCode Data 
int GetQRCodeData(const HObject, HTuple, HTuple,
    HTuple, HTuple);

//Convert frame date to suitable pixel format
int PixelFormatConvert(PGX_FRAME_BUFFER);

//Save one frame to PPM image file
void SavePPMFile(uint32_t, uint32_t);

// Acquisition thread function
void *ProcGetImage(void*);

// Get description of error
void GetErrorString(GX_STATUS);

int main()
{
    printf("\n");
    printf("-------------------------------------------------------------\n");
    printf("Sample to show how to acquire image continuously and QR Code Recognition.\n");
    printf("version: 1.0.1901.9311\n");
    printf("-------------------------------------------------------------\n");
    printf("\n");
    printf("<Initializing......>"); 
    printf("\n\n");

    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    uint32_t ui32DeviceNum = 0;

    //Initialize libary
    emStatus = GXInitLib(); 
    if(emStatus != GX_STATUS_SUCCESS)
    {
        GetErrorString(emStatus);
        return emStatus;
    }

    //Get device enumerated number
    emStatus = GXUpdateDeviceList(&ui32DeviceNum, 1000);
    if(emStatus != GX_STATUS_SUCCESS)
    { 
        GetErrorString(emStatus);
        GXCloseLib();
        return emStatus;
    }

    //If no device found, app exit
    if(ui32DeviceNum <= 0)
    {
        printf("<No device found>\n");
        GXCloseLib();
        return emStatus;
    }

    //Open first device enumerated
    emStatus = GXOpenDeviceByIndex(1, &g_hDevice);
    if(emStatus != GX_STATUS_SUCCESS)
    {
        GetErrorString(emStatus);
        GXCloseLib();
        return emStatus;           
    }

    //Get Device Info
    printf("***********************************************\n");
    //Get libary version
    printf("<Libary Version : %s>\n", GXGetLibVersion());
    size_t nSize = 0;
    //Get string length of Vendor name
    emStatus = GXGetStringLength(g_hDevice, GX_STRING_DEVICE_VENDOR_NAME, &nSize);
    GX_VERIFY_EXIT(emStatus);
    //Alloc memory for Vendor name
    char *pszVendorName = new char[nSize];
    //Get Vendor name
    emStatus = GXGetString(g_hDevice, GX_STRING_DEVICE_VENDOR_NAME, pszVendorName, &nSize);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        delete[] pszVendorName;
        pszVendorName = NULL;
        GX_VERIFY_EXIT(emStatus);
    }

    printf("<Vendor Name : %s>\n", pszVendorName);
    //Release memory for Vendor name
    delete[] pszVendorName;
    pszVendorName = NULL;

    //Get string length of Model name
    emStatus = GXGetStringLength(g_hDevice, GX_STRING_DEVICE_MODEL_NAME, &nSize);
    GX_VERIFY_EXIT(emStatus);
    //Alloc memory for Model name
    char *pszModelName = new char[nSize];
    //Get Model name
    emStatus = GXGetString(g_hDevice, GX_STRING_DEVICE_MODEL_NAME, pszModelName, &nSize);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        delete[] pszModelName;
        pszModelName = NULL;
        GX_VERIFY_EXIT(emStatus);
    }

    printf("<Model Name : %s>\n", pszModelName);
    //Release memory for Model name
    delete[] pszModelName;
    pszModelName = NULL;

    //Get string length of Serial number
    emStatus = GXGetStringLength(g_hDevice, GX_STRING_DEVICE_SERIAL_NUMBER, &nSize);
    GX_VERIFY_EXIT(emStatus);
    //Alloc memory for Serial number
    char *pszSerialNumber = new char[nSize];
    //Get Serial Number
    emStatus = GXGetString(g_hDevice, GX_STRING_DEVICE_SERIAL_NUMBER, pszSerialNumber, &nSize);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        delete[] pszSerialNumber;
        pszSerialNumber = NULL;
        GX_VERIFY_EXIT(emStatus);
    }

    printf("<Serial Number : %s>\n", pszSerialNumber);
    //Release memory for Serial number
    delete[] pszSerialNumber;
    pszSerialNumber = NULL;

    //Get string length of Device version
    emStatus = GXGetStringLength(g_hDevice, GX_STRING_DEVICE_VERSION, &nSize);
    GX_VERIFY_EXIT(emStatus);
    char *pszDeviceVersion = new char[nSize];
    //Get Device Version
    emStatus = GXGetString(g_hDevice, GX_STRING_DEVICE_VERSION, pszDeviceVersion, &nSize);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        delete[] pszDeviceVersion;
        pszDeviceVersion = NULL;
        GX_VERIFY_EXIT(emStatus);
    }

    printf("<Device Version : %s>\n", pszDeviceVersion);
    //Release memory for Device version
    delete[] pszDeviceVersion;
    pszDeviceVersion = NULL;
    printf("***********************************************\n");

    //Get the type of Bayer conversion. whether is a color camera.
    emStatus = GXIsImplemented(g_hDevice, GX_ENUM_PIXEL_COLOR_FILTER, &g_bColorFilter);
    GX_VERIFY_EXIT(emStatus);
 
    if (g_bColorFilter)
    {
        emStatus = GXGetEnum(g_hDevice, GX_ENUM_PIXEL_COLOR_FILTER, &g_i64ColorFilter);
        if (emStatus != GX_STATUS_SUCCESS)
        {
            GetErrorString(emStatus);
            return PIXFMT_CVT_FAIL;
        }
    }

    emStatus = GXGetInt(g_hDevice, GX_INT_PAYLOAD_SIZE, &g_nPayloadSize);
    GX_VERIFY(emStatus);

    printf("\n");
    printf("Press [a] or [A] and then press [Enter] to start acquisition\n");
    printf("Press [s] or [S] and then press [Enter] to save one ppm image\n");
    printf("Press [x] or [X] and then press [Enter] to Exit the Program\n");
    printf("\n");

    char chStartKey = 0;
    bool bWaitStart = true;
    while (bWaitStart)
    {
        chStartKey = getchar();
        switch(chStartKey)
        {
            //press 'a' and [Enter] to start acquisition;
            //press 'x' and [Enter] to exit.
            case 'a':
            case 'A':
                //Start to acquisition
                bWaitStart = false;
                break;
            case 'S':
            case 's':
                printf("<Please start acquisiton before saving image!>\n");
                break;
            case 'x':
            case 'X':
                //App exit
                GXCloseDevice(g_hDevice);
                g_hDevice = NULL;
                GXCloseLib();
                printf("<App exit!>\n");
                return 0;
            default:
                break;
        }
    }

    //Set acquisition mode
    emStatus = GXSetEnum(g_hDevice, GX_ENUM_ACQUISITION_MODE, GX_ACQ_MODE_CONTINUOUS);
    GX_VERIFY_EXIT(emStatus);

    //Set trigger mode
    emStatus = GXSetEnum(g_hDevice, GX_ENUM_TRIGGER_MODE, GX_TRIGGER_MODE_OFF);
    GX_VERIFY_EXIT(emStatus);

    //Set buffer quantity of acquisition queue
    uint64_t nBufferNum = ACQ_BUFFER_NUM;
    emStatus = GXSetAcqusitionBufferNumber(g_hDevice, nBufferNum);
    GX_VERIFY_EXIT(emStatus);

    bool bStreamTransferSize = false;
    emStatus = GXIsImplemented(g_hDevice, GX_DS_INT_STREAM_TRANSFER_SIZE, &bStreamTransferSize);
    GX_VERIFY_EXIT(emStatus);

    if(bStreamTransferSize)
    {
        //Set size of data transfer block
        emStatus = GXSetInt(g_hDevice, GX_DS_INT_STREAM_TRANSFER_SIZE, ACQ_TRANSFER_SIZE);
        GX_VERIFY_EXIT(emStatus);
    }

    bool bStreamTransferNumberUrb = false;
    emStatus = GXIsImplemented(g_hDevice, GX_DS_INT_STREAM_TRANSFER_NUMBER_URB, &bStreamTransferNumberUrb);
    GX_VERIFY_EXIT(emStatus);

    if(bStreamTransferNumberUrb)
    {
        //Set qty. of data transfer block
        emStatus = GXSetInt(g_hDevice, GX_DS_INT_STREAM_TRANSFER_NUMBER_URB, ACQ_TRANSFER_NUMBER_URB);
        GX_VERIFY_EXIT(emStatus);
    }

    //Prepare for Acquisition, alloc memory for image pixel format tansform
    PreForAcquisition();

    //Device start acquisition
    emStatus = GXStreamOn(g_hDevice);
    if(emStatus != GX_STATUS_SUCCESS)
    {
        //Release the memory allocated
        UnPreForAcquisition();
        GX_VERIFY_EXIT(emStatus);
    }

    //Start acquisition thread, if thread create failed, exit this app
    int nRet = pthread_create(&g_nAcquisitonThreadID, NULL, ProcGetImage, NULL);
    if(nRet != 0)
    {
        //Release the memory allocated
        UnPreForAcquisition();

        GXCloseDevice(g_hDevice);
        g_hDevice = NULL;
        GXCloseLib();

        printf("<Failed to create the acquisition thread, App Exit!>\n");
        exit(nRet);
    }

    //Main loop
    bool bRun = true;
    while(bRun == true)
    {
        char chKey = getchar();
        //press 's' and [Enter] to save image;
        //press 'x' and [Enter] to exit.
        switch(chKey)
        {
            //Save PPM Image
            case 'S':
            case 's':
                g_bSavePPMImage = true;
                break;
            //Exit app
            case 'X': 
            case 'x':
                bRun = false;
                break;
            default:
                break;
        }
    }

    //Stop Acquisition thread
    g_bAcquisitionFlag = false;
    pthread_join(g_nAcquisitonThreadID, NULL);

    //Device stop acquisition
    emStatus = GXStreamOff(g_hDevice);
    if(emStatus != GX_STATUS_SUCCESS)
    {
        //Release the memory allocated
        UnPreForAcquisition();
        GX_VERIFY_EXIT(emStatus);
    }

    //Release the resources and stop acquisition thread
    UnPreForAcquisition();

    //Close device
    emStatus = GXCloseDevice(g_hDevice);
    if(emStatus != GX_STATUS_SUCCESS)
    {
        GetErrorString(emStatus);
        g_hDevice = NULL;
        GXCloseLib();
        return emStatus;
    }

    //Release libary
    emStatus = GXCloseLib();
    if(emStatus != GX_STATUS_SUCCESS)
    {
        GetErrorString(emStatus);
        return emStatus;
    }

    printf("<App exit!>\n");
    return 0;
}

//-------------------------------------------------
/**
\brief Transform image buffer into halcon image data
\param[in]  ui32Width               Image Width
\param[in]  ui32Height              Image Height
\param[out] pImg                    halcon: Image data
\return int         IMGBUF_TO_HOBJ_SUCCESS      0
                    IMGBUF_TO_HOBJ_FAIL         -1
*/
//-------------------------------------------------
int ImgBuf2HObject(uint32_t ui32Width, uint32_t ui32Height, HObject *pImg)
{
    unsigned char *pImageRed = NULL;
    unsigned char *pImageGreen = NULL;
    unsigned char *pImageBlue = NULL;

    pImageRed   = (unsigned char*)malloc(ui32Width * ui32Height);
    if (pImageRed == NULL)
    {
        printf("Alloc red channel failed!\n");
        return IMGBUF_TO_HOBJ_FAIL;
    }
    pImageGreen = (unsigned char*)malloc(ui32Width * ui32Height);
    if (pImageGreen == NULL)
    {
        free(pImageRed);
        pImageRed = NULL;
        printf("Alloc green channel failed!\n");
        return IMGBUF_TO_HOBJ_FAIL;
    }
    pImageBlue  = (unsigned char*)malloc(ui32Width * ui32Height);
    if (pImageBlue == NULL)
    {
        free(pImageRed);
        pImageRed = NULL;
        free(pImageGreen);
        pImageGreen = NULL;
        printf("Alloc blue channel failed!\n");
        return IMGBUF_TO_HOBJ_FAIL;
    }

    unsigned char* pRGBImageTmp = g_pRGBImageBuf;
    for (int row = 0; row < ui32Height; row++)
    {
        for (int col = 0; col < ui32Width; col++)
        {
            pImageRed  [row * ui32Width + col] = pRGBImageTmp[0];
            pImageGreen[row * ui32Width + col] = pRGBImageTmp[1];
            pImageBlue [row * ui32Width + col] = pRGBImageTmp[2];
            pRGBImageTmp += 3;
        }
    }
    // Create a three-channel image from three pointers on the pixels with storage management.
    GenImage3Extern(pImg, "byte", (Hlong)ui32Width, (Hlong)ui32Height, (Hlong)pImageRed, (Hlong)pImageGreen, (Hlong)pImageBlue, (Hlong)free);

    return IMGBUF_TO_HOBJ_SUCCESS;
}

//-------------------------------------------------
/**
\brief Get QR Code Data
\param[in]  objImage                halcon: Image data
\param[out] pobjDecodedDataStrings  halcon: Data string from QR Code
\param[out] pobjSymbolXLDs          halcon: QR Code Area
\param[out] pobjTime                halcon: Recognize time
\return int                         DETECT_STATUS_SUCCESS QRCode Detected
                                    DETECT_STATUS_FAIL    QRCode Not Detected
*/
//-------------------------------------------------
int GetQRCodeData(const HImage *objImage, HTuple *pobjDecodedDataStrings, HObject *pobjSymbolXLDs, HTuple *pobjTime)
{
    // Local control variables
    HTuple objDataCodeHandle;
    HTuple objResultHandles;
    HTuple objSecondsBegin;
    HTuple objSecondsEnd;

    // Create a model of a 2D data code class.
    CreateDataCode2dModel("QR Code", HTuple(), HTuple(), &objDataCodeHandle);

    // Start Time.
    CountSeconds(&objSecondsBegin);

    // Detect and read 2D data code symbols in an image or train the 2D data code model.
    FindDataCode2d(*objImage, pobjSymbolXLDs, objDataCodeHandle, HTuple(), HTuple(),
            &objResultHandles, pobjDecodedDataStrings);

    // Passed Time.
    CountSeconds(&objSecondsEnd);
    *pobjTime = (objSecondsEnd - objSecondsBegin) * 1000;

    // Delete a 2D data code model and free the allocated memory.
    ClearDataCode2dModel(objDataCodeHandle);

    if (objResultHandles == 0)
    {
        return DETECT_STATUS_SUCCESS;
    }
    else
    {
        return DETECT_STATUS_FAIL;
    }
}

//-------------------------------------------------
/**
\brief Convert frame date to suitable pixel format
\param pFrameBuffer[in]    FrameData from camera
\return void
*/
//-------------------------------------------------
int PixelFormatConvert(PGX_FRAME_BUFFER pFrameBuffer)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    VxInt32 emDXStatus = DX_OK;

    // Convert RAW8 or RAW16 image to RGB24 image
    switch (pFrameBuffer->nPixelFormat)
    {
        case GX_PIXEL_FORMAT_MONO8:
        case GX_PIXEL_FORMAT_BAYER_GR8:
        case GX_PIXEL_FORMAT_BAYER_RG8:
        case GX_PIXEL_FORMAT_BAYER_GB8:
        case GX_PIXEL_FORMAT_BAYER_BG8:
        {
            // Convert to the RGB image
            emDXStatus = DxRaw8toRGB24((unsigned char*)pFrameBuffer->pImgBuf, g_pRGBImageBuf, pFrameBuffer->nWidth, pFrameBuffer->nHeight,
                              RAW2RGB_NEIGHBOUR, DX_PIXEL_COLOR_FILTER(g_i64ColorFilter), false);
            if (emDXStatus != DX_OK)
            {
                printf("DxRaw8toRGB24 Failed, Error Code: %d\n", emDXStatus);
                return PIXFMT_CVT_FAIL;
            }
            break;
        }
        case GX_PIXEL_FORMAT_MONO10:
        case GX_PIXEL_FORMAT_MONO12:
        case GX_PIXEL_FORMAT_BAYER_GR10:
        case GX_PIXEL_FORMAT_BAYER_RG10:
        case GX_PIXEL_FORMAT_BAYER_GB10:
        case GX_PIXEL_FORMAT_BAYER_BG10:
        case GX_PIXEL_FORMAT_BAYER_GR12:
        case GX_PIXEL_FORMAT_BAYER_RG12:
        case GX_PIXEL_FORMAT_BAYER_GB12:
        case GX_PIXEL_FORMAT_BAYER_BG12:
        {
            // Convert to the Raw8 image
            emDXStatus = DxRaw16toRaw8((unsigned char*)pFrameBuffer->pImgBuf, g_pRaw8Image, pFrameBuffer->nWidth, pFrameBuffer->nHeight, DX_BIT_2_9);
            if (emDXStatus != DX_OK)
            {
                printf("DxRaw16toRaw8 Failed, Error Code: %d\n", emDXStatus);
                return PIXFMT_CVT_FAIL;
            }
            // Convert to the RGB24 image
            emDXStatus = DxRaw8toRGB24((unsigned char*)g_pRaw8Image, g_pRGBImageBuf, pFrameBuffer->nWidth, pFrameBuffer->nHeight,
                              RAW2RGB_NEIGHBOUR, DX_PIXEL_COLOR_FILTER(g_i64ColorFilter), false);
            if (emDXStatus != DX_OK)
            {
                printf("DxRaw8toRGB24 Failed, Error Code: %d\n", emDXStatus);
                return PIXFMT_CVT_FAIL;
            }
            break;
        }
        default:
        {
            printf("Error : PixelFormat of this camera is not supported\n");
            return PIXFMT_CVT_FAIL;
        }
    }
    return PIXFMT_CVT_SUCCESS;
}

//-------------------------------------------------
/**
\brief Save PPM image
\param ui32Width[in]       image width
\param ui32Height[in]      image height
\return void
*/
//-------------------------------------------------
void SavePPMFile(uint32_t ui32Width, uint32_t ui32Height)
{
    char szName[FILE_NAME_LEN] = {0};

    static int nRawFileIndex = 0;
    FILE* phImageFile = NULL;
    sprintf(szName, "Frame_%d.ppm", nRawFileIndex++);
    phImageFile = fopen(szName,"wb");
    if (phImageFile == NULL)
    {
        printf("Save %s failed!\n", szName);
        return;
    }

    //Save color image
    if(g_pRGBImageBuf != NULL)
    {
        fprintf(phImageFile, "P6\n" "%u %u 255\n", ui32Width, ui32Height);
        fwrite(g_pRGBImageBuf, 1, g_nPayloadSize * 3, phImageFile);
        fclose(phImageFile);
        phImageFile = NULL;
        printf("Save %s successed\n", szName);
    }
    else
    {
        printf("Save %s failed!\n", szName);
    }

    return;
}

//-------------------------------------------------
/**
\brief Allocate the memory for pixel format transform 
\return void
*/
//-------------------------------------------------
void PreForAcquisition()
{
    //Alloc memory for color image pixel format transform 
    g_pRGBImageBuf = new unsigned char[g_nPayloadSize * 3]; 
    g_pRaw8Image = new unsigned char[g_nPayloadSize];

    return;
}

//-------------------------------------------------
/**
\brief Release the memory allocated
\return void
*/
//-------------------------------------------------
void UnPreForAcquisition()
{
    //Release resources
    if (g_pRaw8Image != NULL)
    {
        delete[] g_pRaw8Image;
        g_pRaw8Image = NULL;
    }
    if (g_pRGBImageBuf != NULL)
    {
        delete[] g_pRGBImageBuf;
        g_pRGBImageBuf = NULL;
    }

    return;
}

//-------------------------------------------------
/**
\brief Acquisition thread function
\param pParam[in]       thread param, not used in this app
\return void*
*/
//-------------------------------------------------
void *ProcGetImage(void* pParam)
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    int nStatusBuf2Hobj = IMGBUF_TO_HOBJ_SUCCESS;

    // Thread running flag setup
    g_bAcquisitionFlag = true;
    PGX_FRAME_BUFFER pFrameBuffer = NULL;
    uint32_t ui32FrameCount = 0;
    uint32_t ui32AcqFrameRate = 0;

    // Halcon Window Size
    const uint32_t ui32X = 16;
    const uint32_t ui32Y = 16;
    const uint32_t ui32WindowWidth = 960;
    const uint32_t ui32WindowHeight = 600;
        
    // Setup Window, Halcon will throw a exception when license missing, exit when exception catched.
    HWindow objWindow;
    try
    {
        objWindow = HWindow(ui32X, ui32Y, ui32WindowWidth, ui32WindowHeight, 0, "visible", "");
    }
    catch(...)
    {
        UnPreForAcquisition();
        printf("<Unexpected Halcon exception, please check halcon installation and license! App Exit!>\n");
        exit(0);
    }

    int64_t nWidth = 0;
    int64_t nHeight = 0;
    emStatus = GXGetInt(g_hDevice, GX_INT_WIDTH, &nWidth);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        printf("Get camera info failed, please restart this app!\n");
        return 0;
    }
    emStatus = GXGetInt(g_hDevice, GX_INT_HEIGHT, &nHeight);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        printf("Get camera info failed, please restart this app!\n");
        return 0;
    }

    HTuple objDecodedDataStrings;
    HTuple objTime;

    HImage objImage;
    HObject objSymbolXLDs;
    int nStatusDetect = DETECT_STATUS_SUCCESS;

    // Set Window Size
    objWindow.SetPart(0, 0, nHeight - 1, nWidth - 1);
    objWindow.SetLineWidth(3);

    while(g_bAcquisitionFlag)
    {
        // Get a frame from Queue
        emStatus = GXDQBuf(g_hDevice, &pFrameBuffer, 1000);
        if(emStatus != GX_STATUS_SUCCESS)
        {
            if (emStatus == GX_STATUS_TIMEOUT)
            {
                continue;
            }
            else
            {
                GetErrorString(emStatus);
                break;
            }
        }

        if(pFrameBuffer->nStatus != GX_FRAME_STATUS_SUCCESS)
        {
            printf("<Abnormal Acquisition: Exception code: %d>\n", pFrameBuffer->nStatus);
        }
        else
        {
            emStatus = PixelFormatConvert(pFrameBuffer);
            if(emStatus != GX_STATUS_SUCCESS)
            {
                GXQBuf(g_hDevice, pFrameBuffer);
                break;
            }

            if (g_bSavePPMImage)
            {
                SavePPMFile(pFrameBuffer->nWidth, pFrameBuffer->nHeight);
                g_bSavePPMImage = false;
            }

            // Transform Image buffer to HImage
            nStatusBuf2Hobj = ImgBuf2HObject(nWidth, nHeight, &objImage);
            if (nStatusBuf2Hobj != IMGBUF_TO_HOBJ_SUCCESS)
            {
                GXQBuf(g_hDevice, pFrameBuffer);
                printf("Transform Image buffer to HImage failed!\n");
                break;
            }

            // Display image
            objWindow.DispObj(objImage);

            // Get QR Code Data and QR Code Area
            nStatusDetect = GetQRCodeData(&objImage, &objDecodedDataStrings, &objSymbolXLDs, &objTime);
            if (nStatusDetect == DETECT_STATUS_SUCCESS)
            {
                // Print String to console
                printf("QR Code Result String:%s  Using %.3fms\n", objDecodedDataStrings.S().Text(), objTime.D());
                // Display QR Code Area
                objWindow.DispObj(objSymbolXLDs);
            }
        }
        // Put the frame back to Queue
        emStatus = GXQBuf(g_hDevice, pFrameBuffer);
        if(emStatus != GX_STATUS_SUCCESS)
        {
            GetErrorString(emStatus);
            break;
        }  
    }
    printf("<Acquisition thread Exit!>\n");

    return 0;
}

//----------------------------------------------------------------------------------
/**
\brief  Get description of input error code
\param[in]  emErrorStatus  error code

\return void
*/
//----------------------------------------------------------------------------------
void GetErrorString(GX_STATUS emErrorStatus)
{
    char *error_info = NULL;
    size_t size = 0;
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    
    // Get length of error description
    emStatus = GXGetLastError(&emErrorStatus, NULL, &size);
    if(emStatus != GX_STATUS_SUCCESS)
    {
        printf("<Error when calling GXGetLastError>\n");
        return;
    }
    
    // Alloc error resources
    error_info = new char[size];
    if (error_info == NULL)
    {
        printf("<Failed to allocate memory>\n");
        return ;
    }
    
    // Get error description
    emStatus = GXGetLastError(&emErrorStatus, error_info, &size);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        printf("<Error when calling GXGetLastError>\n");
    }
    else
    {
        printf("%s\n", (char*)error_info);
    }

    // Realease error resources
    if (error_info != NULL)
    {
        delete []error_info;
        error_info = NULL;
    }
}


//--------------------------------------------------------------------------------
/**
\file     AcquisitionThread.cpp
\brief    CAcquisitionThread Class implementation file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include "AcquisitionThread.h"

//----------------------------------------------------------------------------------
/**
\Constructor
*/
//----------------------------------------------------------------------------------
CAcquisitionThread::CAcquisitionThread(QObject *parent) :
    QThread(parent),
    m_ui64AcquisitionBufferNum(0),
    m_nFrameCount(0),
    m_bAcquisitionThreadFlag(false),
    m_hDevice(NULL),
    m_bSoftTriggerOn(false),
    m_i64ColorFilter(0),
    m_i64ImageMaxWidth(0),
    m_i64ImageWidth(0),
    m_i64ImageMaxHeight(0),
    m_i64ImageHeight(0),
    m_bColorFilter(false),
    m_bColorCorrection(false),
    m_bGammaRegulation(false),
    m_bContrastRegulation(false),
    m_i64ColorCorrection(0),
    m_pGammaLut(NULL),
    m_pContrastLut(NULL),
    m_pstarrFrameBuffer(NULL),
    m_pRaw8Image(NULL),
    m_pImageElement0(NULL),
    m_pImageElement1(NULL),
    m_pImageElement2(NULL),
    m_objFps(),
    m_objParamMutex(QMutex::Recursive),
    m_objDequeMutex(QMutex::Recursive)
{

}
//----------------------------------------------------------------------------------
/**
\Destructor
*/
//----------------------------------------------------------------------------------
CAcquisitionThread::~CAcquisitionThread()
{
    // Release all resources
    RELEASE_ALLOC_MEM(m_pImageElement0);
    RELEASE_ALLOC_MEM(m_pImageElement1);
    RELEASE_ALLOC_MEM(m_pImageElement2);
    RELEASE_ALLOC_ARR(m_pRaw8Image);

    RELEASE_ALLOC_ARR(m_pGammaLut);
    RELEASE_ALLOC_ARR(m_pContrastLut);

    RELEASE_ALLOC_ARR(m_pstarrFrameBuffer);
}

//----------------------------------------------------------------------------------
/**
\Main function of Acquisition-thread, Acquisition-thread run start from here
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::run()
{
    GX_STATUS   emStatus = GX_STATUS_SUCCESS;
    PROC_STATUS emProcStatus = PROC_SUCCESS;
    uint32_t    ui32FrameNum = 0;

    // Acquisition frame count reset
    m_nFrameCount = 0;

    // Acquisition thread loop
    while (m_bAcquisitionThreadFlag)
    {
        // Acquire ui32FrameElementNum frame data from buffer queue
        emStatus = GXDQAllBufs(m_hDevice, m_pstarrFrameBuffer, m_ui64AcquisitionBufferNum, &ui32FrameNum, 1000);

        // Continue when GXDQAllBufs timeout, other error will quit acquisiton loop
        if (emStatus != GX_STATUS_SUCCESS)
        {
            if (emStatus == GX_STATUS_TIMEOUT)
            {
                continue;
            }
            else
            {
                //Get Acquisition error and send it to main thread
                GetAcquistionErrorString(emStatus);
                break;
            }
        }

        // Return all bufs back when met the last frame is incomplete
        if (m_pstarrFrameBuffer[ui32FrameNum - 1]->nStatus != GX_FRAME_STATUS_SUCCESS)
        {
            emStatus = GXQAllBufs(m_hDevice);
            continue;
        }

        // Get a buffer for process new image
        QImage *pobjImageBuffer = PopFrontFromEmptyBufferDeque();
        // If buffer deque is empty, get one buffer from image show deque
        if (pobjImageBuffer == NULL)
        {
            pobjImageBuffer = PopFrontFromShowImageDeque();
        }

        // Assign the address of the first pixel of the QImage to a temporary variable for image processing
        unsigned char* pImageProcess = pobjImageBuffer->bits();

        // Image processing, Raw to RGB24 and image improvment, if process failed put buffer back to buffer deque
        emProcStatus = ImageProcess(m_pstarrFrameBuffer[ui32FrameNum - 1], pImageProcess);
        if (emProcStatus != PROC_SUCCESS)
        {
            emStatus = GXQAllBufs(m_hDevice);
            PushBackToEmptyBufferDeque(pobjImageBuffer);
            break;
        }

        // Image processing is done push processed buffer to show image deque
        PushBackToShowImageDeque(pobjImageBuffer);

        // Put all buffers back to deque
        emStatus = GXQAllBufs(m_hDevice);
        if (emStatus != GX_STATUS_SUCCESS)
        {
            //Get Acquisition error and send it to main thread
            GetAcquistionErrorString(emStatus);
            break;
        }

        // Get acquisition frame rate
        for (uint32_t i = 0; i < ui32FrameNum; i++)
        {
            m_nFrameCount++;
            m_objFps.IncreaseFrameNum();
        }
    }

    // Acquisition fps reset
    m_objFps.Reset();

    // Clear both deque when acquisition is stop
    ClearDeque();

    return;
}

//----------------------------------------------------------------------------------
/**
\Push back to empty buffer deque
\param[in]      pobjImage      Buffer pointer to push back
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::PushBackToEmptyBufferDeque(QImage* pobjImage)
{
    QMutexLocker locker(&m_objDequeMutex);
    m_objEmptyBufferDeque.push_back(pobjImage);

    return;
}

//----------------------------------------------------------------------------------
/**
\Push back to show image deque
\param[in]      pobjImage      Buffer pointer to push back
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::PushBackToShowImageDeque(QImage* pobjImage)
{
    QMutexLocker locker(&m_objDequeMutex);
    m_objShowImageDeque.push_back(pobjImage);

    return;
}

//----------------------------------------------------------------------------------
/**
\Pop front from empty buffer deque
\param[in]
\param[out]
\return  QImage*    pobjImage   If deque not empty return a buffer pointer
                    NULL        If deque is empty return NULL
*/
//----------------------------------------------------------------------------------
QImage* CAcquisitionThread::PopFrontFromEmptyBufferDeque()
{
    QMutexLocker locker(&m_objDequeMutex);

    if (m_objEmptyBufferDeque.empty())
    {
        return NULL;
    }

    QImage* pobjImage = m_objEmptyBufferDeque.front();
    m_objEmptyBufferDeque.pop_front();

    return pobjImage;
}

//----------------------------------------------------------------------------------
/**
\Pop front from show image deque
\param[in]
\param[out]
\return  QImage*    pobjImage   If deque not empty return a buffer pointer
                    NULL        If deque is empty return NULL
*/
//----------------------------------------------------------------------------------
QImage* CAcquisitionThread::PopFrontFromShowImageDeque()
{
    QMutexLocker locker(&m_objDequeMutex);

    if (m_objShowImageDeque.empty())
    {
        return NULL;
    }

    QImage* pobjImage = m_objShowImageDeque.front();
    m_objShowImageDeque.pop_front();

    return pobjImage;
}

//----------------------------------------------------------------------------------
/**
\Clear both deque
\param[in]
\param[out]
\return  void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::ClearDeque()
{
    QMutexLocker locker(&m_objDequeMutex);

    m_objEmptyBufferDeque.clear();
    m_objShowImageDeque.clear();

    return;
}

//----------------------------------------------------------------------------------
/**
\Get image show frame rate
\param[in]
\param[out]
\return  double
*/
//----------------------------------------------------------------------------------
double CAcquisitionThread::GetImageAcqFps()
{
    m_objFps.UpdateFps();
    double dAcqFrameRate = m_objFps.GetFps();

    return dAcqFrameRate;
}

//----------------------------------------------------------------------------------
/**
\Process Raw image to RGB image and do image improvment
\param[in]      pstFrameBuffer  Raw image acquired
\param[out]     pImageProcess   Processed image
\return  PROC_STATUS     PROC_SUCCESS   process successed
                         PROC_FAIL      process failed
*/
//----------------------------------------------------------------------------------
PROC_STATUS CAcquisitionThread::ImageProcess(const PGX_FRAME_BUFFER pstFrameBuffer, unsigned char* pImageProcess)
{
    VxInt32 emDxStatus = DX_OK;

    // Convert RAW8 or RAW16 image to RGB24 image
    switch (pstFrameBuffer->nPixelFormat)
    {
        case GX_PIXEL_FORMAT_MONO8:
        case GX_PIXEL_FORMAT_MONO8_SIGNED:
        case GX_PIXEL_FORMAT_BAYER_GR8:
        case GX_PIXEL_FORMAT_BAYER_RG8:
        case GX_PIXEL_FORMAT_BAYER_GB8:
        case GX_PIXEL_FORMAT_BAYER_BG8:
        {
            // Convert to the RGB
            emDxStatus = DxRaw8toRGB24((unsigned char*)pstFrameBuffer->pImgBuf, pImageProcess, m_i64ImageWidth, m_i64ImageHeight,
                              RAW2RGB_NEIGHBOUR, DX_PIXEL_COLOR_FILTER(m_i64ColorFilter), false);
            if (emDxStatus != DX_OK)
            {
                emit SigImageProcError(emDxStatus);
                return PROC_FAIL;
            }
            break;
        }
        case GX_PIXEL_FORMAT_MONO10:
        case GX_PIXEL_FORMAT_BAYER_GR10:
        case GX_PIXEL_FORMAT_BAYER_RG10:
        case GX_PIXEL_FORMAT_BAYER_GB10:
        case GX_PIXEL_FORMAT_BAYER_BG10:
        {
            // Convert to the Raw8 image
            emDxStatus = DxRaw16toRaw8((unsigned char*)pstFrameBuffer->pImgBuf, m_pRaw8Image, m_i64ImageWidth, m_i64ImageHeight, DX_BIT_2_9);
            if (emDxStatus != DX_OK)
            {
                emit SigImageProcError(emDxStatus);
                return PROC_FAIL;
            }
            // Convert to the RGB24 image
            emDxStatus = DxRaw8toRGB24((unsigned char*)m_pRaw8Image, pImageProcess, m_i64ImageWidth, m_i64ImageHeight,
                              RAW2RGB_NEIGHBOUR, DX_PIXEL_COLOR_FILTER(m_i64ColorFilter), false);
            if (emDxStatus != DX_OK)
            {
                emit SigImageProcError(emDxStatus);
                return PROC_FAIL;
            }
            break;
        }
        case GX_PIXEL_FORMAT_MONO12:
        case GX_PIXEL_FORMAT_BAYER_GR12:
        case GX_PIXEL_FORMAT_BAYER_RG12:
        case GX_PIXEL_FORMAT_BAYER_GB12:
        case GX_PIXEL_FORMAT_BAYER_BG12:
        {
            // Convert to the Raw8 image
            emDxStatus = DxRaw16toRaw8((unsigned char*)pstFrameBuffer->pImgBuf, m_pRaw8Image, m_i64ImageWidth, m_i64ImageHeight, DX_BIT_4_11);
            if (emDxStatus != DX_OK)
            {
                emit SigImageProcError(emDxStatus);
                return PROC_FAIL;
            }
            // Convert to the RGB24 image
            emDxStatus = DxRaw8toRGB24((unsigned char*)m_pRaw8Image, pImageProcess, m_i64ImageWidth, m_i64ImageHeight,
                              RAW2RGB_NEIGHBOUR, DX_PIXEL_COLOR_FILTER(m_i64ColorFilter), false);
            if (emDxStatus != DX_OK)
            {
                emit SigImageProcError(emDxStatus);
                return PROC_FAIL;
            }
            break;
        }
        default:
        {
            // Enter this branch when pixel format not support
            emit SigImageProcError(emDxStatus);
            return PROC_FAIL;
        }
    }

    // Image improvment params will changed in other thread, must being locked
    QMutexLocker locker(&m_objParamMutex);

    int64_t i64ColorCorrection = m_bColorCorrection ? m_i64ColorCorrection : 0;
    unsigned char* pGammaLut = m_bGammaRegulation ? m_pGammaLut : NULL;
    unsigned char* pContrastLut = m_bContrastRegulation ? m_pContrastLut : NULL;

    if (i64ColorCorrection != 0 || pGammaLut != NULL || pContrastLut != NULL)
    {
        emDxStatus = DxImageImprovment(pImageProcess, pImageProcess, m_i64ImageWidth, m_i64ImageHeight, i64ColorCorrection, pContrastLut, pGammaLut);
        if (emDxStatus != DX_OK)
        {
            emit SigImageProcError(emDxStatus);
            return PROC_FAIL;
        }
    }

    return PROC_SUCCESS;
}


//----------------------------------------------------------------------------------
/**
\Get device handle from main-thread
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::GetDeviceHandle(GX_DEV_HANDLE hDeviceHandle)
{
    m_hDevice = hDeviceHandle;
}

//----------------------------------------------------------------------------------
/**
\Alloc QImage resource for show frames on ImageLabel
\param[in]
\param[out]
\return bool    true : Prepare success
\               false: Prepare fail
*/
//----------------------------------------------------------------------------------
bool CAcquisitionThread::PrepareForShowImg()
{
    GX_STATUS emStatus = GX_STATUS_SUCCESS;
    int64_t i64ImageWidth = 0;
    int64_t i64ImageHeight = 0;

    // Release PGX_FRAME_BUFFER array
    RELEASE_ALLOC_ARR(m_pstarrFrameBuffer);

    // PGX_FRAME_DATA is pointer of GX_FRAME_DATA, pointer array for image acquisition
    try
    {
        m_pstarrFrameBuffer = new PGX_FRAME_BUFFER[m_ui64AcquisitionBufferNum];
    }
    catch (std::bad_alloc& e)
    {
        QMessageBox::about(NULL, "Error", "Start Acquisition Failed : Allocate PGX_FRAME_BUFFER array failed! ");
        return false;
    }

    // Get the type of Bayer conversion. whether is a color camera.
    emStatus = GXIsImplemented(m_hDevice, GX_ENUM_PIXEL_COLOR_FILTER, &m_bColorFilter);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        ShowErrorString(emStatus);
        return false;
    }

    // Color image
    if(m_bColorFilter)
    {
        emStatus = GXGetEnum(m_hDevice, GX_ENUM_PIXEL_COLOR_FILTER, &m_i64ColorFilter);
        if (emStatus != GX_STATUS_SUCCESS)
        {
            ShowErrorString(emStatus);
            return false;
        }
    }

    // Get the image width
    emStatus = GXGetInt(m_hDevice, GX_INT_WIDTH, &i64ImageWidth);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        ShowErrorString(emStatus);
        return false;
    }

    // Get the image height
    emStatus = GXGetInt(m_hDevice, GX_INT_HEIGHT, &i64ImageHeight);
    if (emStatus != GX_STATUS_SUCCESS)
    {
        ShowErrorString(emStatus);
        return false;
    }

    // If width or height is changed, realloc image buffer
    if (i64ImageWidth != m_i64ImageWidth || i64ImageHeight != m_i64ImageHeight)
    {
        m_i64ImageWidth = i64ImageWidth;
        m_i64ImageHeight = i64ImageHeight;

        RELEASE_ALLOC_ARR(m_pRaw8Image);
        RELEASE_ALLOC_MEM(m_pImageElement0);
        RELEASE_ALLOC_MEM(m_pImageElement1);
        RELEASE_ALLOC_MEM(m_pImageElement2);

        try
        {
            // Allocate raw8 frame buffer for DxRaw16toRaw8
            m_pRaw8Image = new unsigned char[m_i64ImageWidth * m_i64ImageHeight];

            // Allocate three QImage buffer for deque acquisition
            m_pImageElement0 = new QImage(m_i64ImageWidth, m_i64ImageHeight, QImage::Format_RGB888);
            m_pImageElement1 = new QImage(m_i64ImageWidth, m_i64ImageHeight, QImage::Format_RGB888);
            m_pImageElement2 = new QImage(m_i64ImageWidth, m_i64ImageHeight, QImage::Format_RGB888);
        }
        catch (std::bad_alloc& e)
        {
           QMessageBox::about(NULL, "Error", "Start Acquisition Failed : Allocate image resources failed! ");
           return false;
        }
    }

    // Clear deque if it is not empty
    if (!m_objEmptyBufferDeque.empty())
    {
        ClearDeque();
    }

    // Add buffer pointer to empty buffer deque
    PushBackToEmptyBufferDeque(m_pImageElement0);
    PushBackToEmptyBufferDeque(m_pImageElement1);
    PushBackToEmptyBufferDeque(m_pImageElement2);

    return true;
}

//----------------------------------------------------------------------------------
/**
\Alloc image improvement resource
\param[in]
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
bool CAcquisitionThread::PrepareForImageImprovement()
{
    VxInt32 emDxStatus = DX_OK;

    // Will not re-allocate lut buffer while it is already allocated
    if (m_pGammaLut == NULL)
    {
        // This value only for get Lut Length, could be any value in range(0.1-10)
        const double dGammaParam = 1.0;
        // Get LUT length of Gamma LUT(LUT length not determine by dGammaParam)
        emDxStatus = DxGetGammatLut(dGammaParam, NULL, &m_nGammaLutLength);
        if (emDxStatus != DX_OK)
        {
            QMessageBox::about(NULL, "DxGetGammatLUT Error", "Error : Get gamma LUT length failed!");
            RELEASE_ALLOC_ARR(m_pContrastLut);
            return false;
        }

        try
        {
            m_pGammaLut = new unsigned char[m_nGammaLutLength];
        }
        catch (std::bad_alloc& e)
        {
            RELEASE_ALLOC_ARR(m_pContrastLut);
            return false;
        }
    }

    // Will not re-allocate lut buffer while it is already allocated
    if (m_pContrastLut == NULL)
    {
        // This value only for get Lut Length, could be any value in range(-50-100)
        const int nContrastParam = 0;

        // Get LUT length of Contrast LUT(LUT length not determine by nContrastParam)
        emDxStatus = DxGetContrastLut(nContrastParam, NULL, &m_nContrastLutLength);
        if (emDxStatus != DX_OK)
        {
            QMessageBox::about(NULL, "DxGetContrastLut Error", "Error : Get contrast LUT length failed");
            RELEASE_ALLOC_ARR(m_pGammaLut);
            return false;
        }

        try
        {
            m_pContrastLut = new unsigned char[m_nContrastLutLength];
        }
        catch (std::bad_alloc& e)
        {
            RELEASE_ALLOC_ARR(m_pGammaLut);
            return false;
        }
    }

    return true;
}

//----------------------------------------------------------------------------------
/**
\Get color correction param slot
\param[in]      i64ColorCorrection  ColorCorrection param
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::SlotGetColorCorrectionParam(int64_t i64ColorCorrection)
{
    // Thread parameters lock
    QMutexLocker locker(&m_objParamMutex);

    if (i64ColorCorrection != 0)
    {
        m_i64ColorCorrection = i64ColorCorrection;
        m_bColorCorrection = true;
    }
    else
    {
        m_bColorCorrection = false;
    }

    return;
}

//----------------------------------------------------------------------------------
/**
\Get gamma LUT slot
\param[in]      pGammaLut  Gamma LUT pointer
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::SlotGetGammaLUT(unsigned char* pGammaLut)
{
    // Thread parameters lock
    QMutexLocker locker(&m_objParamMutex);

    if (pGammaLut != NULL)
    {
        memcpy(m_pGammaLut, pGammaLut, m_nGammaLutLength);
        m_bGammaRegulation = true;
    }
    else
    {
        m_bGammaRegulation = false;
    }

    return;
}


//----------------------------------------------------------------------------------
/**
\Get contrast LUT slot
\param[in]      pContrastLut  Contrast LUT pointer
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::SlotGetContrastLUT(unsigned char* pContrastLut)
{
    // Thread parameters lock
    QMutexLocker locker(&m_objParamMutex);

    if (pContrastLut != NULL)
    {
        memcpy(m_pContrastLut, pContrastLut, m_nContrastLutLength);
        m_bContrastRegulation = true;
    }
    else
    {
        m_bContrastRegulation = false;
    }

    return;
}

//----------------------------------------------------------------------------------
/**
\Get Acquisition error and send it to main thread(GXGetLastError can only get string from the thread which error occured)
\param[in]      emStatus    Error code
\param[out]
\return void
*/
//----------------------------------------------------------------------------------
void CAcquisitionThread::GetAcquistionErrorString(GX_STATUS emError)
{
    char*     error_info = NULL;
    size_t    size        = 0;
    GX_STATUS emStatus = GX_STATUS_SUCCESS;

    // Get the length of the error message and alloc memory for error info
    emStatus = GXGetLastError(&emError, NULL, &size);

    // Alloc memory for error info
    try
    {
        error_info = new char[size];
    }
    catch (std::bad_alloc& e)
    {
        emit SigAcquisitionError(QString("Alloc error info Faild!"));
        return;
    }

    // Get the error message and display
    emStatus = GXGetLastError (&emError, error_info, &size);

    if (emStatus != GX_STATUS_SUCCESS)
    {
        emit SigAcquisitionError(QString("Interface of GXGetLastError call failed!"));
    }
    else
    {
        emit SigAcquisitionError(QString("%1").arg(QString(QLatin1String(error_info))));
    }

    // Release memory alloced
    if (NULL != error_info)
    {
        delete[] error_info;
        error_info = NULL;
    }

    return;
}

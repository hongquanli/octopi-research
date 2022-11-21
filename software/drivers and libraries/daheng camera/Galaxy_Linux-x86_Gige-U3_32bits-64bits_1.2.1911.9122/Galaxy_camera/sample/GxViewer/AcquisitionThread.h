//--------------------------------------------------------------------------------
/**
\file     AcquisitionThread.h
\brief    CAcquisitionThread Class declaration file

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#ifndef ACQUISITIONTHREAD_H
#define ACQUISITIONTHREAD_H

#include <QThread>
#include <QMutex>
#include <deque>

#include "Common.h"
#include "ImageImprovement.h"

#include "Fps.h"

/// Image process status
enum PROC_STATUS
{
    PROC_SUCCESS = 0,
    PROC_FAIL = -1
};

class CAcquisitionThread : public QThread
{
    Q_OBJECT
public:
    explicit CAcquisitionThread(QObject *parent = 0);
    ~CAcquisitionThread();

    /// Get device handle from main-thread
    void GetDeviceHandle(GX_DEV_HANDLE);

    /// Alloc QImage resource for show frames on ImageLabel
    bool PrepareForShowImg();

    /// Alloc image improvement resource
    bool PrepareForImageImprovement();

    /// Push back to empty buffer deque
    void PushBackToEmptyBufferDeque(QImage*);

    /// Push back to show image deque
    void PushBackToShowImageDeque(QImage*);

    /// Pop front from show image deque
    QImage* PopFrontFromShowImageDeque();

    /// Pop front from empty buffer deque
    QImage* PopFrontFromEmptyBufferDeque();

    /// Clear both deque
    void ClearDeque();

    /// Get acquisition frame rate
    double GetImageAcqFps();

    uint64_t            m_ui64AcquisitionBufferNum; ///< Acquisition buffer number
    uint32_t            m_nFrameCount;              ///< Acquisition frame count
    bool                m_bAcquisitionThreadFlag;   ///< Acquistion thread run flag

private:
    /// Process Raw image to RGB image and do image improvment
    PROC_STATUS ImageProcess(PGX_FRAME_BUFFER, unsigned char*);

    /// Get Acquisition error and send it to main thread(GXGetLastError can only get string from the thread which error occured)
    void GetAcquistionErrorString(GX_STATUS);

    GX_DEV_HANDLE       m_hDevice;                  ///< Device Handle
    bool                m_bSoftTriggerOn;           ///< Trigger Mode is on
    int64_t             m_i64ColorFilter;           ///< The bayer format
    int64_t             m_i64ImageMaxWidth;         ///< The Maximum of image width
    int64_t             m_i64ImageWidth;            ///< The image width
    int64_t             m_i64ImageMaxHeight;        ///< The Maximum of image height
    int64_t             m_i64ImageHeight;           ///< The image height
    bool                m_bColorFilter;             ///< Support color pixel format or not

    bool                m_bColorCorrection;         ///< Flag : ColorCorrection is on or not
    bool                m_bGammaRegulation;         ///< Flag : GammaRegulation is on or not
    bool                m_bContrastRegulation;      ///< Flag : ContrastRegulation is on or not
    int64_t             m_i64ColorCorrection;       ///< Color correction param
    unsigned char*      m_pGammaLut;                ///< Gamma look up table
    int                 m_nGammaLutLength;          ///< Gamma look up table length
    unsigned char*      m_pContrastLut;             ///< Contrast look up table
    int                 m_nContrastLutLength;       ///< Contrast look up table length

    PGX_FRAME_BUFFER*   m_pstarrFrameBuffer;        ///< Array of PGX_FRAME_BUFFER
    unsigned char*      m_pRaw8Image;               ///< Intermediate variables between DxRaw16toRaw8 and DxRaw8toRGB24
    QImage*             m_pImageElement0;           ///< QImage for image showing
    QImage*             m_pImageElement1;           ///< QImage for image showing
    QImage*             m_pImageElement2;           ///< QImage for image showing

    std::deque<QImage*> m_objEmptyBufferDeque;      ///< Empty buffer deque
    std::deque<QImage*> m_objShowImageDeque;        ///< Show image deque

    CFps                m_objFps;                   ///< Fps calulate object

    QMutex              m_objParamMutex;            ///< Mutex for cross thread parameters
    QMutex              m_objDequeMutex;            ///< Mutex for deque


protected:
    /// The starting point for acquisition thread.
    /// Only code within this function are run in acquisition threads
    void run();

signals:
    /// Acquisition error occured signal
    void SigAcquisitionError(QString);

    /// Image process error occured signal
    void SigImageProcError(VxInt32);

public slots:

    /// Get color correction param slot
    void SlotGetColorCorrectionParam(int64_t);

    /// Get gamma LUT slot
    void SlotGetGammaLUT(unsigned char*);

    /// Get contrast LUT slot
    void SlotGetContrastLUT(unsigned char*);

};

#endif // ACQUISITIONTHREAD_H

using System;
using System.Runtime.InteropServices;
using Windows.Foundation;
using Windows.UI.Xaml;
using Windows.UI.Xaml.Controls;
using Windows.UI.Popups;
using Windows.UI.Core;
using Windows.ApplicationModel.Core;
using Windows.UI.Xaml.Media.Imaging;
using Windows.UI.Xaml.Controls.Primitives;
using Windows.Graphics.Imaging;
using Windows.Storage;
using Windows.Storage.Streams;

namespace demouwp
{
    [ComImport]
    [Guid("5B0D3235-4DBA-4D44-865E-8F1D0E4FD04D")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    unsafe interface IMemoryBufferByteAccess
    {
        void GetBuffer(out byte* buffer, out uint capacity);
    }

    /// <summary>
    /// An empty page that can be used on its own or navigated to within a Frame.
    /// </summary>
    public sealed partial class MainPage : Page
    {
        private Toupcam cam_ = null;
        private SoftwareBitmap bmp_ = null;
        private bool started_ = false;
        private DispatcherTimer timer_ = null;
        private uint count_ = 0;

        /*
         * The dispatcher MUST be cached, CoreApplication.MainView.CoreWindow may deadlock in worker thread. see:
         * (1) https://social.msdn.microsoft.com/Forums/windowsapps/en-US/5a68b924-fc6c-409d-85fc-0518909e892f/uwpc-why-does-await-coreapplicationmainviewcorewindowdispatcherrunasync-cause-deadlock
         *      It seems that the app gets deadlock from the MediaStreamSource.SampleRequested event’s thread to the CoreApplicationView’s ASTA thread to get the CoreWindow.
         *      It happens it the getter. There is a way to avoid this. You could get the right CoreWindow sometime safe and cache it, then call it directly rather than querying for it in the SampleRequested event handler.
         *      This might be slightly more efficient than making an extra cross thread call for every sample request.
         * (2) https://stackoverflow.com/questions/31839003/async-await-deadlock
         *      The real culprit is var window = view.CoreWindow.
         *      I guess there is some weird interaction between WinRT needing to switch to the UI thread to retrieve the reference to the window
         */
        private CoreDispatcher dispatcher_ = null;

        public MainPage()
        {
            this.InitializeComponent();

            snap_.IsEnabled = false;
            combo_.IsEnabled = false;
            auto_exposure_.IsEnabled = false;
            white_balance_once_.IsEnabled = false;
            slider_expotime_.IsEnabled = false;
            slider_temp_.IsEnabled = false;
            slider_tint_.IsEnabled = false;
            slider_temp_.Minimum = Toupcam.TEMP_MIN;
            slider_temp_.Maximum = Toupcam.TEMP_MAX;
            slider_tint_.Minimum = Toupcam.TINT_MIN;
            slider_tint_.Maximum = Toupcam.TINT_MAX;

            image_.Source = new SoftwareBitmapSource();
            dispatcher_ = CoreApplication.MainView.CoreWindow.Dispatcher;
        }

        private async void MessageBox(string text)
        {
            var msgDialog = new MessageDialog(text) { Title = "Error" };
            msgDialog.Commands.Add(new UICommand("OK", uiCommand => { }));
            await msgDialog.ShowAsync();
        }

        private void OnEventError()
        {
            cam_.Close();
            cam_ = null;
            MessageBox("Generic error.");
        }

        private void OnEventDisconnected()
        {
            cam_.Close();
            cam_ = null;
            MessageBox("Camera disconnect.");
        }

        private void OnEventExposure()
        {
            uint nTime = 0;
            if (cam_.get_ExpoTime(out nTime))
            {
                slider_expotime_.Value = (int)nTime;
                textblock_expotime_.Text = nTime.ToString();
            }
        }

        private bool TrytoPull(SoftwareBitmap bmp, Func<IntPtr, int, bool> pFunc)
        {
            /* Create, edit, and save bitmap images
             * https://docs.microsoft.com/en-us/windows/uwp/audio-video-camera/imaging 
             */
            using (BitmapBuffer buffer = bmp.LockBuffer(BitmapBufferAccessMode.Write))
            {
                if (buffer != null)
                {
                    using (IMemoryBufferReference reference = buffer.CreateReference())
                    {
                        unsafe
                        {
                            byte* dataInBytes;
                            uint capacity = 0;
                            ((IMemoryBufferByteAccess)reference).GetBuffer(out dataInBytes, out capacity);
                            return pFunc((IntPtr)dataInBytes, buffer.GetPlaneDescription(0).Stride);
                        }
                    }
                }
            }
            return false;
        }

        private void OnEventImage()
        {
            if (bmp_ != null)
            {
                Toupcam.FrameInfoV4 info = new Toupcam.FrameInfoV4();
                if (TrytoPull(bmp_, (IntPtr dataInBytes, int Stride) =>
                {
                    return cam_.PullImage(dataInBytes, 0, 32, Stride, out info); // check the return value
                }))
                {
                    SoftwareBitmapSource src = (SoftwareBitmapSource)image_.Source;
                    _ = src.SetBitmapAsync(bmp_);
                }
            }
        }

        private async void SaveToFile(SoftwareBitmap bmp)
        {
            StorageFile file = await ApplicationData.Current.LocalFolder.CreateFileAsync(string.Format("demouwp_{0}.jpg", ++count_), CreationCollisionOption.ReplaceExisting);
            using (IRandomAccessStream stream = await file.OpenAsync(FileAccessMode.ReadWrite))
            {
                BitmapEncoder enc = await BitmapEncoder.CreateAsync(BitmapEncoder.JpegEncoderId, stream);
                enc.SetSoftwareBitmap(bmp);
                await enc.FlushAsync();
            }
        }

        private void OnEventStillImage()
        {
            Toupcam.FrameInfoV3 info = new Toupcam.FrameInfoV3();
            if (cam_.PullImageV3(IntPtr.Zero, 1, 32, 0, out info))   /* peek the width and height */
            {
                SoftwareBitmap bmp = new SoftwareBitmap(BitmapPixelFormat.Bgra8, (int)info.width, (int)info.height, BitmapAlphaMode.Ignore);
                if (TrytoPull(bmp, (IntPtr dataInBytes, int Stride) =>
                {
                    return cam_.PullImageV3(dataInBytes, 1, 32, Stride, out info); // check the return value
                }))
                {
                    SaveToFile(bmp);
                }
            }
        }

        private void DelegateOnEventCallback(Toupcam.eEVENT evt)
        {
            /* It's not safe to directly use CoreApplication.MainView.CoreWindow.Dispatcher. we use the dispatcher from the cached variable */
            _ = dispatcher_.RunAsync(CoreDispatcherPriority.Normal, () =>
            {
                /* this run in the UI thread */
                if (cam_ != null)
                {
                    switch (evt)
                    {
                        case Toupcam.eEVENT.EVENT_ERROR:
                            OnEventError();
                            break;
                        case Toupcam.eEVENT.EVENT_DISCONNECTED:
                            OnEventDisconnected();
                            break;
                        case Toupcam.eEVENT.EVENT_EXPOSURE:
                            OnEventExposure();
                            break;
                        case Toupcam.eEVENT.EVENT_IMAGE:
                            OnEventImage();
                            break;
                        case Toupcam.eEVENT.EVENT_STILLIMAGE:
                            OnEventStillImage();
                            break;
                        case Toupcam.eEVENT.EVENT_TEMPTINT:
                            OnEventTempTint();
                            break;
                        default:
                            break;
                    }
                }
            });
        }

        private void OnEventTempTint()
        {
            int nTemp = 0, nTint = 0;
            if (cam_.get_TempTint(out nTemp, out nTint))
            {
                textblock_temp_.Text = nTemp.ToString();
                textblock_tint_.Text = nTint.ToString();
                slider_temp_.Value = nTemp;
                slider_tint_.Value = nTint;
            }
        }

        private void startDevice(string camId)
        {
            cam_ = Toupcam.Open(camId);
            if (cam_ != null)
            {
                cam_.put_Option(Toupcam.eOPTION.OPTION_RGB, 2); //RGB32

                auto_exposure_.IsEnabled = true;
                combo_.IsEnabled = true;
                snap_.IsEnabled = true;
                auto_exposure_.IsEnabled = true;
                InitExpoTime();
                if (cam_.MonoMode)
                {
                    slider_temp_.IsEnabled = false;
                    slider_tint_.IsEnabled = false;
                    white_balance_once_.IsEnabled = false;
                }
                else
                {
                    slider_temp_.IsEnabled = true;
                    slider_tint_.IsEnabled = true;
                    white_balance_once_.IsEnabled = true;
                    OnEventTempTint();
                }

                uint resnum = cam_.ResolutionNumber;
                uint eSize = 0;
                if (cam_.get_eSize(out eSize))
                {
                    for (uint i = 0; i < resnum; ++i)
                    {
                        int w = 0, h = 0;
                        if (cam_.get_Resolution(i, out w, out h))
                            combo_.Items.Add(w.ToString() + "*" + h.ToString());
                    }
                    combo_.SelectedIndex = (int)eSize;

                    int width = 0, height = 0;
                    if (cam_.get_Size(out width, out height))
                    {
                        /* The backend of WPF/UWP/WinUI is Direct3D/Direct2D, which is different from Winform's backend GDI.
                         * We use their respective native formats, Bgr32 in WPF/UWP/WinUI, and Bgr24 in Winform
                         */
                        bmp_ = new SoftwareBitmap(BitmapPixelFormat.Bgra8, width, height, BitmapAlphaMode.Ignore);
                        if (!cam_.StartPullModeWithCallback(new Toupcam.DelegateEventCallback(DelegateOnEventCallback)))
                            MessageBox("Failed to start camera");
                        else
                        {
                            bool autoexpo = true;
                            cam_.get_AutoExpoEnable(out autoexpo);
                            auto_exposure_.IsChecked = autoexpo;
                            slider_expotime_.IsEnabled = !autoexpo;
                        }

                        timer_ = new DispatcherTimer();
                        timer_.Interval = new TimeSpan(0, 0, 1);
                        timer_.Tick += (object sender, object e) =>
                        {
                            if (cam_ != null)
                            {
                                uint nFrame = 0, nTime = 0, nTotalFrame = 0;
                                if (cam_.get_FrameRate(out nFrame, out nTime, out nTotalFrame) && (nTime > 0))
                                    textblock_fps_.Text = string.Format("{0}; fps = {1:#.0}", nTotalFrame, ((double)nFrame) * 1000.0 / (double)nTime);
                            }
                        };
                        timer_.Start();
                        
                        started_ = true;
                    }
                }
            }
        }

        private void onClick_start(object sender, RoutedEventArgs e)
        {
            if (cam_ != null)
                return;

            Toupcam.DeviceV2[] arr = Toupcam.EnumV2();
            if (arr.Length <= 0)
                MessageBox("No camera found.");
            else if (1 == arr.Length)
                startDevice(arr[0].id);
            else
            {
                MenuFlyout flyout = new MenuFlyout();
                for (int i = 0; i < arr.Length; ++i)
                {
                    MenuFlyoutItem mitem = new MenuFlyoutItem { Text = arr[i].displayname, CommandParameter = arr[i].id };
                    mitem.Click += (object nsender, RoutedEventArgs ne) =>
                    {
                        string camId = (string)(((MenuFlyoutItem)nsender).CommandParameter);
                        if ((camId != null) && (camId.Length > 0))
                            startDevice(camId);
                    };
                    flyout.Items.Add(mitem);
                }
                flyout.ShowAt(start_);
            }
        }

        private void onClick_whitebalanceonce(object sender, RoutedEventArgs e)
        {
            cam_?.AwbOnce();
        }

        private void onChanged_temptint(object sender, RangeBaseValueChangedEventArgs e)
        {
            if ((cam_ != null) && started_)
            {
                cam_.put_TempTint((int)slider_temp_.Value, (int)slider_tint_.Value);
                textblock_temp_.Text = ((int)slider_temp_.Value).ToString();
                textblock_tint_.Text = ((int)slider_tint_.Value).ToString();
            }
        }

        private void onChanged_expotime(object sender, RangeBaseValueChangedEventArgs e)
        {
            if ((cam_ != null) && started_)
            {
                cam_.put_ExpoTime((uint)slider_expotime_.Value);
                textblock_expotime_.Text = ((uint)slider_expotime_.Value).ToString();
            }
        }

        private void onClick_auto_exposure(object sender, RoutedEventArgs e)
        {
            cam_?.put_AutoExpoEnable(auto_exposure_.IsChecked ?? false);
            slider_expotime_.IsEnabled = !auto_exposure_.IsChecked ?? false;
        }

        private void OnClick_snap(object sender, RoutedEventArgs e)
        {
            if (cam_ != null)
            {
                if (cam_.StillResolutionNumber <= 0)
                {
                    if (bmp_ != null)
                        SaveToFile(bmp_);
                }
                else
                {
                    MenuFlyout flyout = new MenuFlyout();
                    for (uint i = 0; i < cam_.ResolutionNumber; ++i)
                    {
                        int w = 0, h = 0;
                        cam_.get_Resolution(i, out w, out h);
                        MenuFlyoutItem mitem = new MenuFlyoutItem { Text = string.Format("{0} * {1}", w, h), CommandParameter = i }; //inbox
                        mitem.Click += (object nsender, RoutedEventArgs ne) =>
                        {
                            uint k = (uint)(((MenuFlyoutItem)nsender).CommandParameter); //unbox
                            if (k < cam_.StillResolutionNumber)
                                cam_.Snap(k);
                        };
                        flyout.Items.Add(mitem);
                    }
                    flyout.ShowAt(snap_);
                }
            }
        }

        private void InitExpoTime()
        {
            if (cam_ == null)
                return;

            uint nMin = 0, nMax = 0, nDef = 0;
            if (cam_.get_ExpTimeRange(out nMin, out nMax, out nDef))
            {
                slider_expotime_.Minimum = nMin;
                slider_expotime_.Maximum = nMax;
            }
            OnEventExposure();
        }

        private void onSelchange_combo(object sender, SelectionChangedEventArgs e)
        {
            if (cam_ != null)
            {
                uint eSize = 0;
                if (cam_.get_eSize(out eSize))
                {
                    if (eSize != combo_.SelectedIndex)
                    {
                        cam_.Stop();
                        cam_.put_eSize((uint)combo_.SelectedIndex);

                        InitExpoTime();
                        OnEventTempTint();

                        int width = 0, height = 0;
                        if (cam_.get_Size(out width, out height))
                        {
                            bmp_ = new SoftwareBitmap(BitmapPixelFormat.Bgra8, width, height, BitmapAlphaMode.Ignore);
                            cam_.StartPullModeWithCallback(new Toupcam.DelegateEventCallback(DelegateOnEventCallback));
                        }
                    }
                }
            }
        }
    }
}

//--------------------------------------------------------------------------------
/**
\file     main.cpp
\brief    Application entry, create the MainWindow

\version  v1.0.1807.9271
\date     2018-07-27

<p>Copyright (c) 2017-2018</p>
*/
//----------------------------------------------------------------------------------
#include <QApplication>
#include "GxViewer.h"

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);

    //Set Qt window style
    //QApplication::setStyle("windows");   // or windows etc.

    CGxViewer w;

    QFont font = w.font();
    font.setPointSize(10);
    w.setFont(font);

    w.show();

    return a.exec();
}

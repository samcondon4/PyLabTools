// The following ifdef block is the standard way of creating macros which make exporting 
// from a DLL simpler. All files within this DLL are compiled with the ORIEL_USB_EXPORTS
// symbol defined on the command line. This symbol should not be defined on any project
// that uses this DLL. This way any other project whose source files include this file see 
// ORIEL_USB_API functions as being imported from a DLL, whereas this DLL sees symbols
// defined with this macro as being exported.


// Following two includes are for string switching code
#include <map>
#include <string>
#include <cmath>

#include "cyapi.h"

#ifdef __cplusplus
extern "C"
{
#else
#typedef INT32 bool;  /* C does not know bool, only C++ */
#endif

#ifdef ORIEL_USB_EXPORTS
#define ORIEL_USB_API __declspec(dllexport)
#else
#define ORIEL_USB_API __declspec(dllimport)
#endif

// This class is exported from the Oriel_USB.dll
class ORIEL_USB_API COriel_USB {
public:

	
	/////////////////// FUNCTIONS
	COriel_USB(void);
	~COriel_USB(void);

	// Below were private
	INT32 Connect(UCHAR nUSBItem = 0);
	INT32 Disconnect(void);

	char * GetLibraryVersion(void);
	
	INT32 Send(const char* strCommand, INT32 bStaticDelay = false);
	INT32 Read(LPSTR strReturn);

	
	INT32 Query(const char* strCommand, char* strReturn, INT32 bStaticDelay = false);
	INT32 getCommandDelay(const char * command);

	INT32 getIsConnected();

private:

	int SendString(const char* strCommand);
	int QueryString(const char* strCommand, char* strReturn, INT32 bStaticDelay );

	INT32 m_bConnected = 0;

	CCyUSBDevice* usbDevices[10];
	USB_DEVICE_DESCRIPTOR usbDescr[10];
	CCyUSBDevice *myDevice;

	/////////////////// VARIABLES
	CCyUSBDevice *USBDevice;

	CCyUSBEndPoint *OutEndpt;
	CCyUSBEndPoint *InEndpt;

	INT32 DeviceIndex;

	bool bSendBusy = false, bReadBusy = false, bQueryBusy = false;

	const LONG XFERSIZE = 64;

	char buf[64];// [XFERSIZE];
	PUCHAR data = new UCHAR[XFERSIZE];
	PUCHAR inData = new UCHAR[XFERSIZE];

	OVERLAPPED outOvLap, inOvLap;

	BOOL bSuccess = false;

	char strTemp[124];
	char strVersion[124];
	INT32 Initialize(void);
//	INT32 Connect(void);
//	INT32 Disconnect(void);

	void stringToUpper(std::string &s);


};

#ifdef __cplusplus
}
#endif

// The following ifdef block is the standard way of creating macros which make exporting 
// from a DLL simpler. All files within this DLL are compiled with the CUSB_SCSI_EXPORTS
// symbol defined on the command line. This symbol should not be defined on any project
// that uses this DLL. This way any other project whose source files include this file see 
// CUSB_SCSI_API functions as being imported from a DLL, whereas this DLL sees symbols
// defined with this macro as being exported.

#include <winioctl.h> // SCSI typedef's

#define CUSB_SCSI_EXPORTS

#ifdef CUSB_SCSI_EXPORTS
#define CUSB_SCSI_API __declspec(dllexport)
#else
#define CUSB_SCSI_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif 

// Default Product Variables for USB connect VID/PID
static char vendorID[] = "Newport ";// This is verified correct string (8 char for vend, 16 for prod)
static char productID[] = "OPS             ";
#define BLOCKSIZE 512
#define MSC_USER_CMD_BLOCK  0x000186A0 //or 100,000  get zero's back on command parse error



// This class is exported from the ORIEL_CONTROL.dll
class CUSB_SCSI{
public:
	CUSB_SCSI(void);
	~CUSB_SCSI(void);

	HANDLE ConnectDrive(char drive, char *vendor = vendorID, char *product = productID);
	PSTORAGE_DEVICE_DESCRIPTOR getDescriptor(HANDLE theHandle);
	INT32 ConnectSCSI(char drive, char *vendor = vendorID, char *product = productID);
	INT32 Connect(char *vendor = vendorID, char *product = productID);
	INT32 Disconnect();

	INT32 WriteBlock( char *message, int mlength);

	INT32 ReadBlock( char *data);


private:
	HANDLE m_fileHandle = NULL;
	char m_driveLetter = 0;
	HANDLE m_fileHandles[26];

	HANDLE m_hLastDevice = NULL;
	char m_nLastDriveLetter = 0;
	
};


#ifdef __cplusplus
}
#endif 
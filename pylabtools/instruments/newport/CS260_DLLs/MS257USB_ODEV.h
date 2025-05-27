// cs_USB DLL Universal Header File


// WARNING: This file must maintain DLL compatibility with
// C/C++, Visual Basic, LabVIEW and MATLAB, whether or not the
// client includes this file directly.


// declare MS257USB_API function prefix depending on whether this
// file is used as import or export
#ifdef MS257USB_EXPORTS		// declared only during DLL build
#define MS257USB_API		// see MS257USB.def for exports
#else
#define MS257USB_API __declspec(dllimport)	// declare as import
#endif

// declare calling convention--this must be __stdcall
// for VB compatibility
#define CCONV __stdcall

// exported functions must use C-style (undecorated) names
// for C, VB, LV, and MATLAB compatibility
#ifdef __cplusplus
extern "C" {
#endif

MS257USB_API int CCONV ms_Open (unsigned long serialNo);
MS257USB_API long CCONV ms_Close (int deviceID);
MS257USB_API long CCONV ms_Write (int deviceID, char* statement);
MS257USB_API char* CCONV ms_Read (int deviceID);
MS257USB_API char* CCONV ms_ReadNowait (int deviceID);
MS257USB_API long CCONV ms_GetLastError (void);
MS257USB_API char* CCONV ms_GetDLLVersion (void);
MS257USB_API void CCONV ms_RescanBus (void);

// end previous name-decoration containment block
#ifdef __cplusplus
}
#endif
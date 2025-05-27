// The following ifdef block is the standard way of creating macros which make exporting 
// from a DLL simpler. All files within this DLL are compiled with the ORIEL_CONTROL_EXPORTS
// symbol defined on the command line. This symbol should not be defined on any project
// that uses this DLL. This way any other project whose source files include this file see 
// ORIEL_CONTROL_API functions as being imported from a DLL, whereas this DLL sees symbols
// defined with this macro as being exported.
#ifndef ODEVICE_HEADER
#define ODEVICE_HEADER 1


#include "Oriel_USB_ODEV.h"	// CS USB
#include "MS257USB_ODEV.h"	// MS257 USB
#include "USB_SCSI.h"	// OPS USB
#include "ORIEL_CONTROL.h"	// OPS USB

#include <basetsd.h>

#ifdef __cplusplus
extern "C"
{
#else
#typedef INT32 bool;  /* C does not know bool, only C++ */
#endif

//#define ODEVICE_EXPORTS 1 
// for LabVIEW, should be defined in compiler, also "INT32=int" in preprocessor defines

//#define ORIEL_USB_EXPORTS

#ifdef ODEVICE_EXPORTS
#define ODEVICE_API __declspec(dllexport)
#else
#define ODEVICE_API __declspec(dllimport)
#endif



#pragma once

/// This will discover Oriel USB devices connected and return a list of them.
/// Note:  It discovers at load time, so if there are new connections a restart is needed.
INT32 ODEVICE_API odev_list_resources(char *devices, INT32 nType = 0);

/// Device Open, if no parameters are provided, it will connect to first device found, must open before talking to devices
INT32 ODEVICE_API odev_open(INT32 nIndex = 0, INT32 nActiveDev = 0);

/// Close Device that has been openned
INT32 ODEVICE_API odev_close(INT32 nActiveDev = 0);

/// Write command to instrument (generally one that does not expect an answer)
INT32 ODEVICE_API odev_write(const char* data = "IDN?", INT32 nActiveDev = 0);

/// Read a response from the instrument, generally should not be used, use ask() instead
INT32 ODEVICE_API odev_read(char* response, INT32 nActiveDev = 0);

/// Ask a question, send a query command and wait for the answer
INT32 ODEVICE_API odev_ask(const char* data, char* response, INT32 nActiveDev = 0);

#ifdef __cplusplus
}
#endif 

#endif 
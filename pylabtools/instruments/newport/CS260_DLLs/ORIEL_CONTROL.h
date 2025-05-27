// The following ifdef block is the standard way of creating macros which make exporting 
// from a DLL simpler. All files within this DLL are compiled with the ORIEL_CONTROL_EXPORTS
// symbol defined on the command line. This symbol should not be defined on any project
// that uses this DLL. This way any other project whose source files include this file see 
// ORIEL_CONTROL_API functions as being imported from a DLL, whereas this DLL sees symbols
// defined with this macro as being exported.
#ifndef ORIEL_CONTROL_HEADER
#define ORIEL_CONTROL_HEADER 1

#include <basetsd.h>

#ifdef __cplusplus
extern "C"
{
#else
#typedef INT32 bool;  /* C does not know bool, only C++ */
#endif

//#define ORIEL_CONTROL_EXPORTS 1 
// for LabVIEW, should be defined in compiler, also "INT32=int" in preprocessor defines

#ifdef ORIEL_CONTROL_EXPORTS
#define ORIEL_CONTROL_API __declspec(dllexport)
#else
#define ORIEL_CONTROL_API __declspec(dllimport)
#endif



// Product Variables for USB connect VID/PID
static char vendor[] = "Newport ";// This is verified correct string (8 char for vend, 16 for prod)
static char product[] = "OPS             ";



// This class is exported from the ORIEL_CONTROL.dll
class ORIEL_CONTROL_API CORIEL_CONTROL {
public:
	CORIEL_CONTROL(void);
	~CORIEL_CONTROL(void);

	BOOL m_bConnected = false;
	BOOL m_bFast_CS = true;

	INT32 open(INT32 nIndex = 0); // First device with VID/PID
	INT32 close();
	INT32 write(const char* data = "IDN?");
	INT32 read(char* response);
	INT32 cs_write(const char* data, int RemoveEcho = 0, int VerifyDone = 0);
	INT32 cs_read(char* response, int RemoveEcho = 1);
	INT32 cs_query(const char* data, char* response);
	INT32 query(const char* data, char* response);

	INT32 list_resources(char *devices, INT32 nType = 0);  // nType - {0 - ALL, 1 - OPS, 2 - CS, 3 - MS257}



private:
	HANDLE ConnectDrive(char drive, char *vendor, char *product);
	
public:
	INT32 get_cs_shutter_open(INT32 &Open);
	INT32 set_cs_shutter_open(INT32 Open);
	INT32 get_cs_wavelength(double &Wavelength);
	INT32 set_cs_wavelength(double Wavelength);

	////// Standard OPS
	INT32 get_stb(INT32 &STB);
	INT32 get_esr(INT32 &ESR);
	INT32 get_amps(double &Amps);
	INT32 get_volts(double &Volts);
	INT32 get_watts(INT32 &Watts);
	INT32 get_lamp_hrs(INT32 &LampHrs);

	INT32 get_amps_preset(double &Amps);
	INT32 get_power_preset(INT32 &Watts);
	INT32 get_amps_limit(double &Amps);
	INT32 get_power_limit(INT32 &Watts);
	INT32 set_amps_preset(double Amps);
	INT32 set_power_preset(INT32 Watts);
	INT32 set_amps_limit(double Amps);
	INT32 set_power_limit(INT32 Watts);

	INT32 get_id(char* Identity);
	///~~~~~
	INT32 set_lamp_on(INT32 On); // START/STOP
	INT32 get_shutter_open(INT32 &Open);
	INT32 set_mode(INT32 Mode); // 0: Power, 1: Current, 2:Intensity
	INT32 set_exposure_on(INT32 On); // STARTEXP/STOPEXP
	INT32 get_detector_reading(double &uAmps);
	INT32 get_faults(INT32 &Faults);

private:
	double query_dbl_value(const char* strCommand);
	INT32 set_dbl_value(const char* strCommand, double dblValue);
	INT32 set_int_value(const char* strCommand, INT32 nValue);
	INT32 read_cs_echo(void);
};


INT32 format_command(const char* strCommand, char* strOPSCommand, INT32 AddMonoPrefix = 0);
INT32 trim_response(char* strToTrim);
INT32 trim_echo(char* strToTrim);
// Example Exports... to Remove
//extern ORIEL_CONTROL_API INT32 nORIEL_CONTROL;

//ORIEL_CONTROL_API INT32 fnORIEL_CONTROL(void);

//CORIEL_CONTROL m_this;
//
//ORIEL_CONTROL_API INT32 open(INT32 nIndex = 0); // First device with VID/PID
//
//ORIEL_CONTROL_API INT32 close();
//ORIEL_CONTROL_API INT32 write(const char* data = "IDN?");
//ORIEL_CONTROL_API INT32 read(char* response);
//ORIEL_CONTROL_API INT32 cs_write(const char* data, int RemoveEcho = 0, int VerifyDone = 0);
//ORIEL_CONTROL_API INT32 cs_read(char* response, int RemoveEcho = 1);
//ORIEL_CONTROL_API INT32 cs_query(const char* data, char* response);
//
//ORIEL_CONTROL_API INT32 query(const char* data, char* response);
//
//ORIEL_CONTROL_API INT32 list_resources(char *devices);
//
//ORIEL_CONTROL_API INT32 get_cs_shutter_open(INT32 &Open);
//ORIEL_CONTROL_API INT32 set_cs_shutter_open(INT32 Open);
//ORIEL_CONTROL_API INT32 get_cs_wavelength(double &Wavelength); // done first, works
//ORIEL_CONTROL_API INT32 set_cs_wavelength(double Wavelength);
////
////////// Standard OPS
//ORIEL_CONTROL_API INT32 get_stb(INT32 &STB);
//ORIEL_CONTROL_API INT32 get_esr(INT32 &ESR);
//ORIEL_CONTROL_API INT32 get_amps(double &Amps);
//ORIEL_CONTROL_API INT32 get_volts(double &Volts);
//ORIEL_CONTROL_API INT32 get_watts(INT32 &Watts);		
//ORIEL_CONTROL_API INT32 get_lamp_hrs(INT32 &LampHrs);
//		
//ORIEL_CONTROL_API INT32 get_amps_preset(double &Amps);
//ORIEL_CONTROL_API INT32 get_power_preset(INT32 &Watts);
//ORIEL_CONTROL_API INT32 get_amps_limit(double &Amps);
//ORIEL_CONTROL_API INT32 get_power_limit(INT32 &Watts);
//ORIEL_CONTROL_API INT32 set_amps_preset(double Amps);
//ORIEL_CONTROL_API INT32 set_power_preset(INT32 Watts);
//ORIEL_CONTROL_API INT32 set_amps_limit(double Amps);
//ORIEL_CONTROL_API INT32 set_power_limit(INT32 Watts);
//
//ORIEL_CONTROL_API INT32 get_id(char* Identity);
/////~~~~~
//ORIEL_CONTROL_API INT32 set_lamp_on(INT32 On); // START/STOP
//ORIEL_CONTROL_API INT32 get_shutter_open(INT32 &Open);
//ORIEL_CONTROL_API INT32 set_mode(INT32 Mode); // 0: Power, 1: Current, 2:Intensity
//ORIEL_CONTROL_API INT32 set_exposure_on(INT32 On); // STARTEXP/STOPEXP
//ORIEL_CONTROL_API INT32 get_detector_reading(double &uAmps);
//ORIEL_CONTROL_API INT32 get_faults(INT32 &Faults);

#ifdef __cplusplus
}
#endif 

#endif 
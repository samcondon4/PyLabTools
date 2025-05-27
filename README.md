# PyLabTools

PyLabTools provides a general purpose laboratory data acquisition and instrument control system with driver level 
software for control of testbed instrumentation, graphical interfaces, real-time data visualization, processing, data archival tools 
for a variety of output file formats, and mechanisms to run manual and automated measurements. Each component is highly configurable with 
minimal manual coding required by a user.

PyLabTools is inspired heavily from the existing PyMeasure project. Instrument drivers from PyMeasure are used 
directly, and the `Procedure` class is used to handle automated measurement scripts. PyLabTools adds a configuration
file based system which streamlines the process of building up a measurement interface, adds support for several
output data formats, decouples measurement data output from live plotting, and adds additional features which are
detailed in the official documentation.


PyLabTools was initially developed under the name *SPHERExLabTools* for use in the optical calibration of NASA's
medium class explorer telescope, SPHEREx. For a description of this early version of the package, see the 
[SPHERExLabTools Conference Proceedings](https://www.spiedigitallibrary.org/conference-proceedings-of-spie/12180/121804S/SPHERExLabTools-SLT--a-Python-data-acquisition-system-for-SPHEREx/10.1117/12.2630662.full?SSO=1)

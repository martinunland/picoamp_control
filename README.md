# PicoampControl 

PicoampControl was created to control the KEITHLEY picoampere meter 6482.

## Installation
This library uses pyvisa. You need to install NI-VISA, follow https://pyvisa.readthedocs.io/en/latest/introduction/getting.html#backend
You can install the library using pip:

```bash
pip install git+https://github.com/martinunland/picoamp_control.git
```
Or download the wheel in repositories and pip:
```bash
pip install picoamp_control-0.1.0-py3-none-any.whl
```


## Usage
First, import the PicoampControl class, create a PicoampControl object and connect to the picoamperemeters:

```python

from picoamp_control import PicoampControl
picoamp = PicoampControl()
picoamp.connect() 
```

connect() will try to find the picoamp device. If it fails, you will have to pass the com port, e.g.:
```python
picoamp.connect(com='COM3')  # Replace 'COM3' with the appropriate port for your device
```
After connecting, you can configure the instrument using various methods. auto_config should be enough for almost all uses
```python
picoamp.auto_config(plc=10) #plc is number of power cycles that are integrated for a reading, 1plc = 20ms in a 50Hz utility frequency (EU)
```
You can configure the measurement range manually, passing a valide range with the enum CurrentRanges, but I recommend always using the autorange (applied in auto_config)...
```python
from picoamp_control import CurrentRanges
picoamp.set_channel_range(range_ch1: CurrentRanges.rng_2_mA, range_ch2: CurrentRanges.rng_20_nA)
```

Finally, you can use the get_mean_current() method to retrieve the mean and standard error of the mean for a specified number of current readings:

```python
(mean_ch1, error_ch1), (mean_ch2, error_ch2) = picoamp.get_mean_current(n=10)
```

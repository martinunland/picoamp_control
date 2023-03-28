import logging
from typing import Tuple
import numpy as np
import visa
import time
from enum import Enum
import re

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


class BasicCMDs(Enum):
    FORMAT = ":FORMat:ELEMents"
    RANGE_CHANNEL_1 = ":SENSe1:CURRent:RANGe"
    RANGE_CHANNEL_2 = ":SENSe2:CURRent:RANGe"
    AUTO_RANGE_CHANNEL_1 = ":SENSe1:CURRent:RANGe:AUTO 1"
    AUTO_RANGE_CHANNEL_2 = ":SENSe2:CURRent:RANGe:AUTO 1"
    SPEED = ":SENSe:CURRent:NPLCycles"
    AUTOZERO_ON = ":SYST:AZER ON"
    AUTOZERO_OFF = ":SYST:AZER OFF"
    SWEEPS = ":ARM:SEQuence:LAYer:COUNt"
    RESET = "*RST"
    READ_CURRENT = "READ?"  

    def __str__(self):
        return self.value


class FilterCMDs(Enum):
    # see 4-11 of reference manual pdf. Implemented only "average" mode
    FILTER_COUNT = ":AVER:COUN"
    SET_FILTER_ON = ":AVER ON"
    SET_FILTER_OFF = ":AVER OFF"
    FILTER_NOISE_WINDOW = ":AVER:ADV:NTO"
    ADVANCED_FILTER_ON = "AVER:ADV ON"
    ADVANCED_FILTER_OFF = "AVER:ADV OFF"

    def __str__(self):
        return self.value


class CurrentRanges(Enum):
    # see 3-2 of reference manual pdf.
    rng_2_nA = 2e-9
    rng_20_nA = 20e-9
    rng_200_nA = 200e-9
    rng_2_uA = 2e-6
    rng_20_uA = 20e-6
    rng_200_uA = 200e-6
    rng_2_mA = 2e-3
    rng_20_mA = 20e-3

    @property
    def description(self):
        resolutions = {
            self.rng_2_nA: "1 fA",
            self.rng_20_nA: "10 fA",
            self.rng_200_nA: "100 fA",
            self.rng_2_uA: "1 pA",
            self.rng_20_uA: "10 pA",
            self.rng_200_uA: "100 pA",
            self.rng_2_mA: "1 nA",
            self.rng_20_mA: "10 nA",
        }
        descriptions = {}
        for key, val in resolutions.items():
            descriptions[
                key
            ] = f"maximal resolution {val} and maximum reading {self.value * 1.05}"
        return descriptions[self]

    def __str__(self):
        return self.description


class PicoampControl:
    def __init__(self):
        self._rm = None

    def _query(self, command: str, max_retries=100) -> str:
        log.debug(f"Query command {command}.")
        for attempt in range(max_retries):
            try:
                return self._rm.query(command)

            except visa.VisaIOError as err:
                log.warning(f"Error in query attempt {attempt + 1}: {err}")
                self._rm.write(f"{BasicCMDs.RESET}")
                self.config_instrument()
                time.sleep(0.1)
        mssg = f"Reached maximum of {max_retries} retries. Something is wrong, check the picoamperemeter."
        log.exception(mssg)
        raise Exception(mssg)

    def _write(self, command: str) -> None:
        if type(command) in [BasicCMDs, FilterCMDs]:
            command = str(command)
        log.debug(f"Sending command {command}.")
        self._rm.write(command)

    def find_instrument(self, identifier: str) -> str:
        """
        Find the instrument with a given identifier and return its port.

        Args:
            identifier (str): The identifier string to search for in the connected devices.

        Returns:
            str: The port of the identified instrument.
        """
        rm = visa.ResourceManager()
        connected_devices = rm.list_resources()
        instrument_address = None
        log.info(f"Searching for picoamperemeter's port, assuming identifier {identifier}...")
        for device in connected_devices:
            try:
                with rm.open_resource(device) as temp_resource:
                    temp_resource.timeout = 3000
                    instrument_info = temp_resource.query("*IDN?")
                    if re.search(identifier, instrument_info):
                        return temp_resource.resource_name
            except (visa.VisaIOError, ValueError):
                continue

        if instrument_address is None:
            mssg = f"No instrument found with identifier '{identifier}'. Provide a com port directly or check connection to picoamperemeter..."
            log.critical(mssg)
            raise Exception(mssg)
        
        return instrument_address

    def connect(self, com: str = None, identifier: str = "KEITHLEY INSTRUMENTS INC.,MODEL 6482,4008415,A01   May 29 2012 09:36:59/A02  /E"):
        if com is None:
            com = self.find_instrument(identifier)
        
        log.info(f"Connecting to picoamperemeter on port {com}...")
        rm = visa.ResourceManager()
        self._rm = rm.open_resource(com)
        self.configure_resource_manager()

    def configure_resource_manager(self) -> None:
        self._rm.read_termination = "\r"
        self._rm.timeout = 20000

    def activate_average_filter(self, filter_count: int = 10) -> None:
        """
        The moving average filter uses a first-in, first-out stack. When the stack (filter count) becomes full,
        the readings are averaged, yielding a filtered reading. For each subsequent reading placed into
        the stack, the oldest reading is discarded. The stack is reaveraged, yielding a new reading.
        Args:
            filter_count (int): number of readings to be averaged
        """
        self._write(f"{FilterCMDs.FILTER_COUNT} {filter_count}")
        self._write(FilterCMDs.SET_FILTER_ON)

    def activate_advanced_filter(self, noise_window: int) -> None:
        """
        Advanced filter: The advanced filter is part of the moving filter. With the advanced filter enabled, a
        user-programmable noise “window” is used with the moving filter. The noise window, which is
        expressed as a percentage of range (0 to 105 percent), allows a faster response time to large
        signal step changes. As previously explained, if the readings are within the noise window, the
        moving filter operates normally. If, however, a reading falls outside of the window, the stack is
        flushed of old readings and filled with the new reading.
        For example, assume the window is set to 10 percent and the 20 mA range is selected. Therefore,
        the noise window is ±2 mA (20 mA × 10% = 2 mA). Also assume the first reading is 2 mA. During
        normal filter operation, the stack is filled with that reading. If each subsequent reading is within
        ±2 mA of the previous reading, the filter operates normally. Now assume a 10 mA noise spike
        occurs.
        """
        self._write(f"{FilterCMDs.FILTER_NOISE_WINDOW} {noise_window}")
        self._write(FilterCMDs.ADVANCED_FILTER_ON)

    def deactivate_average_filter(self) -> None:
        self._write(FilterCMDs.SET_FILTER_OFF)

    def deactivate_advanced_filter(self) -> None:
        self._write(FilterCMDs.ADVANCED_FILTER_OFF)

    def set_channel_range(
        self, range_ch1: CurrentRanges, range_ch2: CurrentRanges
    ) -> None:
        log.warning(
            "In general, the auto-range set by the auto_config method works better than setting the measurement range manually. You may get saturated values!"
        )
        for i, (range, CMD) in enumerate(
            zip(
                [range_ch1, range_ch2],
                [BasicCMDs.RANGE_CHANNEL_1, BasicCMDs.RANGE_CHANNEL_2],
            )
        ):
            if isinstance(range, CurrentRanges):
                log.info(f"Selected range for channel {i + 1}: {range.value}; {range}")
                self._write(f"{CMD} {range.value}")
            else:
                log.error(
                    "Please pass an element of the CurrentRanges enum. Get it with 'from picoamp_control import CurrentRanges'"
                )

    def auto_config(self, plc: int = 10) -> None:
        log.info(
            f"Configuring default setting: autozero activated, auto-range for channel 1 & 2, integration of {plc} power line cylcles."
        )
        self._write(BasicCMDs.AUTOZERO_ON)
        self._write(BasicCMDs.AUTO_RANGE_CHANNEL_1)
        self._write(BasicCMDs.AUTO_RANGE_CHANNEL_2)
        self._write(f"{BasicCMDs.SPEED} {plc}")

    def deactivate_autozero(self) -> None:
        """Every analog-to-digital conversion (current reading) is calculated from a series of zero, reference,
        and signal measurements. With autozero enabled, all three of these measurements are performed
        for each reading to achieve rated accuracy. With autozero disabled, zero and reference are not
        measured. Disabling autozero increases measurement speed, but zero drift will eventually
        degrade accuracy."""
        log.info("Activating autozero.")
        self._write(BasicCMDs.AUTOZERO_OFF)

    def activate_autozero(self) -> None:
        """Every analog-to-digital conversion (current reading) is calculated from a series of zero, reference,
        and signal measurements. With autozero enabled, all three of these measurements are performed
        for each reading to achieve rated accuracy. With autozero disabled, zero and reference are not
        measured. Disabling autozero increases measurement speed, but zero drift will eventually
        degrade accuracy."""
        log.info("Deactivating autozero.")
        self._write(BasicCMDs.AUTOZERO_ON)

    def close_instrument(self) -> None:
        log.info("Disconnecting picoamperemeter...")
        self._rm.close()

    def get_currents(self, n: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get 'n' current readings from the picoamperemeter.

        Args:
            n (int): Number of readings to acquire.

        Returns:
            Tuple[np.ndarray, np.ndarray]: A tuple containing two NumPy arrays with the acquired current readings for each channel.
        """
        self._write(f"{BasicCMDs.SWEEPS} {n}")
        reply = self._query(BasicCMDs.READ_CURRENT)
        reply = reply.split(",")
        current_readings = [float(current) for current in reply]
        ch1 = np.array(current_readings[::2])
        ch2 = np.array(current_readings[1::2])
        return ch1, ch2

    def get_mean_current(
        self, n: int
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        Get the mean and standard error of the mean (SEM) for 'n' current readings from both channels.

        Args:
            n (int): Number of readings to acquire.

        Returns:
            Tuple[Tuple[float, float], Tuple[float, float]]: A tuple containing two tuples, each with the mean and SEM for each channel.
        """
        if n < 3:
            log.warning(
                "You need at least 3 current measurements to calculate the uncertainty of the mean. Measuring with n=3..."
            )
            n = 3

        ch1, ch2 = self.get_currents(n)

        mean_ch1 = np.mean(ch1)
        sem_ch1 = np.std(ch1) / np.sqrt(ch1.size - 1)

        mean_ch2 = np.mean(ch2)
        sem_ch2 = np.std(ch2) / np.sqrt(ch2.size - 1)

        return ((mean_ch1, sem_ch1), (mean_ch2, sem_ch2))

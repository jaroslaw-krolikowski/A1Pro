from __future__ import annotations


class TuyaBLEError(Exception):
    """Base class for Tuya BLE errors."""


class TuyaBLEEnumValueError(TuyaBLEError):
    """Raised when value assigned to DP_ENUM datapoint has unexpected type."""

    def __init__(self) -> None:
        super().__init__("Value of DP_ENUM datapoint must be unsigned integer")


class TuyaBLEDataFormatError(TuyaBLEError):
    """Raised when data in Tuya BLE structures formatted in wrong way."""

    def __init__(self) -> None:
        super().__init__("Incoming packet is formatted in wrong way")


class TuyaBLEDataCRCError(TuyaBLEError):
    """Raised when data packet has invalid CRC."""

    def __init__(self) -> None:
        super().__init__("Incoming packet has invalid CRC")


class TuyaBLEDataLengthError(TuyaBLEError):
    """Raised when data packet has invalid length."""

    def __init__(self) -> None:
        super().__init__("Incoming packet has invalid length")


class TuyaBLEDeviceError(TuyaBLEError):
    """Raised when Tuya BLE device returned error in response to command."""

    def __init__(self, code: int | str) -> None:
        if isinstance(code, str):
            super().__init__(code)
        else:
            super().__init__(("BLE device returned error code %s") % (code))


class TuyaBLECommandTimeoutError(TuyaBLEError):
    """Raised when a command did not reach the device before its deadline.

    The command is dropped, so it can never run minutes later.
    """

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        super().__init__(f"The device did not take the command within {deadline:g} s")

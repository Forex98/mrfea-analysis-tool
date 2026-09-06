##
# @file configreader.py
# @brief Configuration file reader for TXT format files.
#
# This module reads a key=value configuration file and converts each value
# into the appropriate Python type (string, int/float, bool, list, tuple, None).

import os
from typing import Dict, Any, Optional, Tuple, Union, List

##
# @class ConfigReader
# @brief Class for reading and parsing TXT configuration files.
#
# This class reads a configuration file containing key=value pairs
# and automatically converts values into appropriate Python types:
# - strings
# - integers and floats
# - booleans
# - lists
# - tuples
# - None/null
#
# Keys are internally stored in uppercase format.
class ConfigReader:
    ##
    # @brief Constructor of the ConfigReader class.
    #
    # Initializes the configuration reader, verifies that the file exists,
    # and loads its content into the internal dictionary.
    #
    # @param filename Path of the configuration file to read.
    def __init__(self, filename: str) -> None:
        ##
        # @brief Name of the configuration file.
        self.filename = filename

        ##
        # @brief Dictionary containing parameters read from the file.
        self.config_dict: Dict[str, Any] = {}

        self._validate_file_exists()
        self._read_configuration_file()

    ##
    # @brief Checks that the configuration file exists.
    #
    # @exception FileNotFoundError Raised if the file does not exist.
    def _validate_file_exists(self) -> None:

        if not os.path.exists(self.filename):
            raise FileNotFoundError(
                f"Configuration file '{self.filename}' not found. "
                f"Please ensure the file exists at the specified path."
            )

    ##
    # @brief Reads the configuration file line by line.
    #
    # Each line is passed to the parsing method to extract
    # the key-value pair.
    #
    # @exception ValueError Raised if the file cannot be read.
    def _read_configuration_file(self) -> None:

        try:
            with open(self.filename, 'r', encoding='utf-8') as config_file:
                for line_number, line in enumerate(config_file, 1):
                    self._process_configuration_line(line.strip(), line_number)
        except IOError as error:
            raise ValueError(
                f"Failed to read configuration file '{self.filename}': {error}"
            ) from error

    ##
    # @brief Processes a single line of the configuration file.
    #
    # Empty or commented lines are ignored. All other lines are
    # interpreted as key=value pairs.
    #
    # @param line Line from the configuration file.
    # @param line_number Line number in the file.
    def _process_configuration_line(
        self,
        line: str,
        line_number: int
    ) -> None:

        if not line or line.startswith('#'):
            return
        try:
            key, value = self._parse_key_value_pair(line, line_number)
            self.config_dict[key] = value
        except ValueError as error:
            print(f"Warning (line {line_number}): {error}")

    ##
    # @brief Parses a line containing a key=value pair.
    #
    # @param line Line to analyze.
    # @param line_number Line number in the file.
    # @return Tuple containing the key and the converted value.
    #
    # @exception ValueError Raised if the line format is invalid.
    def _parse_key_value_pair(
        self,
        line: str,
        line_number: int
    ) -> Tuple[str, Any]:

        if '=' not in line:
            raise ValueError(
                f"Invalid format: expected 'key=value', got '{line}'"
            )

        key, raw_value = line.split('=', 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if not key:
            raise ValueError(f"Empty key in line: '{line}'")

        parsed_value = self._parse_configuration_value(raw_value)

        return key.upper(), parsed_value

    ##
    # @brief Converts a string into the appropriate Python type.
    #
    # The method attempts to interpret the value as:
    # - quoted string
    # - list
    # - tuple
    # - boolean
    # - None/null
    # - integer or float
    # - plain string
    #
    # @param value_string Value in string format.
    # @return Value converted to the correct Python type.
    def _parse_configuration_value(self, value_string: str) -> Any:

        if self._str_quoted(value_string):
            return value_string[1:-1]

        if value_string.startswith('[') and value_string.endswith(']'):
            return self._parse_list_value(value_string)

        if value_string.startswith('(') and value_string.endswith(')'):
            return self._parse_tuple_value(value_string)

        if value_string.lower() == 'true':
            return True
        elif value_string.lower() == 'false':
            return False
        elif value_string.lower() in ['none', 'null']:
            return None

        numeric_value = self._parse_numeric_value(value_string)
        if numeric_value is not None:
            return numeric_value

        return value_string

    ##
    # @brief Checks whether a string is enclosed in quotes.
    #
    # @param value_string String to check.
    # @return True if the string is quoted.
    @staticmethod
    def _str_quoted(value_string: str) -> bool:

        if len(value_string) < 2:
            return False

        return (
            (value_string[0] == '"' and value_string[-1] == '"') or
            (value_string[0] == "'" and value_string[-1] == "'")
        )

    ##
    # @brief Converts a string representing a list.
    #
    # @param list_string String containing a list in the format [a, b, c].
    # @return Python list with converted values.
    def _parse_list_value(self, list_string: str) -> List[Any]:

        inner_content = list_string[1:-1].strip()
        if not inner_content:
            return []

        elements = [
            element.strip()
            for element in inner_content.split(',')
        ]

        return [
            self._parse_configuration_value(element)
            for element in elements
        ]

    ##
    # @brief Converts a string representing a tuple.
    #
    # @param tuple_string String containing a tuple in the format (a, b, c).
    # @return Python tuple with converted values.
    def _parse_tuple_value(self, tuple_string: str) -> Tuple[Any, ...]:

        inner_content = tuple_string[1:-1].strip()
        if not inner_content:
            return ()

        elements = [
            element.strip()
            for element in inner_content.split(',')
        ]

        return tuple(
            self._parse_configuration_value(element)
            for element in elements
        )

    ##
    # @brief Converts a numeric string into int or float.
    #
    # @param value_string String to convert.
    # @return Numeric value or None if conversion fails.
    @staticmethod
    def _parse_numeric_value(value_string: str) -> Optional[Union[int, float]]:

        try:
            if '.' in value_string or 'e' in value_string.lower():
                return float(value_string)
            return int(value_string)
        except ValueError:
            return None
    ##
    # @brief Returns a copy of the configuration dictionary.
    #
    # @return Dictionary containing all configuration parameters.
    def get_dict(self) -> Dict[str, Any]:

        return self.config_dict.copy()

    ##
    # @brief Retrieves the value associated with a configuration key.
    #
    # @param key Name of the key.
    # @param default Default value if the key does not exist.
    # @return Value associated with the key or the default.
    def get(
        self,
        key: str,
        default: Any = None
    ) -> Any:

        return self.config_dict.get(key.upper(), default)

    ##
    # @brief Allows parameter access using index syntax.
    #
    # Example:
    # config["PARAMETER"]
    #
    # @param key Name of the key.
    # @return Value associated with the key.
    #
    # @exception KeyError Raised if the key does not exist.
    def __getitem__(self, key: str) -> Any:

        try:
            return self.config_dict[key.upper()]
        except KeyError as error:
            raise KeyError(
                f"Configuration key '{key}' not found. "
                f"Available keys: {list(self.config_dict.keys())}"
            ) from error

    ##
    # @brief Checks whether a key exists in the configuration.
    #
    # @param key Name of the key.
    # @return True if the key exists.
    def __contains__(self, key: str) -> bool:

        return key.upper() in self.config_dict

    ##
    # @brief Returns all configuration keys.
    def keys(self):

        return self.config_dict.keys()

    ##
    # @brief Returns all configuration values.
    def values(self):

        return self.config_dict.values()

    ##
    # @brief Returns all key-value pairs in the configuration.
    def items(self):
        """
        @brief Returns all key-value pairs in the configuration.
        """
        return self.config_dict.items()

    ##
    # @brief Returns a readable representation of the configuration.
    #
    # @return Formatted string containing all keys and values.
    def __str__(self) -> str:

        if not self.config_dict:
            return f"Empty configuration from '{self.filename}'"

        lines = [f"Configuration from '{self.filename}':"]
        for key, value in sorted(self.config_dict.items()):
            value_type = type(value).__name__
            lines.append(f"  {key}: {repr(value)} ({value_type})")

        return '\n'.join(lines)

    ##
    # @brief Technical representation of the object.
    def __repr__(self) -> str:

        return f"ConfigReader(filename='{self.filename}')"

##
# @brief Utility function to directly read a configuration file.
#
# @param filename Path of the configuration file.
# @return Dictionary containing the parsed parameters.
def read_from_file(filename: str) -> Dict[str, Any]:

    reader = ConfigReader(filename)
    return reader.get_dict()

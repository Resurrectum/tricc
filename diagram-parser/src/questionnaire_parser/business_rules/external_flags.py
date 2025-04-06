"""
Module for handling external flags and references in medical questionnaires.

This module provides classes and functions to load and manage external references
from configuration files, including flags and numeric functions.
"""

import json
from pathlib import Path
from typing import Optional, Set, Union


class ExternalReferences:
    """Manages external references for medical questionnaires.

    This class loads external flags and numeric function references from a JSON file,
    validates them, and provides access methods.
    """

    def __init__(self, config_path: Union[str, Path, None] = None):
        """Initialize the external references manager.

        Args:
            config_path: Path to the externals.json file. If None, looks for
                        a file named "externals.json" in the current directory.
        """
        self.numeric_refs: Set[str] = set()
        self.flag_refs: Set[str] = set()
        self.config_path = Path(config_path) if config_path else Path("externals.json")

        # Load the externals configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load the externals configuration from the JSON file."""
        try:
            if not self.config_path.exists():
                # Create empty sets if file doesn't exist
                return

            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Load numeric references
            numeric_refs = config.get("numeric", [])
            self.numeric_refs = set(numeric_refs)

            # Load flag references
            flag_refs = config.get("flags", [])
            self.flag_refs = set(flag_refs)

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading externals configuration: {e}")
            # Initialize with empty sets on error

    def is_valid_reference(self, reference_name: str) -> bool:
        """Check if a reference name is a valid external reference.

        Args:
            reference_name: The name of the reference to check

        Returns:
            True if the reference is valid, False otherwise
        """
        return reference_name in self.numeric_refs or reference_name in self.flag_refs

    def is_numeric_reference(self, reference_name: str) -> bool:
        """Check if a reference name is a valid numeric external reference.

        Args:
            reference_name: The name of the reference to check

        Returns:
            True if the reference is a numeric reference, False otherwise
        """
        return reference_name in self.numeric_refs

    def is_flag_reference(self, reference_name: str) -> bool:
        """Check if a reference name is a valid flag external reference.

        Args:
            reference_name: The name of the reference to check

        Returns:
            True if the reference is a flag reference, False otherwise
        """
        return reference_name in self.flag_refs

    def get_all_references(self) -> Set[str]:
        """Get all valid external references.

        Returns:
            Set of all valid external reference names
        """
        return self.numeric_refs.union(self.flag_refs)

    def get_numeric_references(self) -> Set[str]:
        """Get all valid numeric external references.

        Returns:
            Set of all valid numeric reference names
        """
        return self.numeric_refs

    def get_flag_references(self) -> Set[str]:
        """Get all valid flag external references.

        Returns:
            Set of all valid flag reference names
        """
        return self.flag_refs

    def save_config(self, path: Optional[Union[str, Path]] = None) -> None:
        """Save the current configuration to a JSON file.

        Args:
            path: Path to save the file. If None, uses the original config path.
        """
        save_path = Path(path) if path else self.config_path

        config = {"numeric": list(self.numeric_refs), "flags": list(self.flag_refs)}

        try:
            with open(save_path, "w") as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"Error saving externals configuration: {e}")

    def add_numeric_reference(self, reference_name: str) -> None:
        """Add a new numeric reference.

        Args:
            reference_name: Name of the numeric reference to add
        """
        self.numeric_refs.add(reference_name)

    def add_flag_reference(self, reference_name: str) -> None:
        """Add a new flag reference.

        Args:
            reference_name: Name of the flag reference to add
        """
        self.flag_refs.add(reference_name)

    def remove_reference(self, reference_name: str) -> bool:
        """Remove a reference if it exists.

        Args:
            reference_name: Name of the reference to remove

        Returns:
            True if the reference was removed, False if it wasn't found
        """
        if reference_name in self.numeric_refs:
            self.numeric_refs.remove(reference_name)
            return True
        elif reference_name in self.flag_refs:
            self.flag_refs.remove(reference_name)
            return True
        return False


# Create a default instance that loads from externals.json
external_refs = ExternalReferences()

# Example usage:
if __name__ == "__main__":
    # Print all loaded references
    print("Numeric references:", external_refs.get_numeric_references())
    print("Flag references:", external_refs.get_flag_references())

    # Check if a reference is valid
    reference_to_check = "malaria transmission area"
    if external_refs.is_valid_reference(reference_to_check):
        if external_refs.is_flag_reference(reference_to_check):
            print(f"'{reference_to_check}' is a valid flag reference")
        else:
            print(f"'{reference_to_check}' is a valid numeric reference")
    else:
        print(f"'{reference_to_check}' is not a valid external reference")

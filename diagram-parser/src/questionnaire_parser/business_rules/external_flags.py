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

        # If no config_path is provided, default to externals.json in the module's directory
        if config_path is None:
            self.config_path = Path(__file__).parent / "externals.json"
        else:
            self.config_path = Path(config_path)

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

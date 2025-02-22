"""
Validation system for diagram parsing and verification.

This module provides a flexible validation framework that supports different
validation levels and result collection. It can be used to:
- Collect validation issues during parsing
- Support different validation strictness levels
- Generate validation reports
- Handle validation logging

The validation system supports three severity levels:
- CRITICAL: Fatal issues that MUST be addressed
- ERROR: Serious issues that SHOULD be addressed
- WARNING: Minor issues that COULD be improved

And three validation modes. You should conceive your validators, so that:
- STRICT: Raises exceptions immediately for any ERROR or CRITICAL issue and interrupts
- NORMAL: Raises exceptions for CRITICAL issues, but only collects ERROR and WARNING issues
- LENIENT: Collects all issues without raising exceptions (for debugging purposes)
"""
from enum import Enum
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ValidationSeverity(Enum):
    """Defines the severity levels for validation issues."""
    CRITICAL = "CRITICAL"  # Fatal issues that prevent proper functioning
    ERROR = "ERROR"       # Serious issues that should be fixed
    WARNING = "WARNING"   # Minor issues or suggestions for improvement

class ValidationLevel(Enum):
    """Setting this in the parser will determine how strictly 
    validation issues should be handled."""
    STRICT = "STRICT"     # Will raise ERROR and CRITICAL exceptions immediately
    NORMAL = "NORMAL"     # Will raise on CRITICAL, but only collect the other severity levels
    LENIENT = "LENIENT"   # Collect all issues, never raise

class ValidationResult(BaseModel):
    """Represents a single validation issue. This defines how a validation issue will look like."""
    severity: ValidationSeverity
    message: str
    element_id: Optional[str] = None
    element_type: Optional[str] = None
    field_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic configuration."""
        frozen = True  # Make validation results immutable

class ValidationCollector:
    """Collects and manages validation results during parsing."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.NORMAL):
        """Initialize the validation collector.
        
        Args:
            validation_level: Determines how strictly to handle validation issues.
                            Defaults to NORMAL.
        """
        self.validation_level = validation_level
        self.results: List[ValidationResult] = []

    def add_result(self,
                  severity: ValidationSeverity,
                  message: str,
                  element_id: Optional[str] = None,
                  element_type: Optional[str] = None,
                  field_name: Optional[str] = None) -> None:
        """Add a validation result and handle it according to validation level.
        
        Args:
            severity: The severity level of the issue
            message: Description of the validation issue
            element_id: ID of the affected element (if applicable)
            element_type: Type of the affected element (if applicable)
            field_name: Name of the affected field (if applicable)
            
        Raises:
            ValueError: If validation level and severity require an exception
        """
        result = ValidationResult(
            severity=severity,
            message=message,
            element_id=element_id,
            element_type=element_type,
            field_name=field_name
        )
        self.results.append(result)

        self._log_result(result)
        self._handle_result(result)

    def add_pydantic_error(self, error, element_id: str):
        """Convert Pydantic validation errors to our format. 
        Pydantic's own, internal validations are checked prior to user defined ones. 
        This """
        for err in error.errors():
            self.add_result(
                severity=ValidationSeverity.ERROR,
                message=f"Field validation error: {err['msg']}",
                element_id=element_id,
                element_type='Edge',
                field_name='.'.join(str(loc) for loc in err['loc'])
            )

    def _log_result(self, result: ValidationResult) -> None:
        """Log the validation result appropriately.
        
        Args:
            result: The validation result to log
        """
        log_message = self._format_log_message(result)

        if result.severity == ValidationSeverity.CRITICAL:
            logger.error(log_message)
        elif result.severity == ValidationSeverity.ERROR:
            logger.error(log_message)
        else:
            logger.warning(log_message)

    def _handle_result(self, result: ValidationResult) -> None:
        """Handle the validation result based on validation level.
        
        Args:
            result: The validation result to handle
            
        Raises:
            ValueError: If validation level and severity require an exception
        """
        if self.validation_level == ValidationLevel.STRICT:
            if result.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
                raise ValueError(self._format_error_message(result))
        elif self.validation_level == ValidationLevel.NORMAL:
            if result.severity == ValidationSeverity.CRITICAL:
                raise ValueError(self._format_error_message(result))

    def save_report(self, output_path: Path) -> None:
        """Save validation results to a file.
        
        Args:
            output_path: Path where to save the validation report
        """
        output_path.parent.mkdir(exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            self._write_report_header(f)
            self._write_results_by_severity(f)
            self._write_report_summary(f)

    def _write_report_header(self, file) -> None:
        """Write the header section of the validation report.
        
        Args:
            file: File object to write to
        """
        file.write("Diagram Validation Report\n")
        file.write("=" * 50 + "\n")
        file.write(f"Validation Level: {self.validation_level.value}\n")
        file.write(f"Total Issues: {len(self.results)}\n")
        file.write("-" * 50 + "\n\n")

    def _write_results_by_severity(self, file) -> None:
        """Write validation results grouped by severity.
        
        Args:
            file: File object to write to
        """
        for severity in ValidationSeverity:
            results = [r for r in self.results if r.severity == severity]
            if results:
                file.write(f"\n{severity.value} Issues ({len(results)}):\n")
                file.write("-" * 30 + "\n")

                for result in results:
                    file.write(f"- {result.message}\n")
                    if result.element_id:
                        file.write(f"  Element ID: {result.element_id}\n")
                    if result.element_type:
                        file.write(f"  Element Type: {result.element_type}\n")
                    if result.field_name:
                        file.write(f"  Field: {result.field_name}\n")
                    file.write(f"  Time: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    file.write("\n")

    def _write_report_summary(self, file) -> None:
        """Write the summary section of the validation report.
        
        Args:
            file: File object to write to
        """
        file.write("\nSummary:\n")
        file.write("-" * 30 + "\n")
        for severity in ValidationSeverity:
            count = len([r for r in self.results if r.severity == severity])
            file.write(f"{severity.value}: {count} issues\n")

        if self.has_critical_issues:
            file.write("\nWARNING: Critical issues were found!\n")



    @staticmethod
    def _format_log_message(result: ValidationResult) -> str:
        """Format a validation result for logging.
        
        Args:
            result: The validation result to format
            
        Returns:
            Formatted message string
        """
        message = f"{result.severity.value}: {result.message}"
        if result.element_id:
            message += f" (Element ID: {result.element_id})"
        if result.element_type:
            message += f" (Type: {result.element_type})"
        return message

    @staticmethod
    def _format_error_message(result: ValidationResult) -> str:
        """Format a validation result for error raising.
        
        Args:
            result: The validation result to format
            
        Returns:
            Formatted error message
        """
        return f"{result.severity.value}: {result.message}"

    def get_results_by_severity(self, severity: ValidationSeverity) -> List[ValidationResult]:
        """Get all validation results of a specific severity.
        
        Args:
            severity: The severity level to filter by
            
        Returns:
            List of validation results with the specified severity
        """
        return [r for r in self.results if r.severity == severity]

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues.
        
        Returns:
            True if there are any CRITICAL issues, False otherwise
        """
        return any(r.severity == ValidationSeverity.CRITICAL for r in self.results)

"""
Data Preprocessing Script Library — Custom Exceptions & Warnings
=================================================================
All errors and warnings raised by generate_preprocessor().
"""


class TemplateNotFoundError(FileNotFoundError):
    """
    Raised when the requested template file does not exist in templates_dir.

    Example
    -------
    generate_preprocessor("file_union", ...)
    → looks for templates/file_union_template.py
    → raises TemplateNotFoundError if that file is missing
    """


class MissingParameterError(KeyError):
    """
    Raised when a {{PLACEHOLDER}} found in the template has no matching
    key in the *parameters* dict supplied to generate_preprocessor().

    Example
    -------
    Template contains {{JOIN_KEY}} but parameters dict has no 'JOIN_KEY' entry.
    """


class OutputWriteError(OSError):
    """
    Raised when the generated script cannot be written to output_dir
    (e.g. directory does not exist and cannot be created, permission denied).
    """


class ExtraParameterWarning(UserWarning):
    """
    Issued (not raised) when the *parameters* dict contains keys that have
    no matching {{PLACEHOLDER}} in the template.  The extra keys are ignored
    and generation continues normally.

    Example
    -------
    parameters contains 'OUTPUT_ENCODING' but the template has no
    {{OUTPUT_ENCODING}} token → ExtraParameterWarning is issued.
    """

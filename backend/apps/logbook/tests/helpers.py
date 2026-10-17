def error_details(response) -> dict:
    """Field-level error details of STAR's standard error envelope."""
    return response.data.get("error", {}).get("details", {})

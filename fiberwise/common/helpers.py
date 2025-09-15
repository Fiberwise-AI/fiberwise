def validate_input(input_data):
    """Helper function to validate input data"""
    return isinstance(input_data, str) and len(input_data) > 0

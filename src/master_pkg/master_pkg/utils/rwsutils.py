import ast


def string_to_list(input_string):
    """
    Converts a string representation to a List.
    example format '[TRUE,[[0,0,0],[1,0,0,0]],[0.001,[0,0,0.001],[1,0,0,0],0,0,0]]'.
    """
    # Replace ABB-style booleans with Python booleans
    input_string = input_string.replace('TRUE', 'True').replace('FALSE', 'False')
    #print(string)
    try:
        return ast.literal_eval(input_string)
    except Exception as e:
        #print(f"Error: {e}")
        raise ValueError(f"Invalid tool string: {input_string}") from e
    
def list_to_string(input_list):
    """
    Converts a List representation to a string.
    The List should be in the format [True, [[0, 0, 0], [1, 0, 0, 0]], [0.001, [0, 0, 0.001], [1, 0, 0, 0], 0, 0, 0]].
    """
    try:
        # Convert the list to a string representation
        str_input = str(input_list)
        # Replace Python booleans with ABB-style booleans
        return str_input.replace('True', 'TRUE').replace('False', 'FALSE')
    except Exception as e:
        #print(f"Error: {e}")
        raise ValueError(f"Invalid list input: {input_list}") from e
    

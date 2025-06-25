def clamp(start: int, end: int, start_bound: int, end_bound: int) -> tuple[int, int]:
    """
    This function reduces the interval span [start, end] in order to make it
    stay inside the greater one defined by [start_bound, end_bound].
    If the interval is completely outside then a dummy interval [None, None] is
    returned.
    """

    if start > end_bound or end < start_bound:
        return (None, None)
    
    if start < start_bound:
        start = start_bound

    if end > end_bound:
        end = end_bound

    return (start, end)
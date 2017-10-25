
def check_lingvodoc_id(ids):
    if ids is None or\
            type(ids) is not list or\
            len(ids) != 2 or\
            type(ids[0]) is not int or\
            type(ids[1]) is not int:
        return False
    return True
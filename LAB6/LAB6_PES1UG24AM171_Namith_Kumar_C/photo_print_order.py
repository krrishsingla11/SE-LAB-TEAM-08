INCLUDED_PRINTS = {"4x6": 20, "5x7": 15, "8x10": 10}


def extra_print_charge(print_size, copies, finish, is_member):
    if print_size not in INCLUDED_PRINTS:
        raise ValueError("unknown print size")
    if copies < 0:
        raise ValueError("invalid copies")
    included = INCLUDED_PRINTS[print_size]
    if is_member and print_size != "8x10":
        included += 5
    extra = copies - included
    if extra <= 0:
        return 0
    if finish == "matte":
        rate = 4
    else:
        rate = 7
    if extra > 50:
        rate = rate + 2
        if finish == "canvas":
            rate += 5
    return extra * rate


def order_valid(file_mb, copies, is_rush):
    if is_rush:
        return copies <= 50
    if file_mb > 25:
        return False
    return copies <= 500


def dispatch_status(hours_before_dispatch, is_framed, is_international):
    if is_framed:
        cutoff = 24
    else:
        cutoff = 12
    if is_international:
        cutoff += 24
    if hours_before_dispatch >= cutoff:
        return "on_time"
    elif hours_before_dispatch >= cutoff - 6:
        return "tight"
    return "missed"

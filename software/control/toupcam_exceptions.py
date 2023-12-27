def signed_to_unsigned(n, num_bits):
    """
    Helper function to do 2s complement conversion on returned error codes.
    Returns function as a string representation in hexadecimal form.
    """
    return hex(n & ((1 << num_bits) -1))

hresult_error_lookup = {
        'E_ACCESSDENIED':"0x80070005",
        'E_INVALIDARG':"0x80070057",
        'E_NOTIMPL':"0x80004001",
        'E_POINTER':"0x80004003",
        'E_UNEXPECTED':"0x8000ffff",
        'E_WRONG_THREAD':"0x8001010e",
        'E_GEN_FAILURE':"0x8007001f",
        'E_BUSY':"0x800700aa",
        'E_PENDING':"0x8000000a",
        'E_TIMEOUT':"0x8001011f",
        'E_FAIL':"0x80004005"
        }

def hresult_checker(exception, *error_names):
    """
    Gets the hresult_checker's actual type,
    raises it again if unmatchable. Can
    supply it with multiple error name
    strings (see hresult_error_lookup)
    to return only if one of these is
    matched and raise otherwise.

    :return: String containing which
    error type it was, if a valid
    error.
    :raise: HRESULTException if unmatchable
    """
    try:
        exception.hr
    except AttributeError:
        raise exception
    for k in hresult_error_lookup.keys():
        if hresult_error_lookup[k].lower() == signed_to_unsigned(exception.hr, 32).lower():
            if len(error_names) > 0:
                if k in error_names:
                    return k
            else:
                return k
    raise exception

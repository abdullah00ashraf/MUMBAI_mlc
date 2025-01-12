import ctypes
import gc
import os
from typing import Union

# System-level memory pinning configuration
if os.name == 'nt':
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    # CRITICAL: Define 64-bit argument and return types to prevent OverflowError
    # VirtualLock(LPVOID lpAddress, SIZE_T dwSize)
    kernel32.VirtualLock.argtypes = [wintypes.LPVOID, ctypes.c_size_t]
    kernel32.VirtualLock.restype = wintypes.BOOL
    
    # VirtualUnlock(LPVOID lpAddress, SIZE_T dwSize)
    kernel32.VirtualUnlock.argtypes = [wintypes.LPVOID, ctypes.c_size_t]
    kernel32.VirtualUnlock.restype = wintypes.BOOL
else:
    try:
        _libc = ctypes.CDLL("libc.so.6")
    except OSError:
        _libc = ctypes.CDLL(None)

def secure_zero(data: Union[bytearray, memoryview]):
    """
    Overwrites the memory of a mutable buffer with zeros to prevent sensitive data 
    leakage via memory dumps or cold-boot attacks.
    """
    if isinstance(data, (bytearray, memoryview)):
        length = len(data)
        if length > 0:
            # Cast the buffer to a C-compatible char array and memset to 0
            address = (ctypes.c_char * length).from_buffer(data)
            ctypes.memset(address, 0, length)
    force_garbage_collection()

def mlock(data: Union[bytearray, memoryview]):
    """
    Pins a memory range to physical RAM, preventing the OS from swapping it 
    to the pagefile/disk. Crucial for DEK (Data Encryption Key) protection.
    """
    length = len(data)
    if length == 0: return
    
    # Get the raw memory address from the buffer
    address = ctypes.addressof(ctypes.c_char.from_buffer(data))
    
    if os.name == 'nt':
        if not kernel32.VirtualLock(address, length):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        if _libc.mlock(ctypes.c_void_p(address), ctypes.c_size_t(length)) != 0:
            raise OSError("OS mlock failure")

def munlock(data: Union[bytearray, memoryview]):
    """
    Releases the memory pin, allowing the OS to manage the RAM normally (paging/swapping).
    """
    length = len(data)
    if length == 0: return
    
    address = ctypes.addressof(ctypes.c_char.from_buffer(data))
    
    if os.name == 'nt':
        if not kernel32.VirtualUnlock(address, length):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        if _libc.munlock(ctypes.c_void_p(address), ctypes.c_size_t(length)) != 0:
            raise OSError("OS munlock failure")

def force_garbage_collection():
    """
    Triggers an immediate collection of all Python garbage generations to ensure 
    unreferenced sensitive objects are cleared from the heap quickly.
    """
    gc.collect()

class SensitiveBuffer:
    """
    A context manager for sensitive cryptographic data.
    Automatically pins memory upon entry and zeros/unlocks it upon exit.
    
    Usage:
        with SensitiveBuffer(32) as key_buffer:
            # ... perform decryption ...
    """
    def __init__(self, size: int):
        self.buffer = bytearray(size)

    def __enter__(self):
        mlock(self.buffer)
        return self.buffer

    def __exit__(self, exc_type, exc_val, exc_tb):
        secure_zero(self.buffer)
        munlock(self.buffer)
        force_garbage_collection()
"""Defines data that is passed between processing objects"""
from enum import IntEnum


class MessageType(IntEnum):
    """Defines the type of message that is being passed into a multiprocessing queue"""
    RawData = 0
    """Raw UDP packets"""
    PixelData = 1
    """Decoded Pixel/Trigger Data"""
    TriggerData = 8
    """Decoded Triggers"""
    EventData = 2
    """Event Data"""
    CentroidData = 3
    """Centroided Data"""
    OpenFileCommand = 4
    """Open File message"""
    CloseFileCommand = 5
    """Close File Message"""




    
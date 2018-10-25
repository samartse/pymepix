import multiprocessing

from multiprocessing.sharedctypes import RawArray 
import numpy as np
import socket
import time,os
from multiprocessing import Queue
class FileStorage(multiprocessing.Process):

    def __init__(self,data_queue,file_status):
        multiprocessing.Process.__init__(self)
        self._input_queue = data_queue
        self._file_io = None
        self._raw_file_io = None
    def run(self):

        while True:
            try:
                # get a new message
                packet = self._input_queue.get()
                # this is the 'TERM' signal
                if packet is None:
                    break

                message = packet[0]
                # print(packet)
                #Check signal type
                if message == 'OPEN':
                    path = packet[1]
                    prefix = packet[2]
                    tof_filename = os.path.join(path,prefix)+time.strftime("%Y%m%d-%H%M%S")+'.dat'
                    raw_filename = os.path.join(path,'raw_'+prefix)+time.strftime("%Y%m%d-%H%M%S")+'.dat'
                    print('Opening filenames ',tof_filename,raw_filename)
                    if self._file_io is not None:
                        self._file_io.close()
                        self._raw_file_io.close()
                    
                    self._file_io = open(tof_filename,'wb')
                    self._raw_file_io = open(raw_filename,'wb')
                elif message == 'WRITE':
                    data = packet[1]
                    #print(packet)
                    if self._raw_file_io is not None:
                        self._raw_file_io.write(data)
                elif message == 'WRITETOF':
                    counter,x,y,tof,tot = packet[1]
                    
                    #print(packet)
                    if self._file_io is not None:
                        np.save(self._file_io,counter)  
                        np.save(self._file_io,x) 
                        np.save(self._file_io,y) 
                        np.save(self._file_io,tof) 
                        np.save(self._file_io,tot)                   
                elif message == 'CLOSE':
                    if self._file_io is not None:
                        self._file_io.close()
                        self._raw_file_io.close()
                        self._file_io = None
                        self._raw_file_io = None
            except Exception as e:
                print(str(e))
            
        

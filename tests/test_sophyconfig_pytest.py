import os
import socketserver
import threading
import shutil
import pathlib
import os
import numpy as np

from pymepix.pymepix_connection import PymepixConnection
from pymepix.config.sophyconfig import SophyConfig
from pymepix.SPIDR.spidrcmds import SpidrCmds
from pymepix.timepixdef import DacRegisterCodes
from pymepix.util.spidrDummyTCP import TPX3Handler

path = pathlib.Path(__file__).parent

CONFIG_PATH = path / "test_assets/test_config_W0028_H06_50V.spx"
ADDRESS = ("192.168.1.10", 50000)


def parameter_exact(code, value):
    """Test for precisely correct interpreted parameters of a known .spx file"""
    if code == DacRegisterCodes.Ibias_Preamp_ON:
        assert value == 128
    elif code == DacRegisterCodes.Ibias_Preamp_OFF:
        assert value == 8
    elif code == DacRegisterCodes.VPreamp_NCAS:
        assert value == 128
    elif code == DacRegisterCodes.Ibias_Ikrum:
        assert value == 20
    elif code == DacRegisterCodes.Vfbk:
        assert value == 128
    elif code == DacRegisterCodes.Vthreshold_fine:
        assert value == 150
    elif code == DacRegisterCodes.Vthreshold_coarse:
        assert value == 6
    elif code == DacRegisterCodes.Ibias_DiscS1_ON:
        assert value == 128
    elif code == DacRegisterCodes.Ibias_DiscS1_OFF:
        assert value == 8
    elif code == DacRegisterCodes.Ibias_DiscS2_ON:
        assert value == 128
    elif code == DacRegisterCodes.Ibias_DiscS2_OFF:
        assert value == 8
    elif code == DacRegisterCodes.Ibias_PixelDAC:
        assert value == 150
    elif code == DacRegisterCodes.Ibias_TPbufferIn:
        assert value == 128
    elif code == DacRegisterCodes.Ibias_TPbufferOut:
        assert value == 128
    elif code == DacRegisterCodes.VTP_coarse:
        assert value == 128
    elif code == DacRegisterCodes.VTP_fine:
        assert value == 256
    elif code == DacRegisterCodes.Ibias_CP_PLL:
        assert value == 128
    elif code == DacRegisterCodes.PLL_Vcntrl:
        assert value == 128


def parameter_range_of_values(code, value):
    """Test for DAC parameters being in their respective range of values"""
    if code in [1, 3, 4, 5, 8, 10, 12, 13, 14, 15, 17]:
        assert 0 <= value <= 255
    elif code in [2, 7, 9, 11]:
        assert 0 <= value <= 15
    elif code in [6, 16]:
        assert 0 <= value <= 511
    elif code == 18:
        assert (
            True
        )  # TODO: @firode waiting for answer with information about PLL_VCNTRL


def test_read_config():
    spx = SophyConfig(CONFIG_PATH)
    conf_params = spx.dacCodes()
    for code, value in conf_params:
        parameter_range_of_values(code, value)
        parameter_exact(code, value)


def test_pixelmask():
    """Check whether the pixelmask is in an appropriate format"""
    spx = SophyConfig(CONFIG_PATH)
    mask = spx.maskPixels
    test = spx.testPixels()
    thresh = spx.thresholdPixels()

    # check for correct range of values
    assert mask.min() >= 0 and mask.max() <= 1
    assert test.min() >= 0 and test.max() <= 256
    assert thresh.min() >= 0 and thresh.max() <= 15

    # there should be more open pixels than masked ones
    assert np.count_nonzero(mask == 0) > np.count_nonzero(mask == 1)

def test_save_pixelmask():
    tmp_filename = CONFIG_PATH.with_suffix('.tmp')
    shutil.copyfile(CONFIG_PATH, tmp_filename)
    spx = SophyConfig(tmp_filename)
    mask = spx.maskPixels

    mask[0, 0] = 1
    spx.maskPixels = mask

    spx.saveMask()

    new_spx = SophyConfig(tmp_filename)
    new_mask = new_spx.maskPixels
    os.remove(tmp_filename)

    assert np.array_equal(mask, new_mask)

class TestTPX3Handler(TPX3Handler):
    """The handler class for a socketserver to capture and evaluate the config packets from pymepix

        This class uses the main functionality of the spidrDummyTCP to collect config packets.
        Furthermore it takes some of those packets and has another look on them containing the correct values.
        """

    def __init__(self, request, client_address, server, event=None):
        self.shutdown_event = event
        TPX3Handler.__init__(self, request, client_address, server)

    def handle(self):
        """The handle loop is the main function of the request handler.

        Pymepix only connects to the camera once and then sends packets without opening a new request.
        That is why there needs to be a loop in the handle function to capture all the packets from just one request.
        To end the loop a threading event was created to communicate with the handler from the outside
        and tell it when to stop."""
        while not self.shutdown_event.is_set():

            self.actual_data = False
            self._gather_packet()
            self._process_data()

            if self.cmd == SpidrCmds.CMD_SET_PIXCONF:
                assert len(self.data) in [53, 149]
                # marks the next row
                assert 0 <= self.data[4] <= 255

            elif self.cmd == SpidrCmds.CMD_SET_DAC:
                assert len(self.data) == 5

                cmd_load = self.data[4]
                dac_cmd = cmd_load >> 16
                value = cmd_load & 0xFFFF
                parameter_range_of_values(dac_cmd, value)
                # Pymepix first sends hardcoded default parameters and afterwards
                if self.actual_data:
                    parameter_exact(dac_cmd, value)
                if dac_cmd == DacRegisterCodes.PLL_Vcntrl:
                    self.actual_data = True


class CustomTCPServer(socketserver.TCPServer):
    """The custom socketserver to communicate with Pymepix

    This socketserver overrides two functions of the TCPServer to hand the threading event, that is
    responsible for ending the connection, to the custom request handler class.
    Usually you would stop a socketserver by calling the shutdown() function. As the request never gets closed though
    this is not possible in this case. The socketserver will wait for the request handler to finish and
    thus can not compute the shutdown() function call. That is why we need a thread event to communicate with
    the request handler from the outside. For more fundamental insights look up the python socketserver docs."""

    def __init__(
        self, server_address, RequestHandlerClass, bind_and_activate=True, event=None
    ):
        self.shutdown_event = event
        socketserver.TCPServer.__init__(
            self,
            server_address,
            RequestHandlerClass,
            bind_and_activate=bind_and_activate,
        )

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(
            request, client_address, self, event=self.shutdown_event
        )


def test_send_config():
    """Pretend to be a TPX3 and capture config packets.
    Check for correct format and values.
    """
    shutdown_event = threading.Event()
    server = CustomTCPServer(ADDRESS, TestTPX3Handler, event=shutdown_event)
    server.timeout = 5
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.daemon = True
    server_thread.start()
    ip, port = server.server_address

    tpx = PymepixConnection((ip, port))
    tpx[0].loadConfig(CONFIG_PATH)

    shutdown_event.set()
    server.server_close()


if __name__ == "__main__":
    #test_read_config()
    #test_pixelmask()
    #test_send_config()
    test_save_pixelmask()

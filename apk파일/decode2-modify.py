from __future__ import print_function

import sys
import wave

from io import StringIO

import alsaaudio
import colorama
import numpy as np

from reedsolo import RSCodec, ReedSolomonError
from termcolor import cprint
from pyfiglet import figlet_format

HANDSHAKE_START_HZ = 4096
HANDSHAKE_END_HZ = 5120 + 512

START_HZ = 1024
STEP_HZ = 16
BITS = 8

FEC_BYTES = 4

def dominant(frame_rate, chunk):
    w = np.fft.fft(chunk)
    freqs = np.fft.fftfreq(len(chunk))
    peak_coeff = np.argmax(np.abs(w))
    peak_freq = freqs[peak_coeff]
    return abs(peak_freq * frame_rate)  # in Hz


def match(freq1, freq2):
    return abs(freq1 - freq2) < 10


def decode_bitchunks(chunk_bits, chunks):
    out_bytes = []
    next_read_chunk = 0
    byte = 0
    bits_left = 8

    while next_read_chunk < len(chunks):
        byte <<= 2
        byte += (chunks[next_read_chunk]&(-1<<4))
        bits_left -= 2
        next_read_chunk += 1
        if bits_left <= 0:
            byte >>= 4
            out_bytes.append(byte)
            byte = 0
            bits_left = 8

    return out_bytes

def extract_packet(freqs):
    freqs = freqs[::2]
    bit_chunks = [int(round((f - START_HZ) / STEP_HZ)) for f in freqs]
    bit_chunks = [c for c in bit_chunks[1:] if 0 <= c < (2 ** BITS)]
    return bytearray(decode_bitchunks(BITS, bit_chunks))


def display(s):
    cprint(figlet_format(s.replace(' ', '   '), font='doom'), 'yellow')


def listen_linux(frame_rate=44100, interval=0.1):
    mic = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, alsaaudio.PCM_NORMAL, device="default")
    mic.setchannels(1)
    mic.setrate(44100)
    mic.setformat(alsaaudio.PCM_FORMAT_S16_LE)

    num_frames = int(round((interval / 2) * frame_rate))
    mic.setperiodsize(num_frames)
    print("start...")

    in_packet = False
    packet = []

    while True:
        l, data = mic.read()
        if not l:
            continue

        chunk = np.fromstring(data, dtype=np.int16)
        dom = dominant(frame_rate, chunk)

        if in_packet and match(dom, HANDSHAKE_END_HZ):
            byte_stream = extract_packet(packet)
            try:
                byte_stream = RSCodec(FEC_BYTES).decode(byte_stream)
                byte_stream = byte_stream.decode("utf-8")

                display(byte_stream)
            except ReedSolomonError as e:
                pass
                # print("{}: {}".format(e, byte_stream))

            packet = []
            in_packet = False
        elif in_packet:
            packet.append(dom)
        elif match(dom, HANDSHAKE_START_HZ):
            in_packet = True

if __name__ == '__main__':
    colorama.init(strip=not sys.stdout.isatty())

    # decode_file(sys.argv[1], float(sys.argv[2]))
    listen_linux()

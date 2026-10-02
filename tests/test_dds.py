import importlib.util
import io
from pathlib import Path
import struct

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('dds_writer', root/'utils/dds.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
count=0
for width,height in ((1,1),(8,4),(4,8),(256,256)):
    rgba=np.zeros((height,width,4),dtype=np.float32)
    rgba[:]=(.25,.5,.75,.75)
    if height>1:
        rgba[-1,:]=(1,0,0,1)
    stream=io.BytesIO()
    module.write_dds(stream,rgba)
    raw=stream.getvalue()
    levels=max(width,height).bit_length()
    header=struct.unpack('<31I',raw[4:128])
    assert header[2:4]==(height,width) and header[6]==levels
    assert len(raw)==128+sum(max(1,width>>n)*max(1,height>>n)*4 for n in range(levels))
    image=Image.open(io.BytesIO(raw))
    assert image.size==(width,height)
    expected=(255,0,0,255) if height>1 else (137,188,225,191)
    assert image.getpixel((0,0))==expected,(image.getpixel((0,0)),expected)
    count+=1
for bad in (np.zeros((4,4)),np.zeros((3,4,4)),np.full((4,4,4),np.nan),np.full((4,4,4),np.inf)):
    try:
        module.write_dds(io.BytesIO(),bad)
    except ValueError:
        count+=1
    else:
        raise AssertionError('Invalid DDS input accepted')
# Gamma-correct, premultiplied-alpha filtering avoids dark fringes.
rgba=np.array([[[1,0,0,1],[0,0,1,0]]],dtype=np.float32)
stream=io.BytesIO()
module.write_dds(stream,rgba)
assert stream.getvalue()[-4:]==bytes([0,0,255,128])
count+=1
print(f'PASS {count} independent DDS checks: Pillow decoding, orientation, sizes, mip filtering, invalid inputs')

normal=np.zeros((2,2,4),dtype=np.float32)
normal[:]=(.5,.5,1,1)
stream=io.BytesIO()
module.write_dds(stream,normal,normal_map=True)
assert Image.open(io.BytesIO(stream.getvalue())).getpixel((0,0))==(128,128,255,255)
normal[0,:]=(.8,.5,.9,1)
normal[1,:]=(.5,.8,.9,1)
stream=io.BytesIO()
module.write_dds(stream,normal,normal_map=True)
encoded=np.frombuffer(stream.getvalue()[-4:],dtype=np.uint8)[[2,1,0]]/255*2-1
expected=np.array([.3,.3,.8]); expected/=np.linalg.norm(expected)
assert np.max(np.abs(encoded-expected))<.008,(encoded,expected)
print('PASS linear normal encoding and renormalized vector mipmaps')

import time

def decode_mips(raw):
    header = list(struct.unpack('<31I', raw[4:128]))
    assert header[1] == 0xA1007 and header[18:26] == [32, 4, struct.unpack('<I', b'DXT5')[0], 0, 0, 0, 0, 0]
    width, height, count = header[3], header[2], header[6]
    assert header[4] == ((width+3)//4)*((height+3)//4)*16
    offset = 128
    decoded = []
    for level in range(count):
        w, h = max(1,width>>level), max(1,height>>level)
        length = ((w+3)//4)*((h+3)//4)*16
        subheader = header.copy()
        subheader[2], subheader[3], subheader[4], subheader[6], subheader[26] = h, w, length, 1, 0x1000
        payload = b'DDS '+struct.pack('<31I', *subheader)+raw[offset:offset+length]
        image = Image.open(io.BytesIO(payload))
        assert image.size == (w,h)
        decoded.append(np.array(image))
        offset += length
    assert offset == len(raw)
    return decoded

for width,height in ((1,1),(2,1),(1,2),(2,2),(8,4),(4,8),(64,64)):
    rgba=np.zeros((height,width,4),dtype=np.float32)
    rgba[:]=(.25,.5,.75,.75)
    if height>=8: rgba[-4:]=(1,0,0,1)
    stream=io.BytesIO(); module.write_dds(stream,rgba,pixel_format='DXT5')
    mips=decode_mips(stream.getvalue())
    expected=(255,0,0,255) if height>=8 else (137,188,225,191)
    assert max(abs(mips[0][0,0].astype(int)-expected))<=5, (width,height,mips[0][0,0])
    assert len(mips)==max(width,height).bit_length()
print('PASS BC3 independent Pillow decode: dimensions, header, orientation, gamma, small/rectangular mip blocks')

# Every index position, endpoints and alpha mode: decoder is independent of encoder.
rgba=np.zeros((4,4,4),dtype=np.float32)
rgba[:,:,:3]=np.linspace(0,1,16).reshape(4,4,1)
rgba[:,:,3]=np.array([0,1,.2,.3,.4,.5,.6,.7,.8,.9,1,0,.25,.5,.75,1]).reshape(4,4)
stream=io.BytesIO(); module.write_dds(stream,rgba,normal_map=True,pixel_format='DXT5')
decoded=decode_mips(stream.getvalue())[0][::-1]/255
assert np.max(abs(decoded[...,3]-rgba[...,3]))<.072
assert np.mean((decoded[...,:3]-rgba[...,:3])**2)<.012
for value in (0,1):
    rgba[:]=(.5,.5,1,value)
    stream=io.BytesIO(); module.write_dds(stream,rgba,normal_map=True,pixel_format='DXT5')
    mips=decode_mips(stream.getvalue())
    assert np.all(mips[0][...,3]==value*255)
    assert all(np.all(mip[...,3]==255) for mip in mips[1:])
    assert all(np.all(mip[...,:3]==[128,128,255]) for mip in mips)
print('PASS BC3 color/alpha indices, continuous alpha, exact transparent/opaque alpha and flat normal mips')

# Nontrivial RGB gradient, including blocks crossing the encoder chunk boundary.
y,x=np.mgrid[:256,:512].astype(np.float32)
rgba=np.stack((x/511,y/255,(x/511+y/255)/2, (x%64)/63),axis=2)
stream=io.BytesIO(); module.write_dds(stream,rgba,normal_map=True,pixel_format='DXT5')
decoded=decode_mips(stream.getvalue())[0][::-1]/255
assert np.sqrt(np.mean((decoded[...,:3]-rgba[...,:3])**2))*255<3
assert np.sqrt(np.mean((decoded[...,3]-rgba[...,3])**2))*255<3
print('PASS smooth RGB/alpha gradient fidelity across chunk boundaries')

# Filter transparent borders in linear light before compression.
rgba=np.array([[[1,0,0,1],[0,0,1,0]]],dtype=np.float32)
stream=io.BytesIO(); module.write_dds(stream,rgba,pixel_format='DXT5')
last=decode_mips(stream.getvalue())[-1][0,0]
assert np.max(abs(last.astype(int)-[255,0,0,128]))<=1, last
try: module.write_dds(io.BytesIO(),rgba,pixel_format='DXT1')
except ValueError: pass
else: raise AssertionError('Unknown compression accepted')
print('PASS BC3 alpha-aware mip filtering and format validation')

rgba=np.zeros((2048,2048,4),dtype=np.float32); rgba[:]=(.5,.5,1,1)
start=time.perf_counter(); stream=io.BytesIO()
module.write_dds(stream,rgba,normal_map=True,pixel_format='DXT5')
assert len(stream.getvalue())==5592560
print(f'PASS 2048 BC3 complete mip chain: {len(stream.getvalue())} bytes, {time.perf_counter()-start:.2f}s')

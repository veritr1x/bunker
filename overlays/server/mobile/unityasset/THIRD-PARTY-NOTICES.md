# Third-party notices

`audio.go` follows [python-fsb5](https://github.com/HearthSim/python-fsb5) (MIT License,
Copyright (c) Simon Pinfold) to rebuild FSB5 Vorbis as Ogg. `vorbis_setups.go` holds three
Vorbis setup headers generated with [libvorbis](https://xiph.org/vorbis/) 1.3.7
(BSD-3-Clause, Copyright (c) 2002-2020 Xiph.org Foundation) for the encoder settings the game
used; each matches the CRC32 its FSB5 data records.

`astc.go` is a Go port of the ASTC decoder in [texture2ddecoder](https://github.com/K0lb3/texture2ddecoder) (`src/Texture2DDecoder/astc.cpp`, version 1.0.6), used under the MIT License:

```
MIT License

Copyright (c) 2020 K0lb3

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

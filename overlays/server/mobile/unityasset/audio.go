package unityasset

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"path"
	"path/filepath"
	"strings"
)

// FMOD's FSB5 container, as Unity stores AudioClips, rebuilt as Ogg Vorbis.
//
// FSB5 keeps each Vorbis packet with a 16-bit length but drops the three
// header packets. The identification header is rebuilt from the sample's
// channels and rate; the setup header is the one libvorbis produces for the
// settings whose CRC32 FSB5 keeps (vorbis_setups.go). This follows
// python-fsb5 (MIT License, Simon Pinfold).

type fsbSample struct {
	frequency, channels int
	crc32               uint32
	data                []byte
}

var fsbFrequencies = map[int]int{1: 8000, 2: 11000, 3: 11025, 4: 16000, 5: 22050, 6: 24000, 7: 32000, 8: 44100, 9: 48000}

func parseFSB5(data []byte) ([]fsbSample, error) {
	if len(data) < 60 || string(data[:4]) != "FSB5" {
		return nil, errors.New("not an FSB5 sound bank")
	}
	le := binary.LittleEndian
	version := le.Uint32(data[4:])
	count := int(le.Uint32(data[8:]))
	headersSize, namesSize, dataSize := int(le.Uint32(data[12:])), int(le.Uint32(data[16:])), int(le.Uint32(data[20:]))
	if mode := le.Uint32(data[24:]); mode != 15 {
		return nil, fmt.Errorf("FSB5 sound format %d is not Vorbis", mode)
	}
	headerSize := 60
	if version == 0 {
		headerSize = 64
	}
	r := &reader{b: data, p: headerSize, order: le}
	type entry struct {
		fsbSample
		offset int
	}
	entries := make([]entry, count)
	for i := range entries {
		raw := r.u64()
		next := raw&1 != 0
		freq := int(raw >> 1 & 0xf)
		e := entry{offset: int(raw>>6&(1<<28-1)) * 16}
		e.channels = int(raw>>5&1) + 1
		e.frequency = fsbFrequencies[freq]
		for next && r.err == nil {
			chunk := r.u32()
			next = chunk&1 != 0
			size := int(chunk >> 1 & (1<<24 - 1))
			kind := chunk >> 25
			body := r.bytes(size)
			switch {
			case kind == 11 && len(body) >= 4: // VORBISDATA
				e.crc32 = le.Uint32(body)
			case kind == 2 && len(body) >= 4: // FREQUENCY
				e.frequency = int(le.Uint32(body))
			case kind == 1 && len(body) >= 1: // CHANNELS
				e.channels = int(body[0])
			}
		}
		entries[i] = e
	}
	if r.err != nil {
		return nil, r.err
	}
	start := headerSize + headersSize + namesSize
	if start+dataSize > len(data) {
		return nil, errors.New("FSB5 data is cut short")
	}
	out := make([]fsbSample, count)
	for i, e := range entries {
		end := dataSize
		if i+1 < count {
			end = entries[i+1].offset
		}
		if e.offset > end || end > dataSize {
			return nil, errors.New("FSB5 sample lies outside the data")
		}
		e.data = data[start+e.offset : start+end]
		out[i] = e.fsbSample
	}
	return out, nil
}

// ---- Vorbis setup header: only the modes matter here (each packet's block size) ----

type bitReader struct {
	b   []byte
	pos int // in bits
	err error
}

func (r *bitReader) read(n int) uint32 {
	var v uint32
	for i := 0; i < n; i++ {
		byteIndex := r.pos >> 3
		if byteIndex >= len(r.b) {
			r.err = errors.New("setup header is cut short")
			return 0
		}
		if r.b[byteIndex]>>(r.pos&7)&1 != 0 {
			v |= 1 << i
		}
		r.pos++
	}
	return v
}

func ilog(v uint32) int {
	n := 0
	for v > 0 {
		n++
		v >>= 1
	}
	return n
}

func lookup1Values(entries, dims int) int {
	r := 0
	for {
		p := 1
		for i := 0; i < dims; i++ {
			p *= r + 1
			if p > entries {
				return r
			}
		}
		r++
	}
}

// vorbisModes reads a setup header and returns each mode's block flag.
func vorbisModes(setup []byte, channels int) ([]bool, error) {
	if len(setup) < 7 || setup[0] != 5 || string(setup[1:7]) != "vorbis" {
		return nil, errors.New("not a Vorbis setup header")
	}
	r := &bitReader{b: setup, pos: 7 * 8}
	books := int(r.read(8)) + 1
	for i := 0; i < books && r.err == nil; i++ {
		if r.read(24) != 0x564342 {
			return nil, errors.New("bad codebook sync")
		}
		dims, entries := int(r.read(16)), int(r.read(24))
		if r.read(1) == 1 { // ordered
			r.read(5)
			for cur := 0; cur < entries && r.err == nil; {
				cur += int(r.read(ilog(uint32(entries - cur))))
			}
		} else {
			sparse := r.read(1) == 1
			for e := 0; e < entries && r.err == nil; e++ {
				if !sparse || r.read(1) == 1 {
					r.read(5)
				}
			}
		}
		switch lookup := r.read(4); lookup {
		case 0:
		case 1, 2:
			r.read(32)
			r.read(32)
			bits := int(r.read(4)) + 1
			r.read(1)
			values := entries * dims
			if lookup == 1 {
				values = lookup1Values(entries, dims)
			}
			r.pos += values * bits
		default:
			return nil, fmt.Errorf("bad codebook lookup type %d", lookup)
		}
	}
	for n := int(r.read(6)) + 1; n > 0; n-- { // time domain transforms (all zero)
		r.read(16)
	}
	floors := int(r.read(6)) + 1
	for i := 0; i < floors && r.err == nil; i++ {
		switch kind := r.read(16); kind {
		case 0:
			r.read(8)
			r.read(16)
			r.read(16)
			r.read(6)
			r.read(8)
			for n := int(r.read(4)) + 1; n > 0; n-- {
				r.read(8)
			}
		case 1:
			parts := int(r.read(5))
			classOf := make([]int, parts)
			maxClass := -1
			for p := range classOf {
				classOf[p] = int(r.read(4))
				maxClass = max(maxClass, classOf[p])
			}
			dims := make([]int, maxClass+1)
			for c := range dims {
				dims[c] = int(r.read(3)) + 1
				subs := int(r.read(2))
				if subs > 0 {
					r.read(8)
				}
				for s := 0; s < 1<<subs; s++ {
					r.read(8)
				}
			}
			r.read(2)
			rangeBits := int(r.read(4))
			for _, c := range classOf {
				r.pos += dims[c] * rangeBits
			}
		default:
			return nil, fmt.Errorf("bad floor type %d", kind)
		}
	}
	residues := int(r.read(6)) + 1
	for i := 0; i < residues && r.err == nil; i++ {
		if kind := r.read(16); kind > 2 {
			return nil, fmt.Errorf("bad residue type %d", kind)
		}
		r.read(24)
		r.read(24)
		r.read(24)
		classes := int(r.read(6)) + 1
		r.read(8)
		cascade := make([]uint32, classes)
		for c := range cascade {
			low := r.read(3)
			if r.read(1) == 1 {
				low |= r.read(5) << 3
			}
			cascade[c] = low
		}
		for _, c := range cascade {
			for b := 0; b < 8; b++ {
				if c>>b&1 != 0 {
					r.read(8)
				}
			}
		}
	}
	mappings := int(r.read(6)) + 1
	for i := 0; i < mappings && r.err == nil; i++ {
		if r.read(16) != 0 {
			return nil, errors.New("bad mapping type")
		}
		submaps := 1
		if r.read(1) == 1 {
			submaps = int(r.read(4)) + 1
		}
		if r.read(1) == 1 {
			steps := int(r.read(8)) + 1
			bits := ilog(uint32(channels - 1))
			r.pos += steps * 2 * bits
		}
		if r.read(2) != 0 {
			return nil, errors.New("bad mapping reserved bits")
		}
		if submaps > 1 {
			r.pos += channels * 4
		}
		r.pos += submaps * (8 + 8 + 8)
	}
	modes := make([]bool, int(r.read(6))+1)
	for i := range modes {
		modes[i] = r.read(1) == 1
		r.read(16)
		r.read(16)
		r.read(8)
	}
	if r.err != nil {
		return nil, r.err
	}
	if r.read(1) != 1 {
		return nil, errors.New("setup header framing bit is missing")
	}
	return modes, nil
}

// ---- Ogg ----

var oggCRC = func() (t [256]uint32) {
	for i := range t {
		r := uint32(i) << 24
		for j := 0; j < 8; j++ {
			if r&0x80000000 != 0 {
				r = r<<1 ^ 0x04c11db7
			} else {
				r <<= 1
			}
		}
		t[i] = r
	}
	return
}()

type oggWriter struct {
	out      bytes.Buffer
	serial   uint32
	sequence uint32
	segments []byte
	body     bytes.Buffer
	granule  int64
	first    bool
}

func (w *oggWriter) flush(last bool) {
	if len(w.segments) == 0 && !last {
		return
	}
	var flags byte
	if w.first {
		flags |= 2
		w.first = false
	}
	if last {
		flags |= 4
	}
	h := make([]byte, 27, 27+len(w.segments))
	copy(h, "OggS")
	h[5] = flags
	binary.LittleEndian.PutUint64(h[6:], uint64(w.granule))
	binary.LittleEndian.PutUint32(h[14:], w.serial)
	binary.LittleEndian.PutUint32(h[18:], w.sequence)
	h[26] = byte(len(w.segments))
	h = append(h, w.segments...)
	var crc uint32
	for _, part := range [][]byte{h, w.body.Bytes()} {
		for _, b := range part {
			crc = crc<<8 ^ oggCRC[byte(crc>>24)^b]
		}
	}
	binary.LittleEndian.PutUint32(h[22:], crc)
	w.out.Write(h)
	w.out.Write(w.body.Bytes())
	w.sequence++
	w.segments = w.segments[:0]
	w.body.Reset()
}

// packet adds one packet; a page ends after it when flushAfter is set or the page is full.
func (w *oggWriter) packet(p []byte, granule int64, flushAfter bool) {
	for left := p; ; {
		n := min(len(left), 255)
		if len(w.segments) == 255 { // page full mid-packet: continue on the next page
			w.flush(false)
		}
		w.segments = append(w.segments, byte(n))
		w.body.Write(left[:n])
		left = left[n:]
		if n < 255 {
			break
		}
	}
	w.granule = granule
	if flushAfter || w.body.Len() >= 4096 {
		w.flush(false)
	}
}

func vorbisIDHeader(channels, rate, blockShort, blockLong int) []byte {
	h := make([]byte, 30)
	h[0] = 1
	copy(h[1:], "vorbis")
	h[11] = byte(channels)
	binary.LittleEndian.PutUint32(h[12:], uint32(rate))
	h[28] = byte(ilog(uint32(blockShort))-1) | byte(ilog(uint32(blockLong))-1)<<4
	h[29] = 1
	return h
}

func vorbisCommentHeader() []byte {
	const vendor = "Bunker Archive"
	h := []byte{3, 'v', 'o', 'r', 'b', 'i', 's'}
	h = binary.LittleEndian.AppendUint32(h, uint32(len(vendor)))
	h = append(h, vendor...)
	h = binary.LittleEndian.AppendUint32(h, 0)
	return append(h, 1)
}

// fsbToOgg rebuilds one FSB5 Vorbis sample as an Ogg Vorbis file.
func fsbToOgg(s fsbSample) ([]byte, error) {
	setup, ok := vorbisSetups[s.crc32]
	if !ok {
		return nil, fmt.Errorf("unknown Vorbis setup (crc32 %d)", s.crc32)
	}
	modes, err := vorbisModes(setup.setup, s.channels)
	if err != nil {
		return nil, err
	}
	modeBits := ilog(uint32(len(modes) - 1))
	w := &oggWriter{serial: 1, first: true}
	w.packet(vorbisIDHeader(s.channels, s.frequency, setup.blockShort, setup.blockLong), 0, true)
	w.packet(vorbisCommentHeader(), 0, false)
	w.packet(setup.setup, 0, true)
	var granule int64
	prev := 0
	data := s.data
	for len(data) >= 2 {
		size := int(binary.LittleEndian.Uint16(data))
		if size == 0 || 2+size > len(data) {
			break
		}
		p := data[2 : 2+size]
		data = data[2+size:]
		if p[0]&1 != 0 {
			return nil, errors.New("FSB5 packet is not an audio packet")
		}
		r := &bitReader{b: p, pos: 1}
		mode := int(r.read(modeBits))
		if mode >= len(modes) {
			return nil, errors.New("FSB5 packet names an unknown mode")
		}
		block := setup.blockShort
		if modes[mode] {
			block = setup.blockLong
		}
		if prev != 0 {
			granule += int64((block + prev) / 4)
		}
		prev = block
		w.packet(p, granule, false)
	}
	w.flush(true)
	return w.out.Bytes(), nil
}

type vorbisSetup struct {
	blockShort, blockLong int
	setup                 []byte
}

// AudioToOgg writes the bundle's first AudioClip to target as Ogg Vorbis, through a temporary file.
func AudioToOgg(bundlePath, target string) error {
	b, err := OpenBundle(bundlePath)
	if err != nil {
		return err
	}
	for name, file := range b.Files {
		if strings.HasSuffix(name, ".resS") || strings.HasSuffix(name, ".resource") {
			continue
		}
		sf, err := ParseSerializedFile(file)
		if err != nil {
			continue
		}
		clips, err := sf.Objects(classIDs["AudioClip"])
		if err != nil {
			return err
		}
		for _, clip := range clips {
			resource, _ := clip.Fields["m_Resource"].(map[string]any)
			source, _ := resource["m_Source"].(string)
			data, ok := b.Files[path.Base(strings.TrimPrefix(source, "archive:/"))]
			offset, size := num(resource["m_Offset"]), num(resource["m_Size"])
			if !ok || offset < 0 || size <= 0 || offset+size > len(data) {
				return errors.New("audio data is missing from the bundle")
			}
			samples, err := parseFSB5(data[offset : offset+size])
			if err != nil {
				return err
			}
			if len(samples) == 0 {
				return errors.New("sound bank is empty")
			}
			ogg, err := fsbToOgg(samples[0])
			if err != nil {
				return err
			}
			if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
				return err
			}
			pending := target + ".tmp"
			if err := os.WriteFile(pending, ogg, 0o644); err != nil {
				return err
			}
			return os.Rename(pending, target)
		}
	}
	return errors.New("no audio clip in this bundle")
}

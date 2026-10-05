package unityasset

import (
	"encoding/binary"
	"fmt"
)

// ETC1 and ETC2 (RGB, and RGBA with an EAC alpha block): a Go port of texture2ddecoder's
// etc.cpp (MIT License, Copyright (c) 2020 K0lb3), as the ASTC decoder is.

var (
	etcWriteOrder    = [16]int{0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15}
	etcWriteOrderRev = [16]int{15, 11, 7, 3, 14, 10, 6, 2, 13, 9, 5, 1, 12, 8, 4, 0}
	etc1Modifiers    = [8][2]int{{2, 8}, {5, 17}, {9, 29}, {13, 42}, {18, 60}, {24, 80}, {33, 106}, {47, 183}}
	etc1Subblocks    = [2][16]int{{0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1}, {0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1}}
	etc2Distances    = [8]int{3, 6, 11, 16, 23, 32, 41, 64}
	etc2AlphaMods    = [16][8]int{
		{-3, -6, -9, -15, 2, 5, 8, 14}, {-3, -7, -10, -13, 2, 6, 9, 12}, {-2, -5, -8, -13, 1, 4, 7, 12},
		{-2, -4, -6, -13, 1, 3, 5, 12}, {-3, -6, -8, -12, 2, 5, 7, 11}, {-3, -7, -9, -11, 2, 6, 8, 10},
		{-4, -7, -8, -11, 3, 6, 7, 10}, {-3, -5, -8, -11, 2, 4, 7, 10}, {-2, -6, -8, -10, 1, 5, 7, 9},
		{-2, -5, -8, -10, 1, 4, 7, 9}, {-2, -4, -8, -10, 1, 3, 7, 9}, {-2, -5, -7, -10, 1, 4, 6, 9},
		{-3, -4, -7, -10, 2, 3, 6, 9}, {-1, -2, -3, -10, 0, 1, 2, 9}, {-4, -6, -8, -9, 3, 5, 7, 8},
		{-3, -5, -7, -9, 2, 4, 6, 8}}
)

func clampByte(n int) byte { return byte(clamp8(n)) }

// etcBlock is one 4x4 block of RGBA texels, row by row.
type etcBlock [16][4]byte

func (b *etcBlock) set(i int, c [3]byte, m int) {
	b[i] = [4]byte{clampByte(int(c[0]) + m), clampByte(int(c[1]) + m), clampByte(int(c[2]) + m), 255}
}

// subblocks fills a block from two base colours and their modifier tables (ETC1 and ETC2's
// individual and differential modes).
func (b *etcBlock) subblocks(d []byte, c [2][3]byte) {
	code := [2]int{int(d[3] >> 5), int(d[3] >> 2 & 7)}
	table := etc1Subblocks[d[3]&1]
	j, k := int(d[6])<<8|int(d[7]), int(d[4])<<8|int(d[5])
	for i := 0; i < 16; i, j, k = i+1, j>>1, k>>1 {
		s := table[i]
		m := etc1Modifiers[code[s]][j&1]
		if k&1 != 0 {
			m = -m
		}
		b.set(etcWriteOrder[i], c[s], m)
	}
}

func (b *etcBlock) individual(d []byte) {
	b.subblocks(d, [2][3]byte{
		{d[0]&0xf0 | d[0]>>4, d[1]&0xf0 | d[1]>>4, d[2]&0xf0 | d[2]>>4},
		{d[0]&0x0f | d[0]<<4, d[1]&0x0f | d[1]<<4, d[2]&0x0f | d[2]<<4},
	})
}

// paletted fills a block from four colours picked by two index bits (ETC2's T and H modes).
func (b *etcBlock) paletted(d []byte, set [4][4]byte) {
	j, k := int(d[6])<<8|int(d[7]), (int(d[4])<<8|int(d[5]))<<1
	for i := 0; i < 16; i, j, k = i+1, j>>1, k>>1 {
		b[etcWriteOrder[i]] = set[k&2|j&1]
	}
}

func shifted(c [3]byte, m int) [4]byte {
	return [4]byte{clampByte(int(c[0]) + m), clampByte(int(c[1]) + m), clampByte(int(c[2]) + m), 255}
}

func raw(c [3]byte) [4]byte { return [4]byte{c[0], c[1], c[2], 255} }

func (b *etcBlock) etc1(d []byte) {
	if d[3]&2 == 0 {
		b.individual(d)
		return
	}
	var c [2][3]byte
	for ch := 0; ch < 3; ch++ {
		base := d[ch] & 0xf8
		delta := int(d[ch])<<3&0x18 - int(d[ch])<<3&0x20
		c[0][ch] = base | base>>5
		second := byte(int(base) + delta)
		c[1][ch] = second | second>>5
	}
	b.subblocks(d, c)
}

func (b *etcBlock) etc2(d []byte) {
	if d[3]&2 == 0 {
		b.individual(d)
		return
	}
	r, g, bl := int(d[0]&0xf8), int(d[1]&0xf8), int(d[2]&0xf8)
	dr := int(d[0])<<3&0x18 - int(d[0])<<3&0x20
	dg := int(d[1])<<3&0x18 - int(d[1])<<3&0x20
	db := int(d[2])<<3&0x18 - int(d[2])<<3&0x20
	switch {
	case r+dr < 0 || r+dr > 255: // T
		c0 := [3]byte{d[0]<<3&0xc0 | d[0]<<4&0x30 | d[0]>>1&0xc | d[0]&3, d[1]&0xf0 | d[1]>>4, d[1]&0x0f | d[1]<<4}
		c1 := [3]byte{d[2]&0xf0 | d[2]>>4, d[2]&0x0f | d[2]<<4, d[3]&0xf0 | d[3]>>4}
		dist := etc2Distances[int(d[3]>>1&6)|int(d[3]&1)]
		b.paletted(d, [4][4]byte{raw(c0), shifted(c1, dist), raw(c1), shifted(c1, -dist)})
	case g+dg < 0 || g+dg > 255: // H
		var c0, c1 [3]byte
		c0[0] = d[0]<<1&0xf0 | d[0]>>3&0xf
		c0[1] = d[0]<<5&0xe0 | d[1]&0x10
		c0[1] |= c0[1] >> 4
		c0[2] = d[1]&8 | d[1]<<1&6 | d[2]>>7
		c0[2] |= c0[2] << 4
		c1[0] = d[2]<<1&0xf0 | d[2]>>3&0xf
		c1[1] = d[2]<<5&0xe0 | d[3]>>3&0x10
		c1[1] |= c1[1] >> 4
		c1[2] = d[3]<<1&0xf0 | d[3]>>3&0xf
		dist := int(d[3]&4 | d[3]<<1&2)
		if c0[0] > c1[0] || (c0[0] == c1[0] && (c0[1] > c1[1] || (c0[1] == c1[1] && c0[2] >= c1[2]))) {
			dist++
		}
		m := etc2Distances[dist]
		b.paletted(d, [4][4]byte{shifted(c0, m), shifted(c0, -m), shifted(c1, m), shifted(c1, -m)})
	case bl+db < 0 || bl+db > 255: // planar
		var c [3][3]byte
		c[0][0] = d[0]<<1&0xfc | d[0]>>5&3
		c[0][1] = d[0]<<7&0x80 | d[1]&0x7e | d[0]&1
		c[0][2] = d[1]<<7&0x80 | d[2]<<2&0x60 | d[2]<<3&0x18 | d[3]>>5&4
		c[0][2] |= c[0][2] >> 6
		c[1][0] = d[3]<<1&0xf8 | d[3]<<2&4 | d[3]>>5&3
		c[1][1] = d[4]&0xfe | d[4]>>7
		c[1][2] = d[4]<<7&0x80 | d[5]>>1&0x7c
		c[1][2] |= c[1][2] >> 6
		c[2][0] = d[5]<<5&0xe0 | d[6]>>3&0x1c | d[5]>>1&3
		c[2][1] = d[6]<<3&0xf8 | d[7]>>5&0x6 | d[6]>>4&1
		c[2][2] = d[7]<<2 | d[7]>>4&3
		for y := 0; y < 4; y++ {
			for x := 0; x < 4; x++ {
				var px [4]byte
				for ch := 0; ch < 3; ch++ {
					o, h, v := int(c[0][ch]), int(c[1][ch]), int(c[2][ch])
					px[ch] = clampByte((x*(h-o) + y*(v-o) + 4*o + 2) >> 2)
				}
				px[3] = 255
				b[y*4+x] = px
			}
		}
	default: // differential
		var c [2][3]byte
		for ch, base := range [3]int{r, g, bl} {
			delta := [3]int{dr, dg, db}[ch]
			c[0][ch] = byte(base) | byte(base)>>5
			second := byte(base + delta)
			c[1][ch] = second | second>>5
		}
		b.subblocks(d, c)
	}
}

// eacAlpha sets the block's alpha from an ETC2 RGBA8 alpha block.
func (b *etcBlock) eacAlpha(d []byte) {
	if d[1]&0xf0 == 0 {
		for i := range b {
			b[i][3] = d[0]
		}
		return
	}
	multiplier := int(d[1] >> 4)
	table := etc2AlphaMods[d[1]&0xf]
	l := binary.BigEndian.Uint64(d)
	for i := 0; i < 16; i, l = i+1, l>>3 {
		b[etcWriteOrderRev[i]][3] = clampByte(int(d[0]) + multiplier*table[l&7])
	}
}

// DecodeETC decodes ETC1 (format 34), ETC2 RGB (45) or ETC2 RGBA8 (47) data to RGBA.
func DecodeETC(data []byte, width, height, format int) ([]byte, error) {
	size := 8
	if format == formatETC2RGBA8 {
		size = 16
	}
	bx, by := (width+3)/4, (height+3)/4
	if len(data) < bx*by*size {
		return nil, fmt.Errorf("ETC data is %d bytes; %dx%d needs %d", len(data), width, height, bx*by*size)
	}
	img := make([]byte, width*height*4)
	var block etcBlock
	for y := 0; y < by; y++ {
		for x := 0; x < bx; x++ {
			d := data[(y*bx+x)*size:]
			switch format {
			case formatETC1:
				block.etc1(d)
			case formatETC2RGB:
				block.etc2(d)
			default:
				block.etc2(d[8:])
				block.eacAlpha(d)
			}
			for t := 0; t < 4 && y*4+t < height; t++ {
				for s := 0; s < 4 && x*4+s < width; s++ {
					copy(img[((y*4+t)*width+x*4+s)*4:], block[t*4+s][:])
				}
			}
		}
	}
	return img, nil
}

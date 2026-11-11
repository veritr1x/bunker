package unityasset

import (
	"bytes"
	"encoding/binary"
	"errors"
)

// Unity's build targets for the game's two clients. A bundle built for one
// does not load on the other.
const (
	PlatformIOS     = 9
	PlatformAndroid = 13
)

// PlatformName names a build target for the player.
func PlatformName(platform int) string {
	switch platform {
	case PlatformIOS:
		return "iOS"
	case PlatformAndroid:
		return "Android"
	}
	return "an unknown platform"
}

// BundlePlatform reads which platform a bundle was built for, from the header
// of the first serialized file in it.
func BundlePlatform(path string) (int, error) {
	b, err := OpenBundle(path)
	if err != nil {
		return 0, err
	}
	for _, data := range b.Files {
		if p, ok := serializedPlatform(data); ok {
			return p, nil
		}
	}
	return 0, errors.New("no serialized file in the bundle")
}

// serializedPlatform reads a serialized file's target platform: after its
// header (20 bytes, or 48 from format 22) comes the Unity version, then the
// platform, in the file's byte order.
func serializedPlatform(data []byte) (int, bool) {
	if len(data) < 20 {
		return 0, false
	}
	format := binary.BigEndian.Uint32(data[8:12])
	if format < 9 || format > 50 {
		return 0, false // a resource (.resS) file, not a serialized one
	}
	start := 20
	if format >= 22 {
		start = 48
	}
	if len(data) < start+1 {
		return 0, false
	}
	end := bytes.IndexByte(data[start:], 0)
	if end < 0 || start+end+5 > len(data) {
		return 0, false
	}
	raw := data[start+end+1 : start+end+5]
	if data[16] == 0 {
		return int(binary.LittleEndian.Uint32(raw)), true
	}
	return int(binary.BigEndian.Uint32(raw)), true
}

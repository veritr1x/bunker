package mobile

import "lunar-tear/server/mobile/unityasset"

// Texture writes the largest texture in an asset bundle to target as a PNG,
// for the Archive; maxSide > 0 shrinks it to fit. It returns "" or an error.
func Texture(bundle, target string, maxSide int) string {
	if err := unityasset.TextureToPNG(bundle, target, maxSide); err != nil {
		return err.Error()
	}
	return ""
}

// Audio writes the first audio clip in an asset bundle to target as Ogg Vorbis,
// for the Archive. It returns "" or an error.
func Audio(bundle, target string) string {
	if err := unityasset.AudioToOgg(bundle, target); err != nil {
		return err.Error()
	}
	return ""
}

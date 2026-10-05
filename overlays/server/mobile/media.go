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

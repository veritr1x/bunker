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

// Model writes the costume in actorFolder (…/3d/actor/ch008001) to target as a
// .glb, with textures no larger than 1024 pixels. It returns "" or an error.
func Model(actorFolder, target string) string {
	if err := unityasset.CostumeToGLB(actorFolder, target, unityasset.ModelOptions{MaxTexture: 1024}); err != nil {
		return err.Error()
	}
	return ""
}

// Motion writes the animation in clipBundle, for the costume in actorFolder, to
// target as three.js clip JSON sampled at 30 frames a second. It returns "" or an error.
func Motion(clipBundle, actorFolder, target string) string {
	if err := unityasset.ClipToJSON(clipBundle, actorFolder, target, 30); err != nil {
		return err.Error()
	}
	return ""
}

// Scenario writes, for the Archive's index, the story lines every event map in dir
// plays and who says them, as JSON to target. It returns "" or an error.
func Scenario(dir, target string) string {
	if err := unityasset.ScenarioToJSON(dir, target); err != nil {
		return err.Error()
	}
	return ""
}

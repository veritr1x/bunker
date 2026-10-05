package main

/*
#include <stdlib.h>
*/
import "C"
import "lunar-tear/server/mobile"

//export LunarStart
func LunarStart(data, assets *C.char) *C.char {
	if e := mobile.Start(C.GoString(data), C.GoString(assets)); e != nil {
		return C.CString(e.Error())
	}
	return C.CString("")
}

// LunarSetPortOffset applies the build's port offset before LunarStart.
//
//export LunarSetPortOffset
func LunarSetPortOffset(offset C.int) *C.char { return C.CString(mobile.SetPortOffset(int(offset))) }

// LunarPorts reports {"game":…,"assets":…,"accounts":…}.
//
//export LunarPorts
func LunarPorts() *C.char { return C.CString(mobile.Ports()) }

// LunarSelfTest checks that this server answers on each port as the game expects.
//
//export LunarSelfTest
func LunarSelfTest() *C.char { return C.CString(mobile.SelfTest()) }

//export LunarStop
func LunarStop() { mobile.Stop() }

//export LunarStatus
func LunarStatus() *C.char { return C.CString(mobile.Status()) }

//export LunarCheck
func LunarCheck(root *C.char) *C.char { return C.CString(mobile.CheckDatabase(C.GoString(root))) }

//export LunarPrepareBackup
func LunarPrepareBackup(root *C.char) *C.char {
	return C.CString(mobile.PrepareBackup(C.GoString(root)))
}

//export LunarTexture
func LunarTexture(bundle, target *C.char, maxSide C.int) *C.char {
	return C.CString(mobile.Texture(C.GoString(bundle), C.GoString(target), int(maxSide)))
}

//export LunarAudio
func LunarAudio(bundle, target *C.char) *C.char {
	return C.CString(mobile.Audio(C.GoString(bundle), C.GoString(target)))
}

//export LunarImportSaves
func LunarImportSaves(data, source *C.char) *C.char {
	return C.CString(mobile.ImportSaves(C.GoString(data), C.GoString(source)))
}

//export LunarImportArchive
func LunarImportArchive(source, stage *C.char) *C.char {
	return C.CString(mobile.ImportArchive(C.GoString(source), C.GoString(stage)))
}

// LunarSetLogDir also keeps the server log in dir, between sessions.
//
//export LunarSetLogDir
func LunarSetLogDir(dir *C.char) *C.char { return C.CString(mobile.SetLogDir(C.GoString(dir))) }

// LunarExportLogs writes a zip of the saved logs in dir and info to target.
//
//export LunarExportLogs
func LunarExportLogs(dir, target, info *C.char) *C.char {
	return C.CString(mobile.ExportLogs(C.GoString(dir), C.GoString(target), C.GoString(info)))
}

// LunarExportLogsFd is LunarExportLogs for a document the caller opened.
//
//export LunarExportLogsFd
func LunarExportLogsFd(dir *C.char, fd C.int, info *C.char) *C.char {
	return C.CString(mobile.ExportLogsFd(C.GoString(dir), int(fd), C.GoString(info)))
}

// LunarImportArchiveFd reads an archive the caller already opened (Android's
// document picker); Android 17 does not allow reopening it by path.
//
//export LunarImportArchiveFd
func LunarImportArchiveFd(fd C.int, stage *C.char) *C.char {
	return C.CString(mobile.ImportArchiveFd(int(fd), C.GoString(stage)))
}

//export LunarImportProgress
func LunarImportProgress() *C.char { return C.CString(mobile.ImportProgress()) }

//export LunarCancelImport
func LunarCancelImport() { mobile.CancelImport() }

//export LunarEdit
func LunarEdit(data, assets, request *C.char) *C.char {
	return C.CString(mobile.Edit(C.GoString(data), C.GoString(assets), C.GoString(request)))
}

func main() {}

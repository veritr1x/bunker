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

//export LunarImportSaves
func LunarImportSaves(data, source *C.char) *C.char {
	return C.CString(mobile.ImportSaves(C.GoString(data), C.GoString(source)))
}

//export LunarImportArchive
func LunarImportArchive(source, stage *C.char) *C.char {
	return C.CString(mobile.ImportArchive(C.GoString(source), C.GoString(stage)))
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

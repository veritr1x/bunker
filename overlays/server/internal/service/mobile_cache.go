package service

// ResetOctoCaches releases catalogs from a previous embedded-server run. Call
// only after its HTTP server has stopped: Android may keep this process alive
// while the user replaces the asset folder in the launcher.
func ResetOctoCaches() {
	for {
		listBinCacheMu.Lock()
		var pending []chan struct{}
		for _, load := range listBinInflight {
			pending = append(pending, load.done)
		}
		if len(pending) == 0 {
			listBinCache = make(map[string]listBinIndex)
			listBinCacheMu.Unlock()
			break
		}
		listBinCacheMu.Unlock()
		for _, done := range pending {
			<-done
		}
	}
	for {
		infoCacheMu.Lock()
		var pending []chan struct{}
		for _, load := range infoInflight {
			pending = append(pending, load.done)
		}
		if len(pending) == 0 {
			infoCache = make(map[string]map[string]infoAlias)
			infoCacheMu.Unlock()
			break
		}
		infoCacheMu.Unlock()
		for _, done := range pending {
			<-done
		}
	}
	fileMD5CacheMu.Lock()
	fileMD5Cache = make(map[string]fileMD5Entry)
	fileMD5CacheMu.Unlock()
}

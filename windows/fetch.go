package main

import (
	"archive/zip"
	"crypto/sha1"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// fetch downloads d to dest, picking up a partial download where it stopped, and
// checks its size and SHA-1 against Google's list. onProgress, if set, follows it.
func fetch(client *http.Client, d download, dest string, onProgress func(done, total int64)) error {
	part := dest + ".part"
	if done, err := os.Stat(dest); err == nil && done.Size() == d.Size {
		return verify(dest, d)
	}
	var have int64
	if st, err := os.Stat(part); err == nil && st.Size() < d.Size {
		have = st.Size()
	}
	req, err := http.NewRequest(http.MethodGet, d.URL, nil)
	if err != nil {
		return err
	}
	if have > 0 {
		req.Header.Set("Range", fmt.Sprintf("bytes=%d-", have))
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	flags := os.O_CREATE | os.O_WRONLY
	switch {
	case resp.StatusCode == http.StatusPartialContent && have > 0:
		flags |= os.O_APPEND
	case resp.StatusCode == http.StatusOK:
		have = 0
		flags |= os.O_TRUNC
	default:
		return fmt.Errorf("%s: %s", d.URL, resp.Status)
	}
	f, err := os.OpenFile(part, flags, 0o644)
	if err != nil {
		return err
	}
	p := &progress{report: onProgress, done: have, total: d.Size}
	_, err = io.Copy(f, io.TeeReader(resp.Body, p))
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		return fmt.Errorf("downloading %s: %w (start Bunker again to resume)", filepath.Base(dest), err)
	}
	if err := verify(part, d); err != nil {
		os.Remove(part)
		return err
	}
	return os.Rename(part, dest)
}

func verify(path string, d download) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	h := sha1.New()
	n, err := io.Copy(h, f)
	if err != nil {
		return err
	}
	if n != d.Size || hex.EncodeToString(h.Sum(nil)) != d.SHA1 {
		return fmt.Errorf("%s did not match Google's checksum, so it was deleted. Start Bunker again to download it again", filepath.Base(path))
	}
	return nil
}

type progress struct {
	report      func(done, total int64)
	done, total int64
}

func (p *progress) Write(b []byte) (int, error) {
	p.done += int64(len(b))
	if p.report != nil {
		p.report(p.done, p.total)
	}
	return len(b), nil
}

// unpack extracts a package archive into dest. Google's archives hold one folder
// (emulator/, platform-tools/, x86_64/), which becomes dest, as with sdkmanager.
// dest appears only once everything is extracted.
func unpack(archivePath, dest string) error {
	tmp := dest + ".unpack"
	if err := os.RemoveAll(tmp); err != nil {
		return err
	}
	if err := extract(archivePath, tmp); err != nil {
		os.RemoveAll(tmp)
		return err
	}
	entries, err := os.ReadDir(tmp)
	if err != nil {
		return err
	}
	src := tmp
	if len(entries) == 1 && entries[0].IsDir() {
		src = filepath.Join(tmp, entries[0].Name())
	}
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return err
	}
	if err := os.RemoveAll(dest); err != nil {
		return err
	}
	if err := os.Rename(src, dest); err != nil {
		return err
	}
	return os.RemoveAll(tmp)
}

func extract(archivePath, dest string) error {
	z, err := zip.OpenReader(archivePath)
	if err != nil {
		return err
	}
	defer z.Close()
	root, err := filepath.Abs(dest)
	if err != nil {
		return err
	}
	for _, f := range z.File {
		target, err := inside(root, f.Name)
		if err != nil {
			return err
		}
		mode := f.Mode()
		switch {
		case mode.IsDir():
			err = os.MkdirAll(target, 0o755)
		case mode&os.ModeSymlink != 0:
			err = extractLink(f, root, target)
		default:
			err = extractFile(f, target, mode.Perm()|0o600)
		}
		if err != nil {
			return fmt.Errorf("unpacking %s: %w", f.Name, err)
		}
	}
	return nil
}

// inside resolves an archive entry under root and refuses entries that leave it.
func inside(root, name string) (string, error) {
	target := filepath.Join(root, filepath.FromSlash(name))
	if target != root && !strings.HasPrefix(target, root+string(filepath.Separator)) {
		return "", fmt.Errorf("archive entry %q is outside the folder", name)
	}
	return target, nil
}

func extractFile(f *zip.File, target string, perm os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	r, err := f.Open()
	if err != nil {
		return err
	}
	defer r.Close()
	w, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, perm)
	if err != nil {
		return err
	}
	if _, err := io.Copy(w, r); err != nil {
		w.Close()
		return err
	}
	return w.Close()
}

// extractLink keeps the symbolic links in the macOS and Linux emulator archives.
func extractLink(f *zip.File, root, target string) error {
	r, err := f.Open()
	if err != nil {
		return err
	}
	link, err := io.ReadAll(io.LimitReader(r, 4096))
	r.Close()
	if err != nil {
		return err
	}
	dest := string(link)
	resolved := filepath.Join(filepath.Dir(target), dest)
	if filepath.IsAbs(dest) || (resolved != root && !strings.HasPrefix(resolved, root+string(filepath.Separator))) {
		return errors.New("link points outside the folder")
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	return os.Symlink(dest, target)
}

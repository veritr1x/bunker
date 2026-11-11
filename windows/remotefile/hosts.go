package remotefile

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"io"
	"mime"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
)

// The hosts' addresses, variables so tests can stand in for them.
var (
	archiveMetadataURL = "https://archive.org/metadata/"
	archiveDownloadURL = "https://archive.org/download/"
	mirrorScheme       = "https://"
	driveDownloadURL   = "https://drive.usercontent.google.com/download"
	megaAPIURL         = "https://g.api.mega.co.nz/cs"
)

var (
	errMegaFolder = errors.New("Mega folder links are not supported. Open the folder and copy the link of the .7z file.")
	errDriveQuota = errors.New("Google Drive's download limit for this file was reached. Try again later.")
	errMegaQuota  = errors.New("Mega's download limit for free users was reached. Try again later. Finished parts are kept.")
)

// classify names the host of a link and the parts that identify the file:
// archive.org's item and file path, Drive's file id, or Mega's handle and key.
func classify(u *url.URL) (kind, a, b string) {
	host := strings.TrimPrefix(strings.ToLower(u.Hostname()), "www.")
	switch {
	case host == "archive.org":
		parts := strings.SplitN(strings.TrimPrefix(u.Path, "/"), "/", 3)
		if len(parts) == 3 && (parts[0] == "download" || parts[0] == "details") && parts[1] != "" && parts[2] != "" {
			return "archive.org", parts[1], parts[2]
		}
	case host == "drive.google.com" || host == "drive.usercontent.google.com" || host == "docs.google.com":
		if id := u.Query().Get("id"); id != "" {
			return "drive", id, ""
		}
		if m := driveFilePath.FindStringSubmatch(u.Path); m != nil {
			return "drive", m[1], ""
		}
	case host == "mega.nz" || host == "mega.co.nz" || host == "mega.io":
		if strings.HasPrefix(u.Path, "/folder/") || strings.HasPrefix(u.Fragment, "F!") {
			return "mega-folder", "", ""
		}
		if handle, ok := strings.CutPrefix(u.Path, "/file/"); ok && u.Fragment != "" {
			key, _, _ := strings.Cut(u.Fragment, "/")
			return "mega", strings.TrimSuffix(handle, "/"), key
		}
		if rest, ok := strings.CutPrefix(u.Fragment, "!"); ok {
			if handle, key, ok := strings.Cut(rest, "!"); ok {
				return "mega", handle, key
			}
		}
	}
	return "http", "", ""
}

var driveFilePath = regexp.MustCompile(`/file/d/([A-Za-z0-9_-]+)`)

// resolve works out a link to the file it names.
func resolve(ctx context.Context, client *http.Client, u *url.URL) (source, error) {
	kind, a, b := classify(u)
	switch kind {
	case "archive.org":
		return archiveOrg(ctx, client, a, b)
	case "drive":
		return drive(ctx, client, a)
	case "mega":
		return mega(ctx, client, a, b)
	case "mega-folder":
		return source{}, errMegaFolder
	}
	return generic(ctx, client, u)
}

// archiveOrg reads the item's metadata for the file's size and storage
// servers. The download address redirects to a server that is sometimes
// down; the storage servers then serve the same file.
func archiveOrg(ctx context.Context, client *http.Client, item, file string) (source, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, archiveMetadataURL+url.PathEscape(item), nil)
	if err != nil {
		return source{}, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return source{}, fmt.Errorf("Cannot reach archive.org: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return source{}, fmt.Errorf("archive.org answered %d for the item %q", resp.StatusCode, item)
	}
	var meta struct {
		D1, D2, Dir string
		Files       []struct {
			Name string
			Size string
		}
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 64<<20)).Decode(&meta); err != nil {
		return source{}, fmt.Errorf("archive.org sent unreadable details for %q: %w", item, err)
	}
	var size int64
	for _, f := range meta.Files {
		if f.Name == file {
			size, _ = strconv.ParseInt(f.Size, 10, 64)
		}
	}
	if size <= 0 {
		return source{}, fmt.Errorf("archive.org has no file %q in the item %q. Copy the link of the .7z file itself.", file, item)
	}
	escaped := (&url.URL{Path: file}).EscapedPath()
	urls := []string{archiveDownloadURL + url.PathEscape(item) + "/" + escaped}
	for _, d := range []string{meta.D1, meta.D2} {
		if d != "" && meta.Dir != "" {
			urls = append(urls, mirrorScheme+d+meta.Dir+"/"+escaped)
		}
	}
	name := file[strings.LastIndex(file, "/")+1:]
	return source{urls: urls, size: size, id: fmt.Sprintf("archive.org %s/%s %d", item, file, size), name: name, host: "archive.org"}, nil
}

// drive asks Google Drive for the file. A large file first gets a page
// warning that it cannot be scanned for viruses; its form leads on to the file.
func drive(ctx context.Context, client *http.Client, id string) (source, error) {
	u := driveDownloadURL + "?" + url.Values{"id": {id}, "export": {"download"}, "confirm": {"t"}}.Encode()
	for range 3 {
		resp, err := rangeRequest(ctx, client, u, 0, 0)
		if err != nil {
			return source{}, fmt.Errorf("Cannot reach Google Drive: %w", err)
		}
		if resp.StatusCode == http.StatusPartialContent {
			resp.Body.Close()
			_, _, total, ok := contentRange(resp.Header.Get("Content-Range"))
			if !ok || total <= 0 {
				return source{}, ErrNoRanges
			}
			name := id
			if _, params, err := mime.ParseMediaType(resp.Header.Get("Content-Disposition")); err == nil && params["filename"] != "" {
				name = params["filename"]
			}
			return source{
				urls: []string{resp.Request.URL.String()}, size: total,
				id: fmt.Sprintf("drive %s %d", id, total), name: name, host: "drive",
				explain: func(code int) error {
					if code == http.StatusForbidden || code == http.StatusTooManyRequests {
						return errDriveQuota
					}
					return nil
				},
			}, nil
		}
		page, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		resp.Body.Close()
		text := string(page)
		switch {
		case resp.StatusCode == http.StatusForbidden || resp.StatusCode == http.StatusTooManyRequests ||
			strings.Contains(text, "Too many users") || strings.Contains(strings.ToLower(text), "quota"):
			return source{}, errDriveQuota
		case resp.StatusCode == http.StatusNotFound:
			return source{}, errors.New("Google Drive has no file for this link, or it is not shared with anyone who has the link.")
		case resp.StatusCode == http.StatusOK && !strings.Contains(resp.Header.Get("Content-Type"), "html"):
			return source{}, ErrNoRanges
		}
		next, ok := driveForm(text)
		if !ok {
			return source{}, errors.New("Google Drive did not offer the file for download. Check that the link is shared with anyone who has the link.")
		}
		u = next
	}
	return source{}, errors.New("Google Drive kept asking for confirmation instead of sending the file.")
}

var (
	formTag  = regexp.MustCompile(`(?is)<form[^>]*>`)
	formAttr = regexp.MustCompile(`(?is)\baction="([^"]*)"`)
	inputTag = regexp.MustCompile(`(?is)<input[^>]*>`)
	nameAttr = regexp.MustCompile(`(?is)\bname="([^"]*)"`)
	valAttr  = regexp.MustCompile(`(?is)\bvalue="([^"]*)"`)
)

// driveForm builds the address the warning page's download form submits to.
func driveForm(page string) (string, bool) {
	tag := formTag.FindString(page)
	action := formAttr.FindStringSubmatch(tag)
	if action == nil {
		return "", false
	}
	q := url.Values{}
	for _, in := range inputTag.FindAllString(page, -1) {
		n, v := nameAttr.FindStringSubmatch(in), valAttr.FindStringSubmatch(in)
		if n != nil && v != nil {
			q.Set(html.UnescapeString(n[1]), html.UnescapeString(v[1]))
		}
	}
	if q.Get("id") == "" {
		return "", false
	}
	return html.UnescapeString(action[1]) + "?" + q.Encode(), true
}

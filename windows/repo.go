package main

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"runtime"
	"strings"
)

// Google's SDK repository: the same lists sdkmanager reads. Nothing of the SDK is
// shipped with Bunker; each player downloads it from Google and accepts its license.
const (
	toolsRepo = "https://dl.google.com/android/repository/repository2-3.xml"
	imageRepo = "https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-3.xml"
)

// The Android 16 image with Google APIs and no Play Store: the one the game was
// tested on. Its x86_64 build runs ARM64 apps through Google's translation.
const imageAPI = "36"

type repository struct {
	base     *url.URL
	Licenses []struct {
		ID   string `xml:"id,attr"`
		Text string `xml:",chardata"`
	} `xml:"license"`
	Packages []remotePackage `xml:"remotePackage"`
}

type remotePackage struct {
	Path     string   `xml:"path,attr"`
	Revision revision `xml:"revision"`
	License  struct {
		Ref string `xml:"ref,attr"`
	} `xml:"uses-license"`
	Channel struct {
		Ref string `xml:"ref,attr"`
	} `xml:"channelRef"`
	Archives []archive `xml:"archives>archive"`
}

type revision struct {
	Major int `xml:"major"`
	Minor int `xml:"minor"`
	Micro int `xml:"micro"`
}

func (r revision) String() string { return fmt.Sprintf("%d.%d.%d", r.Major, r.Minor, r.Micro) }

func (r revision) less(o revision) bool {
	if r.Major != o.Major {
		return r.Major < o.Major
	}
	if r.Minor != o.Minor {
		return r.Minor < o.Minor
	}
	return r.Micro < o.Micro
}

type archive struct {
	Complete struct {
		Size     int64 `xml:"size"`
		Checksum struct {
			Type  string `xml:"type,attr"`
			Value string `xml:",chardata"`
		} `xml:"checksum"`
		URL string `xml:"url"`
	} `xml:"complete"`
	HostOS   string `xml:"host-os"`
	HostArch string `xml:"host-arch"`
}

// download is one archive to fetch, resolved against the list it came from.
type download struct {
	Path     string // SDK path, such as "emulator" or "system-images;android-36;google_apis;x86_64"
	Revision revision
	License  string
	URL      string
	Size     int64
	SHA1     string
}

func fetchRepository(client *http.Client, address string) (*repository, error) {
	resp, err := client.Get(address)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s: %s", address, resp.Status)
	}
	return parseRepository(resp.Body, address)
}

func parseRepository(r io.Reader, address string) (*repository, error) {
	base, err := url.Parse(address)
	if err != nil {
		return nil, err
	}
	repo := &repository{base: base}
	if err := xml.NewDecoder(r).Decode(repo); err != nil {
		return nil, fmt.Errorf("reading %s: %w", address, err)
	}
	return repo, nil
}

// pick returns the newest stable archive of a package for this host.
func (r *repository) pick(path, hostOS, hostArch string) (download, error) {
	var best *remotePackage
	var bestArchive *archive
	for i := range r.Packages {
		p := &r.Packages[i]
		// Packages without a channel are stable, as in sdkmanager.
		if p.Path != path || (p.Channel.Ref != "" && p.Channel.Ref != "channel-0") {
			continue
		}
		for j := range p.Archives {
			a := &p.Archives[j]
			if (a.HostOS == "" || a.HostOS == hostOS) && (a.HostArch == "" || a.HostArch == hostArch) {
				if best == nil || best.Revision.less(p.Revision) {
					best, bestArchive = p, a
				}
				break
			}
		}
	}
	if best == nil {
		return download{}, fmt.Errorf("Google's repository has no stable %s for %s %s", path, hostOS, hostArch)
	}
	if t := bestArchive.Complete.Checksum.Type; t != "" && t != "sha1" {
		return download{}, fmt.Errorf("%s: unexpected checksum type %q", path, t)
	}
	ref, err := url.Parse(strings.TrimSpace(bestArchive.Complete.URL))
	if err != nil {
		return download{}, err
	}
	return download{
		Path:     best.Path,
		Revision: best.Revision,
		License:  best.License.Ref,
		URL:      r.base.ResolveReference(ref).String(),
		Size:     bestArchive.Complete.Size,
		SHA1:     strings.ToLower(strings.TrimSpace(bestArchive.Complete.Checksum.Value)),
	}, nil
}

func (r *repository) license(id string) (string, bool) {
	for _, l := range r.Licenses {
		if l.ID == id {
			return strings.TrimSpace(l.Text), true
		}
	}
	return "", false
}

// licenseHash names a license's text, as sdkmanager does in licenses/<id>.
func licenseHash(text string) string {
	sum := sha1.Sum([]byte(strings.TrimSpace(text)))
	return hex.EncodeToString(sum[:])
}

// hostOS and hostArch name this computer as Google's repository does.
func hostOS() string {
	switch runtime.GOOS {
	case "windows":
		return "windows"
	case "darwin":
		return "macosx"
	}
	return "linux"
}

func hostArch() string {
	if runtime.GOARCH == "arm64" {
		return "aarch64"
	}
	return "x64"
}

// imageABI is x86_64 on Intel and AMD, which runs the game through ARM translation,
// and arm64-v8a on ARM computers such as Apple silicon Macs, which run it directly.
func imageABI() string {
	if runtime.GOARCH == "arm64" {
		return "arm64-v8a"
	}
	return "x86_64"
}

func imagePath() string { return "system-images;android-" + imageAPI + ";google_apis;" + imageABI() }

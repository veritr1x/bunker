package remotefile

import (
	"bytes"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// mega asks Mega's API for a download address. Mega stores files encrypted
// with AES-128 in counter mode; the key is in the link after the "#", and
// never leaves this device.
func mega(ctx context.Context, client *http.Client, handle, linkKey string) (source, error) {
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(linkKey, "="))
	if err != nil || len(raw) != 32 {
		if err == nil && len(raw) == 16 {
			return source{}, errMegaFolder
		}
		return source{}, errors.New("This Mega link has no valid key. Copy the whole link, including the part after #.")
	}
	key := make([]byte, 16)
	for i := range key {
		key[i] = raw[i] ^ raw[i+16]
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return source{}, err
	}
	nonce := raw[16:24]

	size, link, attrs, err := megaFile(ctx, client, handle)
	if err != nil {
		return source{}, err
	}
	name := megaName(block, attrs)
	if name == "" {
		name = handle
	}
	return source{
		urls: []string{link},
		size: size,
		id:   fmt.Sprintf("mega %s %d", handle, size),
		name: name,
		host: "mega",
		decrypt: func(p []byte, off int64) {
			iv := make([]byte, 16)
			copy(iv, nonce)
			binary.BigEndian.PutUint64(iv[8:], uint64(off/16))
			stream := cipher.NewCTR(block, iv)
			if skip := int(off % 16); skip > 0 {
				waste := make([]byte, skip)
				stream.XORKeyStream(waste, waste)
			}
			stream.XORKeyStream(p, p)
		},
		refresh: func(ctx context.Context) (string, error) {
			_, fresh, _, err := megaFile(ctx, client, handle)
			return fresh, err
		},
		explain: func(code int) error {
			if code == 509 {
				return errMegaQuota
			}
			return nil
		},
	}, nil
}

// megaFile asks the API for the file's size, a temporary download address
// and its encrypted attributes.
func megaFile(ctx context.Context, client *http.Client, handle string) (int64, string, string, error) {
	body, _ := json.Marshal([]map[string]any{{"a": "g", "g": 1, "ssl": 1, "p": handle}})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, megaAPIURL, bytes.NewReader(body))
	if err != nil {
		return 0, "", "", err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return 0, "", "", fmt.Errorf("Cannot reach Mega: %w", err)
	}
	defer resp.Body.Close()
	answer, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return 0, "", "", fmt.Errorf("Cannot reach Mega: %w", err)
	}
	if resp.StatusCode == 509 {
		return 0, "", "", errMegaQuota
	}
	var code int
	if json.Unmarshal(answer, &code) == nil {
		return 0, "", "", megaError(code)
	}
	var items []json.RawMessage
	if err := json.Unmarshal(answer, &items); err != nil || len(items) == 0 {
		return 0, "", "", fmt.Errorf("Mega sent an unreadable answer (%d)", resp.StatusCode)
	}
	if json.Unmarshal(items[0], &code) == nil {
		return 0, "", "", megaError(code)
	}
	var file struct {
		S  int64  `json:"s"`
		G  string `json:"g"`
		At string `json:"at"`
	}
	if err := json.Unmarshal(items[0], &file); err != nil || file.G == "" || file.S <= 0 {
		return 0, "", "", errors.New("Mega did not offer the file for download.")
	}
	return file.S, file.G, file.At, nil
}

func megaError(code int) error {
	switch code {
	case -17, -18:
		return errMegaQuota
	case -9, -2:
		return errors.New("This Mega link points to no file. It may have been removed.")
	case -16:
		return errors.New("Mega has blocked this file.")
	case -11:
		return errors.New("Mega refused access to this file.")
	}
	return fmt.Errorf("Mega refused the link (error %d).", code)
}

// megaName decrypts the attributes ("MEGA{"n":"name",...}", AES-CBC with a
// zero IV) for the file's name, or "".
func megaName(block cipher.Block, attrs string) string {
	data, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(attrs, "="))
	if err != nil || len(data) == 0 || len(data)%16 != 0 {
		return ""
	}
	cipher.NewCBCDecrypter(block, make([]byte, 16)).CryptBlocks(data, data)
	text, ok := bytes.CutPrefix(bytes.TrimRight(data, "\x00"), []byte("MEGA"))
	if !ok {
		return ""
	}
	var a struct{ N string }
	if json.Unmarshal(text, &a) != nil {
		return ""
	}
	return a.N
}

package remotefile

import (
	"context"
	"net/http"
	"net/url"
)

// resolve works out a link to the file it names.
func resolve(ctx context.Context, client *http.Client, u *url.URL) (source, error) {
	return generic(ctx, client, u)
}

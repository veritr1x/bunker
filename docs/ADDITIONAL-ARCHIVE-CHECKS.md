# Additional archive and source checks

These checks preserve source evidence separately from the original website
notice pack. None establishes an additional original website image path.

## Archived repository

The Internet Archive item
[BillyCool/MariesWonderland, March 18, 2026](https://archive.org/details/github.com-BillyCool-MariesWonderland_-_2026-03-18_09-50-05)
contains a Git bundle whose published SHA-1 was verified. Its SHA-256 is
`adabf06fed7ee28e286e93017a3ba7069b63b35332204dee1b4c2561c4d1a01e`.
The archived tip is `98d5b1ea1eda29e95b0d526bd1749aa78f362cc3`.
The underlying game build represented by its master exports is not established.

All 2,365 reachable Git blobs, totaling 184,481,839 bytes, were read with their
Git object hashes verified. This found no PNG/JPEG/GIF/WebP payload, exact
missing image filename key, or `/api/information/` body. One notice-host
reference occurs in an APK patching notebook. No repository code was executed.

The repository nevertheless adds useful text evidence: five text exports
contain 92 Japanese row versions absent from all 660 checked global snapshots.
These are preserved in the separate [native pop-up collection](NATIVE-POPUPS.md).
Row versions are not necessarily distinct sentences, new entities, or notices.

## Ten selected nested archives

Bounded HTTP ranges were read from the public
[Accord's Library backup](https://archive.org/details/accordslibrarybackup)
member `Accord's Library/resha.re.zip`; the full 43,316,123,745-byte ZIP was not
downloaded. The selected scope completed for these ten nested archives:

- `Websites/theark.wiki.wacz`
- `Websites/musou.ru.wacz`
- `Websites/www.grimoire-cendre.fr.wacz`
- `Websites/rikoren.dreamwidth.org.wacz`
- `Webpages/ffLml.zip`
- `Webpages/HPo3s.zip`
- `Webpages/kYY0j.zip`
- `Webpages/QE5XG.zip`
- `Webpages/s65zI.zip`
- `Webpages/UD4f8.zip`

For WACZ files, the checked scope is the inner member catalog, complete
compressed CDX index, primary page metadata and data-package metadata. It does
not include every captured WARC payload. The additional 20.7 MB musou page
metadata was not read; its CDX index was checked. Concatenated gzip index
members were fully decoded within the recorded resource limits.

For the six small nested ZIPs, complete outer-member bytes were saved and
CRC checked. WACZ outer-member CRCs cannot be verified from partial ranges;
the retrieved inner resources have CRC and SHA-256 checks. No tested resource
contained the original notice operations host/path or an exact missing image
filename key. This result does not establish that the whole 43 GB archive or
the whole web lacks relevant data.

## Public Drive banner samples

The observed public folder has 863 promotion filenames with native
counterparts. Six PNGs were downloaded and compared: `prm002`, `prm003`,
`prm016`, `prm671`, `prm777` and `prm1068`. All six have matching dimensions
and were visually reviewed as the same artwork and text. None is byte-identical
or exactly RGBA-identical to the native export. Their maximum absolute channel
difference is 1/255. Decoder rounding is a possible explanation, not an
established cause. These samples do not prove byte or visual equivalence for
the remaining 857 files, and no additional campaign variant was established.

## Live Guide notice

The browser-rendered [notice 1608](https://nierrein.guide/notice/1608) has the
same body as the saved source. All eight original-host image elements failed
to decode, and no additional image proxy host was observed on this page.
The separate direct HTTP request returned 403. This one-page result is not a
claim about every Guide notice.

## Preserved evidence

`inputs/bunker-additional-source-checks.zip` contains the source manifests,
retrieved index/metadata resources, six Drive PNGs, pixel comparisons, browser
observations, archived Git bundle, scoped inspection scripts and a SHA-256
file manifest. The Git object database is omitted because the verified bundle
preserves its source objects. Native text/images have their own collection.
Six native PNG comparison copies and a portable pair manifest are also included
so the sample pixel comparisons can be reproduced without the source machine.

The remaining original website image gap is 764 paths. The default notice pack
is unchanged; source or locale similarity alone does not authorize replacing
an original image path.

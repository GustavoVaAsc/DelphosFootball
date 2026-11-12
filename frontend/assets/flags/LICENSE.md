# Flag images

The PNG files in this directory are the 80-pixel-wide (`w80`) country flags published by Flagpedia at `https://flagcdn.com/w80/<code>.png`. They were downloaded once on 2026-11-10 and are bundled with the app, so the client never requests them at runtime (ADR-026 in `docs/ARCHITECTURE.md`).

Licence: Flagpedia states that its flag images are in the public domain (exempt from copyright) and free for commercial and non-commercial use (`https://flagpedia.net/about`). The images are derived from the public-domain flag drawings on Wikimedia Commons.

Attribution: flag images by Flagpedia.net (`https://flagpedia.net`).

Each file is named after the code in `lib/ui/core/labels/countries.dart`: ISO 3166-1 alpha-2 in lower case, plus `gb-eng`, `gb-sct`, `gb-wls`, `gb-nir` and `xk` (Kosovo). Only the codes that table uses are bundled. To add a country, add its row to the table and download its flag with:

```sh
curl -sSfL -o assets/flags/<code>.png https://flagcdn.com/w80/<code>.png
```

The test `test/ui/core/labels/countries_test.dart` fails when a code in the table has no file here, or when a file here has no code in the table.

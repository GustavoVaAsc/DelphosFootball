/// The allowlist for the dataset's portrait and crest URLs (ADR-026).
///
/// The backend passes Transfermarkt URLs through from the dataset, so a
/// changed or poisoned row could point anywhere. A URL survives only when it
/// is https on one of [allowedImageHosts] with no port and no credentials;
/// anything else becomes `null` and the UI shows its placeholder.
///
/// Keep [allowedImageHosts] in sync with both `img-src` and `connect-src` in
/// `frontend/nginx/security-headers.inc.template` (Image.network fetches the
/// bytes): a host on one list and not the others either never loads or
/// loads unchecked.
library;

/// The two image hosts of the dataset.
const Set<String> allowedImageHosts = {
  'img.a.transfermarkt.technology',
  'tmssl.akamaized.net',
};

/// [url] when it is an allowed image URL, otherwise `null`.
String? allowedImageUrl(String? url) {
  final uri = url == null ? null : Uri.tryParse(url);
  if (uri == null ||
      uri.scheme != 'https' ||
      uri.userInfo.isNotEmpty ||
      uri.hasPort ||
      !allowedImageHosts.contains(uri.host)) {
    return null;
  }
  return uri.toString();
}

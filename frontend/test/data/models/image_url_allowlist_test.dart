// Tests for the portrait and crest URL allowlist: only https URLs on the two
// dataset image hosts survive, everything else becomes null.
import 'package:delphos_frontend/data/models/image_url_allowlist.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('keeps https URLs on the two dataset image hosts', () {
    const portrait =
        'https://img.a.transfermarkt.technology/portrait/header/'
        '566723-1762944477.jpg?lm=1';
    const crest = 'https://tmssl.akamaized.net/images/wappen/head/27.png';
    expect(allowedImageUrl(portrait), portrait);
    expect(allowedImageUrl(crest), crest);
  });

  test('drops other schemes, hosts, ports and credentials', () {
    for (final url in [
      'http://tmssl.akamaized.net/images/wappen/head/27.png',
      'https://evil.example/x.png',
      'https://tmssl.akamaized.net.evil.example/x.png',
      'https://sub.tmssl.akamaized.net/x.png',
      'https://tmssl.akamaized.net:8443/x.png',
      'https://user:pass@tmssl.akamaized.net/x.png',
      '//tmssl.akamaized.net/x.png',
      'javascript:alert(1)',
      'data:image/png;base64,AAAA',
      '/assets/x.png',
      'https://[::1]/x.png',
      'not a url',
      '',
    ]) {
      expect(allowedImageUrl(url), isNull, reason: url);
    }
  });

  test('passes null through', () {
    expect(allowedImageUrl(null), isNull);
  });
}

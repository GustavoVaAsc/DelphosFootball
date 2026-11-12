// Tests for the report HTML sanitizer (ADR-028): only p, strong, em and br
// survive, without attributes; other elements are unwrapped to their text;
// scripts, styles, images and media are dropped with their content; text is
// re-escaped; the input is capped at about 20 KB.
import 'package:delphos_frontend/ui/core/html/report_html_sanitizer.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('the ADR-028 input keeps only the text t', () {
    expect(
      sanitizeReportHtml(
        '<p onclick=x><img src=//evil><a href=javascript:1>t</a>'
        '<script>y</script></p>',
      ),
      '<p>t</p>',
    );
  });

  test('keeps the four allowed tags and strips every attribute', () {
    expect(
      sanitizeReportHtml(
        '<p class="x" style="color:red"><strong id=a>A</strong> '
        '<em>b</em><br/>c</p>',
      ),
      '<p><strong>A</strong> <em>b</em><br>c</p>',
    );
  });

  test('unwraps other elements to their text', () {
    expect(sanitizeReportHtml('<div><span>x</span><h1>y</h1></div>'), 'xy');
  });

  test('drops images, media, frames, styles and comments whole', () {
    expect(
      sanitizeReportHtml(
        '<!-- c --><p>a<picture><source srcset=x>z</picture>'
        '<iframe src=x>i</iframe><style>s</style><video>v</video>'
        '<svg><text>g</text></svg>b</p>',
      ),
      '<p>ab</p>',
    );
  });

  test('re-escapes text, so an entity never becomes markup', () {
    expect(
      sanitizeReportHtml('<p>a &lt;img src=x&gt; &amp; O&#x27;Neil</p>'),
      "<p>a &lt;img src=x&gt; &amp; O'Neil</p>",
    );
  });

  test('caps the input at about 20 KB', () {
    final long = '<p>${'a' * 30000}</p>';
    final clean = sanitizeReportHtml(long);
    expect(clean.length, lessThanOrEqualTo(reportHtmlLimit + 16));
    expect(clean, startsWith('<p>aaa'));
  });
}
